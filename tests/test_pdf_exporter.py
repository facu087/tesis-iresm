"""
Tests del exportador PDF (backend/pipeline/pdf_exporter.py).
Verifica que generate_pdf() produzca un PDF válido con el contenido esperado.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import io

import pdfplumber

from backend.api.schemas import (
    CaseSummarySection,
    DebateSummary,
    RankedHypothesis,
    ReportMetadata,
    StructuredReport,
    VerificationSummary,
)
from backend.main import app
from backend.models.hypothesis import Source
from backend.models.trial import ClinicalTrial, RareDiseaseMatch, TrialSearchSummary
from backend.pipeline.pdf_exporter import _limpiar, generate_pdf


def _texto_del_pdf(pdf_bytes: bytes) -> str:
    """Extrae el texto del PDF para poder afirmar sobre su contenido."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_report(
    hypotheses: list[RankedHypothesis] | None = None,
    trials: list[ClinicalTrial] | None = None,
    bibliography: list[Source] | None = None,
    divergences: list[str] | None = None,
) -> StructuredReport:
    return StructuredReport(
        metadata=ReportMetadata(
            generated_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
            nexus_version="0.3.0",
            processing_time_seconds=42.5,
        ),
        case_summary=CaseSummarySection(
            narrative="Paciente varón de 42 años con neuropatía axonal sensitivomotora.",
            patient_profile="Varón, 42 años",
            chief_complaint="neuropatía axonal",
            disease_duration="2 años",
            current_treatments=["pregabalina"],
            relevant_history=["diabetes tipo 2"],
            procedures_done=["EMG", "biopsia de nervio"],
        ),
        hypotheses=hypotheses or [
            RankedHypothesis(
                rank=1,
                text="Neuropatía axonal por deficiencia de vitamina B12.",
                priority="HIGH",
                evidence_level="II",
                rationale="Hallazgos compatibles con déficit.",
                supporting_agents=["Analista de Literatura", "Consultor Clínico"],
                sources=[Source(pmid="12345678", title="Estudio B12", year=2022)],
            ),
            RankedHypothesis(
                rank=2,
                text="Neuropatía axonal de origen paraneoplásico.",
                priority="MEDIUM",
                evidence_level="III",
                rationale="Descartar origen oncológico.",
                supporting_agents=["Consultor Clínico"],
                sources=[],
            ),
        ],
        debate_summary=DebateSummary(
            rounds_completed=4,
            total_critiques=3,
            divergences=divergences or [],
            consensus_reached=True,
        ),
        clinical_trials=trials or [
            ClinicalTrial(
                nct_id="NCT04000001",
                title="Estudio de neuropatía axonal hereditaria",
                status="RECRUITING",
                brief_summary="Ensayo sobre tratamiento.",
                conditions=["Axonal Neuropathy"],
                phase="PHASE3",
                locations=["Argentina", "Brazil"],
                min_age="18 Years",
                max_age="70 Years",
                url="https://clinicaltrials.gov/study/NCT04000001",
            )
        ],
        bibliography=bibliography or [
            Source(pmid="12345678", title="Estudio B12 y neuropatía", journal="NEJM", year=2022),
        ],
    )


# ── Tests: generate_pdf ────────────────────────────────────────────────────────

class TestGeneratePdf:
    def test_devuelve_bytes(self):
        result = generate_pdf(_make_report())
        assert isinstance(result, bytes)

    def test_es_pdf_valido(self):
        result = generate_pdf(_make_report())
        assert result[:4] == b"%PDF"

    def test_pdf_no_vacio(self):
        result = generate_pdf(_make_report())
        assert len(result) > 1024  # al menos 1 KB

    def test_sin_hipotesis(self):
        result = generate_pdf(_make_report(hypotheses=[]))
        assert result[:4] == b"%PDF"

    def test_sin_trials(self):
        result = generate_pdf(_make_report(trials=[]))
        assert result[:4] == b"%PDF"

    def test_sin_bibliografia(self):
        result = generate_pdf(_make_report(bibliography=[]))
        assert result[:4] == b"%PDF"

    def test_con_divergencias(self):
        result = generate_pdf(_make_report(
            divergences=["Agente 01 mantuvo hipótesis criticada [HIGH] por Agente 03."]
        ))
        assert result[:4] == b"%PDF"

    def test_caso_sin_pico(self):
        report = _make_report()
        report.case_summary = CaseSummarySection(
            narrative="Narrativa básica sin campos PICO.",
        )
        result = generate_pdf(report)
        assert result[:4] == b"%PDF"

    def test_hipotesis_con_muchas_fuentes(self):
        h = RankedHypothesis(
            rank=1,
            text="Hipótesis con muchas fuentes.",
            priority="HIGH",
            evidence_level="I",
            rationale="Bien respaldada.",
            supporting_agents=[],
            sources=[
                Source(pmid=f"{i:08d}", title=f"Estudio {i}", year=2020 + i)
                for i in range(10)
            ],
        )
        result = generate_pdf(_make_report(hypotheses=[h]))
        assert result[:4] == b"%PDF"

    def test_texto_largo_no_falla(self):
        h = RankedHypothesis(
            rank=1,
            text="X " * 500,
            priority="LOW",
            evidence_level="III",
            rationale="Razonamiento " * 100,
            supporting_agents=["Agente 01"],
            sources=[],
        )
        result = generate_pdf(_make_report(hypotheses=[h]))
        assert result[:4] == b"%PDF"

    def test_caracteres_espanoles(self):
        report = _make_report()
        report.case_summary.narrative = (
            "Paciente con neuropatía periférica, pérdida de sensación y "
            "déficit motor en miembros inferiores. Síntomas de evolución lenta."
        )
        result = generate_pdf(report)
        assert result[:4] == b"%PDF"


# ── Tests: saneo de caracteres ────────────────────────────────────────────────

class TestLimpiezaDeCaracteres:
    """
    Las fuentes estándar de ReportLab usan WinAnsi y dibujan cualquier letra
    en lugar de los caracteres que no conocen. Los LLM devuelven el guion no
    separable a montones: sin traducir, "sensitivo‑motora" salía
    "sensitivonmotora" en el PDF entregado al médico.
    """

    def test_traduce_el_guion_no_separable(self):
        assert _limpiar("sensitivo‑motora") == "sensitivo-motora"

    def test_traduce_rayas_y_comillas_tipograficas(self):
        assert _limpiar("10–30 ‘x’ “y”") == "10-30 'x' \"y\""

    def test_traduce_espacios_especiales_y_simbolos(self):
        assert _limpiar("HbA1c ≥8×2") == "HbA1c >=8x2"

    def test_no_toca_los_acentos_del_espanol(self):
        texto = "Neuropatía axonal sensitivomotora, evolución de 18 meses."
        assert _limpiar(texto) == texto

    def test_el_pdf_no_arrastra_caracteres_no_dibujables(self):
        report = _make_report()
        report.case_summary.narrative = "Neuropatía sensitivo‑motora ≥ 18 meses."
        assert generate_pdf(report)[:4] == b"%PDF"


# ── Tests: modo mock en el PDF (control de costos, S4 — task 6.4) ────────────

class TestModoMockEnPdf:
    """
    Un reporte de modo mock MUST ser distinguible sin inspeccionar código ni
    logs (spec `modo-mock-pipeline`): la advertencia tiene que estar en el
    texto extraído del PDF, con la misma visibilidad que la del consenso de
    IA o la de verificación bibliográfica.
    """

    def _reporte_mock(self) -> StructuredReport:
        report = _make_report()
        return report.model_copy(
            update={"metadata": report.metadata.model_copy(update={"mock": True})}
        )

    def test_el_pdf_declara_el_modo_mock(self):
        texto = _texto_del_pdf(generate_pdf(self._reporte_mock()))
        assert "mock" in texto.lower()

    def test_un_reporte_real_no_menciona_el_modo_mock(self):
        texto = _texto_del_pdf(generate_pdf(_make_report()))
        assert "modo mock" not in texto.lower()


# ── Tests: verificación bibliográfica en el PDF ───────────────────────────────

class TestVerificacionEnPdf:
    def _report_verificado(self) -> StructuredReport:
        discordante = Source(
            pmid="22439958",
            title="Metformin-associated vitamin B12 deficiency",
            journal="Diabetes Care",
            year=2012,
            verified=False,
            verification_status="discordante",
            actual_title="Breeding replacement gilts for organic pig herds.",
        )
        h = RankedHypothesis(
            rank=1,
            text="Deficiencia de B12 por metformina.",
            priority="HIGH",
            evidence_level="I",
            rationale="Razonamiento.",
            supporting_agents=["Consultor Clínico"],
            sources=[discordante],
            status="especulativa",
            verified_sources=0,
        )
        report = _make_report(hypotheses=[h])
        report.bibliography = [discordante]
        report.verification = VerificationSummary(
            total_fuentes=1, verificadas=0, discordantes=1,
            hipotesis_respaldadas=0, hipotesis_especulativas=1,
        )
        return report

    def test_genera_pdf_valido_con_verificacion(self):
        assert generate_pdf(self._report_verificado())[:4] == b"%PDF"

    def test_el_pdf_avisa_de_las_referencias_no_confirmadas(self):
        texto = _texto_del_pdf(generate_pdf(self._report_verificado()))
        assert "Advertencia de verificación bibliográfica" in texto
        assert "Referencias verificadas en PubMed" in texto

    def test_marca_la_fuente_discordante_con_el_titulo_real(self):
        texto = _texto_del_pdf(generate_pdf(self._report_verificado()))
        assert "NO CORRESPONDE" in texto
        assert "En PubMed este PMID es:" in texto
        assert "Breeding replacement gilts" in texto

    def test_etiqueta_la_hipotesis_como_especulativa(self):
        assert "ESPECULATIVA" in _texto_del_pdf(generate_pdf(self._report_verificado()))

    def test_sin_verificacion_el_pdf_sigue_saliendo(self):
        """Compatibilidad: un reporte viejo, sin la sección, no rompe el export."""
        report = _make_report()
        report.verification = VerificationSummary()
        texto = _texto_del_pdf(generate_pdf(report))
        assert "Advertencia de verificación bibliográfica" not in texto


# ── Tests: priorización por evidencia EBM en el PDF ───────────────────────────

class TestPriorizacionEnPdf:
    def _report_priorizado(self) -> StructuredReport:
        verificada = Source(
            pmid="30000002", title="Metformin use and B12 deficiency: a cohort",
            verified=True, verification_status="verificada",
            publication_types=["Journal Article", "Observational Study"],
        )
        respaldada = RankedHypothesis(
            rank=1, text="Déficit de B12 por metformina.", priority="HIGH",
            evidence_level="II", declared_evidence_level="I",
            evidence_note="El agente declaró nivel I; queda topeado en II.",
            rationale="Razonamiento.", supporting_agents=["Consultor Clínico"],
            sources=[verificada], status="respaldada", verified_sources=1,
        )
        pendiente = RankedHypothesis(
            rank=2, text="Polineuropatía desmielinizante inflamatoria crónica.", priority="MEDIUM",
            evidence_level="III", declared_evidence_level="II",
            evidence_note="Verificación bibliográfica no disponible.",
            rationale="Razonamiento.", supporting_agents=[],
            sources=[Source(pmid="30000003", title="CIDP", verification_status="no_verificable")],
            status="pendiente",
        )
        especulativa = RankedHypothesis(
            rank=3, text="Amiloidosis TTR hereditaria.", priority="HIGH",
            evidence_level="III", declared_evidence_level="III",
            rationale="Razonamiento.", supporting_agents=[], sources=[],
            status="especulativa",
        )
        report = _make_report(hypotheses=[respaldada, pendiente, especulativa])
        report.verification = VerificationSummary(
            total_fuentes=2, verificadas=1, no_verificables=1,
            hipotesis_respaldadas=1, hipotesis_pendientes=1, hipotesis_especulativas=1,
            hipotesis_topeadas=2,
        )
        return report

    def test_agrupa_por_estado_con_encabezados_en_orden(self):
        texto = _texto_del_pdf(generate_pdf(self._report_priorizado()))
        i_resp = texto.index("HIPÓTESIS RESPALDADAS (1)")
        i_pend = texto.index("PENDIENTES DE VERIFICACIÓN (1)")
        i_espe = texto.index("HIPÓTESIS ESPECULATIVAS (1)")
        assert i_resp < i_pend < i_espe

    def test_omite_grupos_vacios(self):
        report = self._report_priorizado()
        report.hypotheses = [report.hypotheses[0], report.hypotheses[2]]
        texto = _texto_del_pdf(generate_pdf(report))
        assert "PENDIENTES DE VERIFICACIÓN" not in texto
        assert "HIPÓTESIS ESPECULATIVAS (1)" in texto

    def test_etiqueta_pendiente(self):
        assert "PENDIENTE" in _texto_del_pdf(generate_pdf(self._report_priorizado()))

    def test_muestra_el_nivel_declarado_cuando_fue_topeado(self):
        texto = _texto_del_pdf(generate_pdf(self._report_priorizado()))
        assert "Evidencia II (declarado I)" in texto
        assert "queda topeado en II" in texto
        # La especulativa declaró III y quedó en III: no muestra "declarado".
        assert "(declarado III)" not in texto

    def test_portada_con_pendientes_y_topeadas(self):
        texto = _texto_del_pdf(generate_pdf(self._report_priorizado()))
        assert "Hipótesis pendientes de verificación" in texto
        assert "Hipótesis con nivel de evidencia topeado" in texto

    def test_fuente_verificada_muestra_su_tipo_de_publicacion(self):
        texto = _texto_del_pdf(generate_pdf(self._report_priorizado()))
        assert "Observational Study" in texto


# ── Tests: endpoint /api/report/pdf ───────────────────────────────────────────

class TestExportPdfEndpoint:
    """
    Desde Sprint 4 (`proteccion-analisis-clinico`), `/api/report/pdf` exige
    una sesión de médico `verificado`: usa la fixture `client_medico_verificado`
    de `tests/conftest.py` en vez de `TestClient(app)` directo.
    """

    def _report_json(self) -> dict:
        return _make_report().model_dump(mode="json")

    def test_endpoint_devuelve_200(self, client_medico_verificado):
        response = client_medico_verificado.post("/api/report/pdf", json=self._report_json())
        assert response.status_code == 200

    def test_content_type_es_pdf(self, client_medico_verificado):
        response = client_medico_verificado.post("/api/report/pdf", json=self._report_json())
        assert response.headers["content-type"] == "application/pdf"

    def test_content_disposition_tiene_filename(self, client_medico_verificado):
        response = client_medico_verificado.post("/api/report/pdf", json=self._report_json())
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "nexus_reporte" in cd
        assert ".pdf" in cd

    def test_body_es_pdf_valido(self, client_medico_verificado):
        response = client_medico_verificado.post("/api/report/pdf", json=self._report_json())
        assert response.content[:4] == b"%PDF"

    def test_reporte_previo_a_la_priorizacion_ebm_sigue_siendo_valido(self, client_medico_verificado):
        """Contrato aditivo: un JSON sin los campos nuevos se acepta y exporta."""
        viejo = self._report_json()
        for h in viejo["hypotheses"]:
            h.pop("declared_evidence_level", None)
            h.pop("evidence_note", None)
            for s in h["sources"]:
                s.pop("publication_types", None)
        for s in viejo["bibliography"]:
            s.pop("publication_types", None)
        viejo["verification"].pop("hipotesis_pendientes", None)
        viejo["verification"].pop("hipotesis_topeadas", None)

        StructuredReport.model_validate(viejo)
        response = client_medico_verificado.post("/api/report/pdf", json=viejo)
        assert response.status_code == 200
        assert response.content[:4] == b"%PDF"

    def test_body_invalido_devuelve_422(self, client_medico_verificado):
        response = client_medico_verificado.post("/api/report/pdf", json={"invalid": "data"})
        assert response.status_code == 422


# ── Tests: navegación de ensayos (Agente 05) ──────────────────────────────────

class TestEnsayosNavegados:
    def _trial_evaluado(self) -> ClinicalTrial:
        return ClinicalTrial(
            nct_id="NCT04000009",
            title="Ensayo de amiloidosis hereditaria",
            status="NOT_YET_RECRUITING",
            brief_summary="Ensayo sobre estabilizadores de transtiretina.",
            conditions=["Hereditary ATTR amyloidosis"],
            locations=["Argentina"],
            url="https://clinicaltrials.gov/study/NCT04000009",
            compatibility="alta",
            compatibility_rationale="La condición estudiada coincide con la hipótesis.",
            criteria_to_verify=["Confirmar biopsia de nervio", "Revisar función renal"],
            related_hypotheses=["Amiloidosis hereditaria por transtiretina"],
            matched_terms=["hereditary ATTR amyloidosis"],
        )

    def _report_navegado(self, **overrides) -> StructuredReport:
        report = _make_report(trials=[self._trial_evaluado()])
        report.rare_diseases = [
            RareDiseaseMatch(
                orpha_code="271861",
                name="Hereditary ATTR amyloidosis",
                url="https://www.orpha.net/en/disease/detail/271861",
                hypothesis="Amiloidosis hereditaria por transtiretina",
                matched_term="hereditary ATTR amyloidosis",
            )
        ]
        datos = dict(
            estado_clinicaltrials="ok",
            estado_orphanet="ok",
            planificacion="ok",
            evaluacion="ok",
            terminos_consultados=["hereditary ATTR amyloidosis"],
            encontrados=1,
        )
        datos.update(overrides)
        report.trial_search = TrialSearchSummary(**datos)
        return report

    def test_pdf_con_ensayos_evaluados(self):
        texto = _texto_del_pdf(generate_pdf(self._report_navegado()))
        assert "COMPATIBILIDAD ALTA" in texto
        assert "Confirmar biopsia de nervio" in texto
        assert "ORPHA:271861" in texto
        assert "orpha.net" in texto
        assert "la elegibilidad la determina el equipo investigador" in texto

    def test_pdf_avisa_que_el_ensayo_no_recluta(self):
        texto = _texto_del_pdf(generate_pdf(self._report_navegado()))
        assert "AÚN NO RECLUTA" in texto

    def test_pdf_senala_la_sede_en_argentina(self):
        texto = _texto_del_pdf(generate_pdf(self._report_navegado()))
        assert "SEDE EN ARGENTINA" in texto

    def test_pdf_con_la_api_caida(self):
        report = _make_report()
        report.clinical_trials = []
        report.trial_search = TrialSearchSummary(estado_clinicaltrials="no_disponible")
        texto = _texto_del_pdf(generate_pdf(report))
        assert "No se pudo consultar ClinicalTrials.gov" in texto
        assert "No se encontraron ensayos clínicos activos relacionados." not in texto

    def test_pdf_avisa_cuando_orphanet_no_respondio(self):
        report = self._report_navegado(estado_orphanet="no_disponible")
        texto = _texto_del_pdf(generate_pdf(report))
        assert "Orphanet no se pudo consultar" in texto

    def test_reporte_previo_se_imprime_como_antes(self):
        """Sin `trial_search` no aparecen etiquetas de compatibilidad."""
        texto = _texto_del_pdf(generate_pdf(_make_report()))
        assert "COMPATIBILIDAD" not in texto
        assert "la elegibilidad la determina el equipo investigador" not in texto
        assert "NCT04000001" in texto

    def test_reporte_previo_sin_ensayos_mantiene_el_mensaje_original(self):
        report = _make_report()
        report.clinical_trials = []
        texto = _texto_del_pdf(generate_pdf(report))
        assert "No se encontraron ensayos clínicos activos relacionados." in texto

    def test_ensayo_sin_evaluar_se_rotula(self):
        report = self._report_navegado(evaluacion="fallback")
        report.clinical_trials[0].compatibility = "sin_evaluar"
        report.clinical_trials[0].compatibility_rationale = None
        texto = _texto_del_pdf(generate_pdf(report))
        assert "SIN EVALUAR" in texto
        assert "la evaluación de compatibilidad no se pudo completar" in texto


class TestPdfConArbitraje:
    """
    El PDF es lo que lee el médico: el consenso, sus objeciones y la aclaración
    de que lo produjo un panel de IA tienen que estar ahí (tarea 9.4).
    """

    @staticmethod
    def _reporte_con_arbitraje() -> StructuredReport:
        from backend.api.schemas import ArbitrationOut, ContradictionOut, RecitationOut

        reporte = _make_report()
        h = reporte.hypotheses[0]
        h.arbiter_note = "Sostenida por dos agentes, con una objeción abierta."
        h.refuting_agents = ["Consultor Clínico"]
        h.contradictions = [ContradictionOut(
            from_agent_name="Consultor Clínico", severity="HIGH",
            critique_text="Sin biopsia no se sostiene.",
        )]
        h.recitation = "mejorada"
        reporte.arbitration = ArbitrationOut(
            status="ok", input_hypotheses=9, consensus_hypotheses=4, contradictions=1,
            cited_sources=15, rag_overlap=0, retrieved_articles=5,
            recitation=RecitationOut(executed=True, recited=3, improved=1, rejected_pmids=2),
        )
        return reporte

    def test_genera_pdf_valido(self):
        pdf = generate_pdf(self._reporte_con_arbitraje())
        assert pdf.startswith(b"%PDF")

    def test_la_portada_informa_la_consolidacion(self):
        texto = _texto_del_pdf(generate_pdf(self._reporte_con_arbitraje()))
        assert "consolidadas por el Árbitro" in texto
        assert "9" in texto and "4" in texto

    def test_la_portada_informa_el_solapamiento_con_el_rag(self):
        """El dato que justifica que el Árbitro exista."""
        texto = _texto_del_pdf(generate_pdf(self._reporte_con_arbitraje()))
        assert "literatura recuperada" in texto

    def test_la_portada_aclara_que_el_consenso_es_entre_agentes_de_ia(self):
        # El salto de línea del PDF cae en cualquier lado: se normaliza antes
        # de afirmar sobre la frase.
        texto = " ".join(_texto_del_pdf(generate_pdf(self._reporte_con_arbitraje())).split())
        assert "panel de agentes de inteligencia artificial" in texto
        assert "No constituyen un diagnóstico ni una recomendación clínica" in texto

    def test_el_veredicto_y_la_objecion_van_junto_a_la_hipotesis(self):
        texto = _texto_del_pdf(generate_pdf(self._reporte_con_arbitraje()))
        assert "Veredicto del Árbitro" in texto
        assert "Objetada por" in texto
        assert "Sin biopsia no se sostiene" in texto

    def test_la_marca_de_recitada_aparece(self):
        texto = _texto_del_pdf(generate_pdf(self._reporte_con_arbitraje()))
        assert "Recitada" in texto

    def test_reporte_sin_arbitraje_sigue_generando(self):
        """No regresión: un reporte anterior al Árbitro exporta igual."""
        reporte = _make_report()
        assert reporte.arbitration is None
        texto = _texto_del_pdf(generate_pdf(reporte))
        assert "Veredicto del Árbitro" not in texto
        assert "NEXUS" in texto

    def test_arbitraje_degradado_lo_dice_en_la_portada(self):
        from backend.api.schemas import ArbitrationOut

        reporte = _make_report()
        reporte.arbitration = ArbitrationOut(
            status="degradado", input_hypotheses=9, consensus_hypotheses=9,
        )
        texto = _texto_del_pdf(generate_pdf(reporte))
        assert "Arbitraje no disponible" in texto


class TestCaracteresNoSoportados:
    """
    Helvetica no tiene flechas ni varios signos tipográficos. Sin sanear, ReportLab
    dibuja un glifo equivocado en el documento que lee el médico.

    Salió preparando la evidencia de la tarjeta #52: la portada mostraba un
    glifo de ligadura donde debía decir la flecha de consolidación.
    """

    def test_la_flecha_no_llega_cruda_al_pdf(self):
        from backend.api.schemas import ArbitrationOut

        reporte = _make_report()
        reporte.arbitration = ArbitrationOut(
            status="ok", input_hypotheses=14, consensus_hypotheses=7,
        )
        texto = _texto_del_pdf(generate_pdf(reporte))

        assert "→" not in texto
        assert "de 14 a 7" in " ".join(texto.split())

    def test_la_tabla_de_sustituciones_cubre_las_flechas(self):
        from backend.pipeline.pdf_exporter import _limpiar

        assert _limpiar("14 → 7") == "14 -> 7"
        assert _limpiar("a ← b") == "a <- b"

    def test_el_texto_de_una_hipotesis_se_sanea(self):
        """
        Los títulos de PubMed traen guiones largos, comillas tipográficas y
        signos matemáticos. El texto que pasa por `_par()` se sanea.

        El em-dash y las comillas sí existen en Helvetica, así que no se rompen;
        la sustitución es defensa en profundidad. La flecha es el caso que
        genuinamente no tiene glifo, y lo cubre el test de arriba.
        """
        reporte = _make_report()
        reporte.hypotheses[0].text = (
            "Amiloidosis ATTR \u2014 variante \u201cVal30Met\u201d con seguimiento \u2265 24 meses"
        )
        texto = " ".join(_texto_del_pdf(generate_pdf(reporte)).split())

        assert "Amiloidosis ATTR - variante \"Val30Met\" con seguimiento >= 24 meses" in texto


def test_resumen_ejecutivo_en_pdf_solo_si_existe():
    from backend.pipeline import pdf_exporter
    from tests.test_agent_06_synthesizer import _report

    r = _report()
    s = pdf_exporter._styles()
    assert pdf_exporter._executive_summary(r, s) == []
    r.executive_summary = "Resumen de prueba."
    assert len(pdf_exporter._executive_summary(r, s)) > 1
    assert pdf_exporter.generate_pdf(r)[:4] == b"%PDF"


class TestResumenEjecutivoLiteral:
    """El resumen es prosa libre del LLM: se dibuja como texto, nunca como marcado."""

    def _pdf_con_resumen(self, resumen: str) -> str:
        report = _make_report()
        report.executive_summary = resumen
        return _texto_del_pdf(generate_pdf(report))

    def test_menor_y_mayor_sin_etiqueta_no_rompen(self):
        texto = self._pdf_con_resumen("Si a<b y c>d entonces la hipótesis se sostiene.")
        assert "a<b y c>d" in texto

    def test_ampersand_se_muestra_literal(self):
        assert "B12 & folato" in self._pdf_con_resumen("Déficit de B12 & folato.")

    def test_el_marcado_se_muestra_como_texto(self):
        texto = self._pdf_con_resumen("Ver <font size=40>grande</font> y </b> suelto.")
        assert "<font size=40>grande</font>" in texto
        assert "</b>" in texto


# ── Todo texto libre se dibuja como texto literal ─────────────────────────────

_HOSTIL = "a<b & c>d </b> <font size=40>x</font>"
_HOSTIL_VISIBLE = "a<b & c>d </b> <font size=40>x</font>"


def _reporte_hostil() -> StructuredReport:
    """Reporte con marcado hostil en cada campo de texto libre que llega a un Paragraph."""
    from backend.api.schemas import ContradictionOut

    h = RankedHypothesis(
        rank=1, text=f"HTEXT {_HOSTIL}", priority="HIGH", evidence_level="II",
        rationale=f"HRAT {_HOSTIL}", supporting_agents=[f"AGSUP {_HOSTIL}"],
        sources=[Source(
            pmid="12345678", title=f"STITLE {_HOSTIL}", journal=f"SJOUR {_HOSTIL}", year=2022,
            verified=True, verification_status="discordante",
            actual_title=f"SACT {_HOSTIL}", publication_types=[f"SPUB {_HOSTIL}"],
        )],
        status="respaldada", evidence_note=f"HEVN {_HOSTIL}", arbiter_note=f"HARB {_HOSTIL}",
        refuting_agents=[f"HREF {_HOSTIL}"],
        contradictions=[ContradictionOut(
            from_agent_name=f"CNAME {_HOSTIL}", severity="HIGH",
            critique_text=f"CTEXT {_HOSTIL}",
        )],
    )
    trial = ClinicalTrial(
        nct_id="NCT04000001", title=f"TTITLE {_HOSTIL}", status="RECRUITING",
        brief_summary="x", conditions=[f"TCOND {_HOSTIL}"], phase="PHASE3",
        locations=[f"TLOC {_HOSTIL}"], min_age="18 <Years>", max_age="70 &Years",
        url="https://ct.gov/study?a=1&b=2&c=<x>",
        compatibility="alta", compatibility_rationale=f"TRAT {_HOSTIL}",
        criteria_to_verify=[f"TCRIT {_HOSTIL}"], related_hypotheses=[f"TREL {_HOSTIL}"],
    )
    r = _make_report(
        hypotheses=[h], trials=[trial],
        bibliography=[Source(pmid="12345678", title=f"BTITLE {_HOSTIL}", journal="J", year=2020)],
        divergences=[f"DIV {_HOSTIL}"],
    )
    r.case_summary.narrative = f"NARR {_HOSTIL}"
    r.metadata.nexus_version = "0.3<0>&"
    r.metadata.disclaimer = f"DISC {_HOSTIL}"
    r.executive_summary = f"EXEC {_HOSTIL}"
    r.trial_search = TrialSearchSummary()
    r.rare_diseases = [RareDiseaseMatch(
        orpha_code="1", name=f"RNAME {_HOSTIL}", url="https://orpha.net/?a=1&b=<2>",
        hypothesis=f"RHYP {_HOSTIL}", matched_term="t",
    )]
    return r


@pytest.mark.parametrize("marca", [
    "HTEXT", "HRAT", "AGSUP", "STITLE", "SJOUR", "SACT", "SPUB", "HEVN", "HARB", "HREF",
    "CNAME", "CTEXT", "TTITLE", "TCOND", "TLOC", "TRAT", "TCRIT", "TREL", "DIV", "NARR",
    "DISC", "EXEC", "BTITLE", "RNAME", "RHYP",
])
def test_texto_libre_se_dibuja_literal(marca):
    texto = " ".join(_texto_del_pdf(generate_pdf(_reporte_hostil())).split())
    assert f"{marca} {_HOSTIL_VISIBLE}" in texto


def test_urls_con_ampersand_y_angulares_no_rompen():
    texto = " ".join(_texto_del_pdf(generate_pdf(_reporte_hostil())).split())
    assert "URL: https://ct.gov/study?a=1&b=2&c=<x>" in texto
    assert "https://orpha.net/?a=1&b=<2>" in texto


def test_campos_cortos_con_marcado_no_rompen_y_se_ven_literales():
    texto = " ".join(_texto_del_pdf(generate_pdf(_reporte_hostil())).split())
    assert "Versión 0.3<0>&" in texto
    assert "18 <Years>" in texto and "70 &Years" in texto


def test_menor_o_igual_traducido_no_se_vuelve_marcado():
    r = _make_report()
    r.hypotheses[0].text = "Seguimiento ≤ 24 meses y ≥ 12"
    texto = " ".join(_texto_del_pdf(generate_pdf(r)).split())
    assert "Seguimiento <= 24 meses y >= 12" in texto


def test_el_marcado_propio_del_exportador_sigue_funcionando():
    texto = _texto_del_pdf(generate_pdf(_reporte_hostil()))
    assert "<b>" not in texto and "<font color" not in texto
    assert "Narrativa clínica:" in texto and "NO CORRESPONDE" in texto
    assert "Justificación:" in texto and "Veredicto del Árbitro:" in texto
