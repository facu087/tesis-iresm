"""
Tests de extracción de biomarcadores e historial terapéutico
(backend/ingestion/biomarker_extractor.py).

Tests unitarios: no llaman APIs externas ni necesitan GROQ_API_KEY. La capa
regex es determinista y se prueba directo; la capa LLM se mockea.

Caso de prueba base del proyecto: neuropatía axonal sensitivomotora,
paciente masculino de 42 años.
"""

from unittest.mock import patch

import pytest

from backend.ingestion.biomarker_extractor import (
    _extract_with_regex,
    _merge_results,
    extract,
)
from backend.models.biomarkers import BiomarkerProfile

CASO_CLINICO = """
Paciente masculino de 42 años con neuropatía axonal sensitivomotora progresiva
de 18 meses de evolución. Compromiso autonómico asociado (hipotensión ortostática,
disfunción sudomotora). Panel genético reducido (CMT panel de 40 genes) negativo.
Electromiograma: axonal difuso sin desmielinización. LCR normal. Anticuerpos
paraneoplásicos estándar (anti-Hu, anti-Yo, anti-Ri) negativos. 3 años de
seguimiento sin diagnóstico. Edad de inicio: 40 años. Antecedentes familiares:
padre con "problemas de equilibrio" no estudiados.
""".strip()


@pytest.fixture
def regex_caso() -> dict:
    return _extract_with_regex(CASO_CLINICO)


# ── Genes: el bug de los falsos positivos ──────────────────────────────────────

class TestGenesFalsosPositivos:
    """
    CMT, FAP y ATTR son siglas de ENFERMEDAD, no de gen, y se reportaban como
    "genes identificados". _GENE_PATTERN matchea cualquier sigla de 2-6
    mayúsculas, así que el único filtro es _NON_GENE_TERMS: sacarlas de
    _KNOWN_GENES no cambiaba nada.
    """

    @pytest.mark.parametrize("sigla", ["CMT", "FAP", "ATTR"])
    def test_sigla_de_enfermedad_no_es_gen(self, sigla):
        texto = f"Panel de {sigla} negativo en el estudio."
        assert sigla not in _extract_with_regex(texto)["genes_regex"]

    def test_caso_base_no_reporta_cmt_como_gen(self, regex_caso):
        """El caso dice 'CMT panel de 40 genes' y encima es un hallazgo NEGATIVO."""
        assert "CMT" not in regex_caso["genes_regex"]

    @pytest.mark.parametrize("sigla", ["LCR", "EMG", "RMN", "PCR"])
    def test_siglas_clinicas_no_son_genes(self, sigla):
        texto = f"Se realizó {sigla} sin hallazgos."
        assert sigla not in _extract_with_regex(texto)["genes_regex"]


class TestGenesVerdaderos:
    @pytest.mark.parametrize("gen", ["PMP22", "TTR", "MPZ", "GJB1", "MFN2", "KCNQ2", "HBB"])
    def test_genes_reales_se_detectan(self, gen):
        texto = f"Se identificó una variante en el gen {gen}."
        assert gen in _extract_with_regex(texto)["genes_regex"]

    @pytest.mark.xfail(
        reason=(
            "Defecto conocido, fuera del alcance de este fix (falsos positivos): "
            r"_GENE_PATTERN es [A-Z]{2,6}\d{0,2}, así que un dígito EN EL MEDIO del "
            r"símbolo corta el match y el  final no cierra. Afecta a 4 de los 51 "
            "genes de _KNOWN_GENES, todos relevantes para el caso de la tesis "
            "(SCN1A, SCN9A, SH3TC2, DYNC1H1). Ver tarjeta de Trello aparte."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("gen", ["SCN1A", "SCN9A", "SH3TC2", "DYNC1H1"])
    def test_genes_con_digito_intermedio_no_se_detectan(self, gen):
        texto = f"Se identificó una variante en el gen {gen}."
        assert gen in _extract_with_regex(texto)["genes_regex"]

    def test_ttr_se_detecta_aunque_attr_no(self):
        """El gen de la amiloidosis ATTR es TTR: uno entra y la otra no."""
        genes = _extract_with_regex("Sospecha de ATTR; se secuencia el gen TTR.")["genes_regex"]
        assert "TTR" in genes
        assert "ATTR" not in genes


# ── Variantes genéticas ────────────────────────────────────────────────────────

class TestVariantes:
    @pytest.mark.parametrize("variante", ["p.Val30Met", "c.148G>A"])
    def test_variantes_se_detectan(self, variante):
        texto = f"Variante {variante} en heterocigosis."
        assert variante in _extract_with_regex(texto)["variants_regex"]


# ── Anticuerpos ────────────────────────────────────────────────────────────────

class TestAnticuerpos:
    def test_detecta_los_tres_paraneoplasicos_del_caso(self, regex_caso):
        encontrados = " ".join(regex_caso["antibodies_regex"]).lower()
        for ab in ("hu", "yo", "ri"):
            assert f"anti-{ab}" in encontrados

    @pytest.mark.parametrize("termino", ["anticuerpos", "antiinflamatorio", "anticoagulante"])
    def test_palabras_que_empiezan_con_anti_no_son_anticuerpos(self, termino):
        """Sin separador no es un anticuerpo: 'anticuerpos' es anti + cuerpos."""
        resultado = _extract_with_regex(f"Se indicó {termino} por 3 meses.")
        assert resultado["antibodies_regex"] == []


# ── Biomarcadores de laboratorio ───────────────────────────────────────────────

class TestBiomarcadoresLab:
    def test_detecta_marcador_por_palabra_completa(self):
        assert "vitamina b12" in _extract_with_regex("Vitamina B12 en rango bajo.")["lab_markers_regex"]

    def test_no_matchea_dentro_de_otra_palabra(self):
        """'ana' no debe matchear dentro de 'analizados'."""
        assert "ana" not in _extract_with_regex("Los estudios analizados fueron normales.")["lab_markers_regex"]


# ── Fusión regex + LLM ─────────────────────────────────────────────────────────

class TestMergeResults:
    def test_el_llm_no_puede_reintroducir_una_enfermedad_como_gen(self):
        """El LLM es la otra mitad de la extracción y también inventa genes."""
        perfil = _merge_results(
            {"genes_regex": ["TTR"]},
            {"genes": ["CMT", "ATTR", "PMP22"]},
        )
        assert "CMT" not in perfil.genes
        assert "ATTR" not in perfil.genes
        assert set(perfil.genes) == {"TTR", "PMP22"}

    def test_fusiona_sin_duplicar(self):
        perfil = _merge_results({"genes_regex": ["TTR"]}, {"genes": ["TTR", "MPZ"]})
        assert perfil.genes == ["TTR", "MPZ"]

    def test_devuelve_biomarker_profile(self):
        assert isinstance(_merge_results({}, {}), BiomarkerProfile)


# ── extract() completo, con el LLM mockeado ────────────────────────────────────

class TestExtract:
    def test_caso_base_end_to_end(self):
        respuesta_llm = {
            "genes": ["CMT"],  # el LLM insiste con la enfermedad
            "antibodies": [],
            "lab_biomarkers": [],
            "genetic_variants": [],
            "pathways": ["neuropatía axonal", "amiloidosis"],
            "therapeutic_history": {
                "drugs": [],
                "procedures": ["Electromiograma", "Punción lumbar"],
                "surgeries": [],
            },
        }
        with patch(
            "backend.ingestion.biomarker_extractor._extract_with_llm",
            return_value=respuesta_llm,
        ):
            perfil = extract(CASO_CLINICO)

        assert "CMT" not in perfil.genes
        assert any("electro" in p.lower() for p in perfil.procedures)
        assert perfil.pathways == ["neuropatía axonal", "amiloidosis"]

    def test_no_requiere_api_key(self):
        """extract() con el LLM mockeado no toca os.environ['GROQ_API_KEY']."""
        with patch("backend.ingestion.biomarker_extractor._extract_with_llm", return_value={}):
            perfil = extract("Variante p.Val30Met en el gen TTR.")
        assert "TTR" in perfil.genes
        assert "p.Val30Met" in perfil.genetic_variants
