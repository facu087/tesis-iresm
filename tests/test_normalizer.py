"""
Tests del módulo de normalización terminológica (backend/ingestion/normalizer.py).
No llaman APIs externas.
"""

import pytest
from backend.ingestion.normalizer import normalize, normalize_inn, normalize_units


# ── Unidades de medida ─────────────────────────────────────────────────────────

class TestNormalizeUnits:
    def test_mg_dl_minusculas(self):
        assert normalize_units("glucosa 95 mg/dl") == "glucosa 95 mg/dL"

    def test_mg_dl_mayusculas(self):
        assert normalize_units("glucosa 95 MG/DL") == "glucosa 95 mg/dL"

    def test_mg_dl_con_espacio(self):
        assert normalize_units("glucosa 95 mg / dl") == "glucosa 95 mg/dL"

    def test_g_dl(self):
        assert normalize_units("hemoglobina 12.5 g/dl") == "hemoglobina 12.5 g/dL"

    def test_mmhg_sin_espacio(self):
        assert normalize_units("TA 120/80 mmhg") == "TA 120/80 mmHg"

    def test_mmhg_con_espacio(self):
        assert normalize_units("TA 120/80 mm Hg") == "TA 120/80 mmHg"

    def test_mcg_a_microgramo(self):
        assert normalize_units("vitamina B12 350 mcg") == "vitamina B12 350 μg"

    def test_ug_a_microgramo(self):
        assert normalize_units("dosis 50 ug") == "dosis 50 μg"

    def test_micro_u00b5_a_micro_u03bc(self):
        # µ (U+00B5 MICRO SIGN) → μ (U+03BC GREEK SMALL LETTER MU)
        assert normalize_units("dosis 50 µg") == "dosis 50 μg"

    def test_meq_l_minusculas(self):
        assert normalize_units("potasio 4.2 meq/l") == "potasio 4.2 mEq/L"

    def test_iu_a_ui(self):
        assert normalize_units("vitamina D 1000 IU") == "vitamina D 1000 UI"

    def test_ng_ml(self):
        assert normalize_units("PSA 3.5 ng/ml") == "PSA 3.5 ng/mL"

    def test_temperatura_celsius(self):
        assert normalize_units("temperatura 37 °c") == "temperatura 37 °C"

    def test_texto_sin_unidades_sin_cambios(self):
        original = "Paciente sin antecedentes relevantes."
        assert normalize_units(original) == original

    def test_multiples_unidades_en_un_texto(self):
        text = "glucosa 100 mg/dl, hemoglobina 13 g/dl, TA 130/85 mm hg"
        result = normalize_units(text)
        assert "mg/dL" in result
        assert "g/dL" in result
        assert "mmHg" in result


# ── Nombres INN ────────────────────────────────────────────────────────────────

class TestNormalizeInn:
    def test_lyrica_a_pregabalina(self):
        assert normalize_inn("Toma Lyrica 75mg.") == "Toma pregabalina 75mg."

    def test_neurontin_a_gabapentina(self):
        assert normalize_inn("tratado con Neurontin") == "tratado con gabapentina"

    def test_case_insensitive(self):
        assert normalize_inn("LYRICA") == "pregabalina"
        assert normalize_inn("lyrica") == "pregabalina"
        assert normalize_inn("Lyrica") == "pregabalina"

    def test_aspirina_a_inn(self):
        result = normalize_inn("indicado Aspirina 100mg")
        assert "ácido acetilsalicílico" in result

    def test_cymbalta_a_duloxetina(self):
        assert normalize_inn("Cymbalta 60mg/día") == "duloxetina 60mg/día"

    def test_voltaren_a_diclofenaco(self):
        assert normalize_inn("aplicó Voltaren gel") == "aplicó diclofenaco gel"

    def test_medrol_a_metilprednisolona(self):
        assert normalize_inn("pulso de Medrol 1g") == "pulso de metilprednisolona 1g"

    def test_marca_dentro_de_palabra_no_reemplaza(self):
        # "Lyrica" no debe matchear dentro de "Lyricamento" (no es una marca)
        result = normalize_inn("Lyricamento es una palabra inventada")
        assert "Lyricamento" in result

    def test_inn_ya_normalizado_sin_doble_reemplazo(self):
        # Si el texto ya tiene el INN, no debe cambiar
        original = "tratamiento con pregabalina 75mg"
        assert normalize_inn(original) == original

    def test_multiples_marcas(self):
        text = "Neurontin 300mg y Lyrica 75mg y Cymbalta 60mg"
        result = normalize_inn(text)
        assert "gabapentina" in result
        assert "pregabalina" in result
        assert "duloxetina" in result


# ── normalize() — función principal ───────────────────────────────────────────

class TestNormalize:
    def test_aplica_unidades_e_inn(self):
        text = "Lyrica 75mg, glucosa 100 mg/dl"
        result = normalize(text)
        assert "pregabalina" in result
        assert "mg/dL" in result

    def test_texto_vacio(self):
        assert normalize("") == ""

    def test_caso_clinico_base(self):
        texto = (
            "Paciente de 42 años con neuropatía axonal. "
            "Tratado con Lyrica 150mg/día y Cymbalta 60mg. "
            "Glucosa 98 mg/dl, hemoglobina 14.2 g/dl. TA 110/70 mm hg."
        )
        result = normalize(texto)
        assert "pregabalina" in result
        assert "duloxetina" in result
        assert "mg/dL" in result
        assert "g/dL" in result
        assert "mmHg" in result
