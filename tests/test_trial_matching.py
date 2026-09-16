"""
Tests de la lógica determinista del Agente 05 (backend/pipeline/trial_matching.py)
y del contrato aditivo de los modelos de ensayos (backend/models/trial.py).

Ningún test toca la red: todo lo que puede excluir un ensayo es determinista.
"""

from backend.models.biomarkers import BiomarkerProfile
from backend.models.case import ClinicalCase, PICOSynthesis
from backend.models.hypothesis import EvidenceLevel, Hypothesis, Priority
from backend.models.trial import (
    ClinicalTrial,
    Compatibility,
    PatientDemographics,
    TrialNavigationResult,
)
from backend.pipeline.trial_matching import (
    MAX_TRIALS,
    TrialHit,
    apply_hard_filters,
    build_navigation_input,
    merge_trials,
    names_match,
    normalize_disease_name,
    parse_patient_demographics,
    parse_trial_age,
    sanitize_term,
    sanitize_terms,
    select_candidates,
    sort_trials,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

_PERFIL_BASE = "Paciente masculino de 42 años con DM2 de 10 años de evolución"


def _hypothesis(
    text: str = "Hipótesis de prueba.",
    priority: Priority = Priority.HIGH,
    evidence_level: EvidenceLevel = EvidenceLevel.II,
) -> Hypothesis:
    return Hypothesis(
        text=text,
        priority=priority,
        evidence_level=evidence_level,
        rationale="Razonamiento de prueba.",
    )


def _pico(**overrides) -> PICOSynthesis:
    datos = dict(
        patient_profile=_PERFIL_BASE,
        chief_complaint="neuropatía axonal sensitivomotora",
        condition_en="axonal sensorimotor polyneuropathy",
        relevant_history=["diabetes tipo 2"],
        negative_findings=["anti-Hu negativo"],
        disease_duration="2 años",
        current_treatments=["pregabalina"],
        procedures_done=["EMG"],
        comparison="No aplica",
        primary_outcome="identificar causa tratable",
        secondary_outcomes=[],
        biomarkers=[],
        genetic_findings=["variante TTR"],
        clinical_narrative="NARRATIVA CONFIDENCIAL del caso completo.",
    )
    datos.update(overrides)
    return PICOSynthesis(**datos)


def _case(**overrides) -> ClinicalCase:
    case = ClinicalCase(raw_text="TEXTO CRUDO del informe original.")
    case.pico = _pico(**overrides)
    case.biomarkers = BiomarkerProfile(
        genes=["TTR", "PMP22"],
        antibodies=["anti-gangliósido GM1"],
        drugs=["pregabalina"],
    )
    return case


def _trial(
    nct_id: str = "NCT04000001",
    status: str = "RECRUITING",
    min_age: str | None = "18 Years",
    max_age: str | None = "70 Years",
    sex: str | None = "ALL",
    locations: list[str] | None = None,
    compatibility: str = Compatibility.SIN_EVALUAR.value,
) -> ClinicalTrial:
    return ClinicalTrial(
        nct_id=nct_id,
        title=f"Ensayo {nct_id}",
        status=status,
        brief_summary="Resumen del ensayo.",
        min_age=min_age,
        max_age=max_age,
        sex=sex,
        locations=locations if locations is not None else ["United States"],
        compatibility=compatibility,
    )


# ── Contrato aditivo de los modelos ────────────────────────────────────────────

class TestContratoAditivo:
    def test_json_previo_valida_y_queda_sin_evaluar(self):
        """Un ensayo serializado antes del Agente 05 no tiene los campos nuevos."""
        previo = {
            "nct_id": "NCT04000001",
            "title": "Estudio de neuropatía axonal hereditaria",
            "status": "RECRUITING",
            "brief_summary": "Ensayo sobre tratamiento.",
            "conditions": ["Axonal Neuropathy"],
            "phase": "PHASE3",
            "locations": ["Argentina"],
            "url": "https://clinicaltrials.gov/study/NCT04000001",
        }
        trial = ClinicalTrial(**previo)
        assert trial.compatibility == "sin_evaluar"
        assert trial.compatibility_rationale is None
        assert trial.criteria_to_verify == []
        assert trial.related_hypotheses == []
        assert trial.matched_terms == []

    def test_resultado_de_navegacion_vacio_tiene_defaults(self):
        resultado = TrialNavigationResult()
        assert resultado.trials == []
        assert resultado.rare_diseases == []
        assert resultado.summary.estado_clinicaltrials == "sin_consulta"
        assert resultado.summary.estado_orphanet == "sin_consulta"


# ── 3.1 Entrada independiente del origen de las hipótesis ──────────────────────

class TestSeleccionDeCandidatas:
    def test_toma_las_tres_primeras_por_prioridad_y_evidencia(self):
        hipotesis = [
            _hypothesis("Baja", Priority.LOW, EvidenceLevel.I),
            _hypothesis("Media", Priority.MEDIUM, EvidenceLevel.III),
            _hypothesis("Alta III", Priority.HIGH, EvidenceLevel.III),
            _hypothesis("Alta I", Priority.HIGH, EvidenceLevel.I),
            _hypothesis("Alta II", Priority.HIGH, EvidenceLevel.II),
        ]
        candidatas = select_candidates(hipotesis)
        assert [c.text for c in candidatas] == ["Alta I", "Alta II", "Alta III"]

    def test_excluye_las_descartadas_por_el_arbitro(self):
        hipotesis = [
            _hypothesis("Descartada"),
            _hypothesis("Vigente A"),
            _hypothesis("Vigente B"),
        ]
        candidatas = select_candidates(hipotesis, {"Descartada": "descartada"})
        assert [c.text for c in candidatas] == ["Vigente A", "Vigente B"]

    def test_conserva_el_estado_cuando_lo_hay(self):
        candidatas = select_candidates(
            [_hypothesis("Con estado")], {"Con estado": "respaldada"}
        )
        assert candidatas[0].status == "respaldada"

    def test_hipotesis_del_debate_no_traen_estado(self):
        candidatas = select_candidates([_hypothesis("Sin estado")])
        assert candidatas[0].status is None

    def test_no_repite_textos_identicos(self):
        candidatas = select_candidates([_hypothesis("Igual"), _hypothesis("Igual")])
        assert len(candidatas) == 1

    def test_lista_vacia_no_deja_candidatas(self):
        assert select_candidates([]) == []

    def test_todas_descartadas_no_deja_candidatas(self):
        hipotesis = [_hypothesis("Una"), _hypothesis("Otra")]
        estados = {"Una": "descartada", "Otra": "descartada"}
        assert select_candidates(hipotesis, estados) == []


class TestBuildNavigationInput:
    def test_no_filtra_el_texto_crudo_ni_la_narrativa(self):
        entrada = build_navigation_input(_case(), [_hypothesis()])
        serializado = entrada.model_dump_json()
        assert "TEXTO CRUDO" not in serializado
        assert "NARRATIVA CONFIDENCIAL" not in serializado

    def test_usa_condition_en_y_no_el_motivo_en_espanol(self):
        entrada = build_navigation_input(_case(), [_hypothesis()])
        assert entrada.condition_en == "axonal sensorimotor polyneuropathy"
        assert "neuropatía" not in entrada.condition_en

    def test_sanea_los_biomarcadores(self):
        entrada = build_navigation_input(_case(), [_hypothesis()])
        assert "TTR" in entrada.biomarker_terms
        assert "PMP22" in entrada.biomarker_terms
        assert all("gangli" not in t for t in entrada.biomarker_terms)

    def test_deduce_la_demografia_del_perfil(self):
        entrada = build_navigation_input(_case(), [_hypothesis()])
        assert entrada.demographics.age_years == 42.0
        assert entrada.demographics.sex == "MALE"

    def test_perfil_de_elegibilidad_usa_campos_pico(self):
        entrada = build_navigation_input(_case(), [_hypothesis()])
        assert "pregabalina" in entrada.eligibility_profile
        assert "diabetes tipo 2" in entrada.eligibility_profile

    def test_caso_sin_pico_no_rompe(self):
        case = ClinicalCase(raw_text="texto sin PICO")
        entrada = build_navigation_input(case, [_hypothesis()])
        assert entrada.condition_en == ""
        assert entrada.eligibility_profile == ""
        assert len(entrada.candidates) == 1

    def test_condition_en_con_datos_demograficos_se_descarta(self):
        entrada = build_navigation_input(
            _case(condition_en="42-year-old male neuropathy"), [_hypothesis()]
        )
        assert entrada.condition_en == ""


# ── 3.2 Saneamiento de términos ────────────────────────────────────────────────

class TestSanitizeTerm:
    def test_acepta_genes(self):
        assert sanitize_term("TTR") == "TTR"
        assert sanitize_term("PMP22") == "PMP22"

    def test_acepta_condicion_en_ingles(self):
        assert sanitize_term("hereditary ATTR amyloidosis") == "hereditary ATTR amyloidosis"

    def test_descarta_datos_demograficos(self):
        assert sanitize_term("42-year-old male neuropathy") is None

    def test_descarta_la_palabra_patient(self):
        assert sanitize_term("patient with neuropathy") is None

    def test_descarta_terminos_con_tildes(self):
        assert sanitize_term("anti-gangliósido GM1") is None

    def test_descarta_mas_de_ochenta_caracteres(self):
        assert sanitize_term("a" * 81) is None

    def test_descarta_mas_de_ocho_palabras(self):
        assert sanitize_term("one two three four five six seven eight nine") is None

    def test_descarta_termino_de_un_caracter(self):
        assert sanitize_term("a") is None

    def test_descarta_vacio(self):
        assert sanitize_term("") is None
        assert sanitize_term("   ") is None

    def test_sanitize_terms_conserva_orden_y_quita_duplicados(self):
        assert sanitize_terms(["TTR", "anti-gangliósido GM1", "TTR", "PMP22"]) == [
            "TTR",
            "PMP22",
        ]

    def test_sanitize_terms_respeta_el_limite(self):
        assert sanitize_terms(["A1", "B2", "C3"], limit=2) == ["A1", "B2"]


# ── 3.3 Demografía ─────────────────────────────────────────────────────────────

class TestParsePatientDemographics:
    def test_perfil_del_caso_base(self):
        demografia = parse_patient_demographics(_PERFIL_BASE)
        assert demografia.age_years == 42.0
        assert demografia.sex == "MALE"

    def test_no_confunde_el_tiempo_de_evolucion_con_la_edad(self):
        demografia = parse_patient_demographics(
            "Paciente con DM2 de 10 años de evolución, 42 años de edad"
        )
        assert demografia.age_years == 42.0

    def test_formato_varon_con_coma(self):
        demografia = parse_patient_demographics("Varón, 42 años")
        assert demografia.age_years == 42.0
        assert demografia.sex == "MALE"

    def test_formato_edad_explicita(self):
        demografia = parse_patient_demographics("Edad: 63. Antecedentes varios.")
        assert demografia.age_years == 63.0

    def test_perfil_femenino(self):
        demografia = parse_patient_demographics("Mujer de 35 años con polineuropatía")
        assert demografia.sex == "FEMALE"

    def test_perfil_sin_sexo_identificable(self):
        demografia = parse_patient_demographics("Persona adulta de 50 años de edad")
        assert demografia.sex is None

    def test_perfil_ambiguo_no_define_sexo(self):
        demografia = parse_patient_demographics(
            "Paciente masculino; antecedente familiar en una mujer de la familia"
        )
        assert demografia.sex is None

    def test_perfil_vacio(self):
        demografia = parse_patient_demographics("")
        assert demografia.age_years is None
        assert demografia.sex is None

    def test_edad_imposible_se_descarta(self):
        demografia = parse_patient_demographics("Paciente masculino de 480 años")
        assert demografia.age_years is None


class TestParseTrialAge:
    def test_anios(self):
        assert parse_trial_age("18 Years") == 18.0

    def test_meses(self):
        assert parse_trial_age("6 Months") == 0.5

    def test_semanas(self):
        assert parse_trial_age("52 Weeks") is not None

    def test_na_devuelve_none(self):
        assert parse_trial_age("N/A") is None

    def test_none_devuelve_none(self):
        assert parse_trial_age(None) is None

    def test_formato_desconocido_devuelve_none(self):
        assert parse_trial_age("adulto") is None
        assert parse_trial_age("18 Parsecs") is None


# ── 3.4 Filtros duros ──────────────────────────────────────────────────────────

class TestFiltrosDuros:
    def test_paciente_fuera_del_rango_etario(self):
        demografia = PatientDemographics(age_years=42.0, sex="MALE")
        trials, conteo = apply_hard_filters(
            [_trial(min_age="18 Years", max_age="40 Years")], demografia
        )
        assert trials == []
        assert conteo.por_edad == 1

    def test_paciente_por_debajo_del_minimo(self):
        demografia = PatientDemographics(age_years=12.0)
        trials, conteo = apply_hard_filters([_trial(min_age="18 Years")], demografia)
        assert trials == []
        assert conteo.por_edad == 1

    def test_ensayo_sin_edad_maxima_se_conserva(self):
        demografia = PatientDemographics(age_years=42.0)
        trials, conteo = apply_hard_filters(
            [_trial(min_age="18 Years", max_age=None)], demografia
        )
        assert len(trials) == 1
        assert conteo.por_edad == 0

    def test_sexo_incompatible(self):
        demografia = PatientDemographics(age_years=42.0, sex="MALE")
        trials, conteo = apply_hard_filters([_trial(sex="FEMALE")], demografia)
        assert trials == []
        assert conteo.por_sexo == 1

    def test_sexo_all_nunca_excluye(self):
        demografia = PatientDemographics(sex="MALE")
        trials, _ = apply_hard_filters([_trial(sex="ALL")], demografia)
        assert len(trials) == 1

    def test_perfil_sin_sexo_no_excluye(self):
        demografia = PatientDemographics(age_years=42.0, sex=None)
        trials, conteo = apply_hard_filters([_trial(sex="FEMALE")], demografia)
        assert len(trials) == 1
        assert conteo.por_sexo == 0

    def test_perfil_sin_edad_no_excluye(self):
        demografia = PatientDemographics(age_years=None, sex="MALE")
        trials, conteo = apply_hard_filters(
            [_trial(min_age="65 Years", max_age="80 Years")], demografia
        )
        assert len(trials) == 1
        assert conteo.por_edad == 0

    def test_rango_ilegible_no_excluye(self):
        demografia = PatientDemographics(age_years=42.0)
        trials, conteo = apply_hard_filters([_trial(min_age="N/A", max_age="N/A")], demografia)
        assert len(trials) == 1
        assert conteo.por_edad == 0


# ── 3.5 Coincidencia con Orphanet ──────────────────────────────────────────────

class TestCoincidenciaOrphanet:
    def test_coincide_sin_importar_el_orden_de_las_palabras(self):
        assert names_match("ATTR amyloidosis, hereditary", "Hereditary ATTR amyloidosis")

    def test_coincide_con_un_sinonimo(self):
        assert names_match("hereditary ATTR amyloidosis", "Hereditary ATTR amyloidosis")

    def test_no_coincide_por_inclusion_de_palabras(self):
        assert not names_match(
            "axonal sensorimotor polyneuropathy",
            "Autosomal recessive lethal neonatal axonal sensorimotor polyneuropathy",
        )

    def test_termino_vacio_no_coincide(self):
        assert not names_match("", "Hereditary ATTR amyloidosis")

    def test_normalizacion_ignora_puntuacion_y_guiones(self):
        assert normalize_disease_name("Charcot-Marie-Tooth disease") == (
            normalize_disease_name("charcot marie tooth, disease")
        )


# ── 3.6 Unificación por NCT ID ─────────────────────────────────────────────────

class TestMergeTrials:
    def test_ensayo_encontrado_por_dos_consultas(self):
        hits = [
            TrialHit(_trial("NCT04000001"), term="axonal sensorimotor polyneuropathy"),
            TrialHit(
                _trial("NCT04000001"),
                term="hereditary ATTR amyloidosis",
                hypothesis="Amiloidosis hereditaria por transtiretina",
            ),
        ]
        unificados = merge_trials(hits)
        assert len(unificados) == 1
        assert unificados[0].matched_terms == [
            "axonal sensorimotor polyneuropathy",
            "hereditary ATTR amyloidosis",
        ]
        assert unificados[0].related_hypotheses == [
            "Amiloidosis hereditaria por transtiretina"
        ]

    def test_ensayo_solo_de_la_busqueda_base_no_tiene_hipotesis(self):
        unificados = merge_trials([TrialHit(_trial("NCT04000001"), term="neuropathy")])
        assert unificados[0].related_hypotheses == []

    def test_mas_de_diez_ensayos_unicos(self):
        hits = [
            TrialHit(_trial(f"NCT0400{i:04d}"), term="neuropathy") for i in range(17)
        ]
        unificados = merge_trials(hits)
        assert len(unificados) == MAX_TRIALS
        assert unificados[0].nct_id == "NCT04000000"
        assert unificados[-1].nct_id == "NCT04000009"

    def test_sin_hits_devuelve_lista_vacia(self):
        assert merge_trials([]) == []


# ── 3.7 Orden del resultado ────────────────────────────────────────────────────

class TestOrdenDelResultado:
    def test_ensayo_local_menos_compatible_va_despues(self):
        local_media = _trial("NCT_LOCAL", locations=["Argentina"], compatibility="media")
        exterior_alta = _trial("NCT_EXT", locations=["Spain"], compatibility="alta")
        ordenados = sort_trials([local_media, exterior_alta])
        assert [t.nct_id for t in ordenados] == ["NCT_EXT", "NCT_LOCAL"]

    def test_desempate_por_sede(self):
        exterior = _trial("NCT_EXT", locations=["Spain"], compatibility="alta")
        local = _trial("NCT_LOCAL", locations=["Brazil", "Argentina"], compatibility="alta")
        ordenados = sort_trials([exterior, local])
        assert [t.nct_id for t in ordenados] == ["NCT_LOCAL", "NCT_EXT"]

    def test_desempate_por_estado_de_reclutamiento(self):
        futuro = _trial("NCT_FUTURO", status="NOT_YET_RECRUITING", compatibility="media")
        abierto = _trial("NCT_ABIERTO", status="RECRUITING", compatibility="media")
        ordenados = sort_trials([futuro, abierto])
        assert [t.nct_id for t in ordenados] == ["NCT_ABIERTO", "NCT_FUTURO"]

    def test_sin_evaluar_va_al_final(self):
        sin_evaluar = _trial("NCT_SIN", compatibility="sin_evaluar")
        baja = _trial("NCT_BAJA", compatibility="baja")
        ordenados = sort_trials([sin_evaluar, baja])
        assert [t.nct_id for t in ordenados] == ["NCT_BAJA", "NCT_SIN"]

    def test_conserva_el_orden_de_descubrimiento_en_empate(self):
        primero = _trial("NCT_1", compatibility="alta")
        segundo = _trial("NCT_2", compatibility="alta")
        ordenados = sort_trials([primero, segundo])
        assert [t.nct_id for t in ordenados] == ["NCT_1", "NCT_2"]

    def test_la_sede_nunca_filtra(self):
        trials = [_trial("NCT_1", locations=["Spain"]), _trial("NCT_2", locations=[])]
        assert len(sort_trials(trials)) == 2
