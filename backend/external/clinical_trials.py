"""
Cliente para ClinicalTrials.gov API v2.

Documentación oficial: https://clinicaltrials.gov/data-api/api
Base URL: https://clinicaltrials.gov/api/v2/studies
Autenticación: ninguna (API pública)
Rate limit: sin límite publicado — se aplica back-off con tenacity por precaución.
"""

from typing import Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.trial import ClinicalTrial

_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
_TRIAL_URL_TEMPLATE = "https://clinicaltrials.gov/study/{nct_id}"

# Estados de reclutamiento por defecto: solo los ensayos que reclutan hoy.
_DEFAULT_STATUSES: tuple[str, ...] = ("RECRUITING",)

# Campos que necesitamos — reducir payload de la respuesta
_FIELDS = ",".join([
    "NCTId",
    "BriefTitle",
    "OverallStatus",
    "BriefSummary",
    "Condition",
    "Phase",
    "LeadSponsorName",
    "StartDate",
    "PrimaryCompletionDate",
    "EligibilityCriteria",
    "MinimumAge",
    "MaximumAge",
    "Sex",
    "LocationCountry",
])


# ── Parseo de la respuesta ─────────────────────────────────────────────────────

def _parse_trial(study: dict) -> ClinicalTrial | None:
    """
    Extrae un ClinicalTrial del dict de un study en la respuesta v2.
    Devuelve None si faltan campos obligatorios.
    """
    proto = study.get("protocolSection", {})

    id_mod = proto.get("identificationModule", {})
    nct_id = id_mod.get("nctId", "").strip()
    title = id_mod.get("briefTitle", "").strip()
    if not nct_id or not title:
        return None

    status_mod = proto.get("statusModule", {})
    status = status_mod.get("overallStatus", "UNKNOWN")
    start = (status_mod.get("startDateStruct") or {}).get("date")
    completion = (status_mod.get("primaryCompletionDateStruct") or {}).get("date")

    desc_mod = proto.get("descriptionModule", {})
    summary = desc_mod.get("briefSummary", "").strip()

    cond_mod = proto.get("conditionsModule", {})
    conditions = cond_mod.get("conditions", [])

    design_mod = proto.get("designModule", {})
    phases = design_mod.get("phases", [])
    phase = phases[0] if phases else None

    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    sponsor = (sponsor_mod.get("leadSponsor") or {}).get("name")

    elig_mod = proto.get("eligibilityModule", {})
    eligibility = elig_mod.get("eligibilityCriteria", "").strip() or None
    min_age = elig_mod.get("minimumAge")
    max_age = elig_mod.get("maximumAge")
    sex = elig_mod.get("sex")

    loc_mod = proto.get("contactsLocationsModule", {})
    locations_raw = loc_mod.get("locations", [])
    countries = sorted({loc.get("country", "") for loc in locations_raw if loc.get("country")})

    return ClinicalTrial(
        nct_id=nct_id,
        title=title,
        status=status,
        brief_summary=summary,
        conditions=conditions,
        phase=phase,
        sponsor=sponsor,
        start_date=start,
        completion_date=completion,
        eligibility_criteria=eligibility,
        min_age=min_age,
        max_age=max_age,
        sex=sex,
        locations=countries,
        url=_TRIAL_URL_TEMPLATE.format(nct_id=nct_id),
    )


# ── Cliente HTTP ───────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _get(params: dict) -> dict:
    """Realiza un GET a la API con reintentos exponenciales ante errores 5xx o timeout."""
    with httpx.Client(timeout=15.0) as client:
        response = client.get(_BASE_URL, params=params)
        response.raise_for_status()
        return response.json()


# ── Interfaz pública ───────────────────────────────────────────────────────────

def search(
    condition: str,
    keywords: str = "",
    max_results: int = 10,
    statuses: Sequence[str] = _DEFAULT_STATUSES,
) -> list[ClinicalTrial]:
    """
    Busca ensayos clínicos en ClinicalTrials.gov.

    Args:
        condition:   Condición o enfermedad principal (ej: "axonal neuropathy").
        keywords:    Términos adicionales de búsqueda (ej: "autonomic TTR").
        max_results: Número máximo de resultados a devolver (máx. 1000).
        statuses:    Estados de reclutamiento a consultar. El default deja solo
                     los que reclutan hoy; el Agente 05 pide además
                     NOT_YET_RECRUITING. Una secuencia vacía no filtra por estado.

    Returns:
        Lista de ClinicalTrial ordenada por relevancia (orden de la API).
    """
    params: dict = {
        "query.cond": condition,
        "pageSize": min(max_results, 1000),
        "format": "json",
    }
    if keywords:
        params["query.term"] = keywords
    if statuses:
        # La API v2 acepta varios estados separados por "|" en el mismo filtro.
        params["filter.overallStatus"] = "|".join(statuses)

    try:
        data = _get(params)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"ClinicalTrials.gov devolvió error {e.response.status_code}: {e.response.text[:200]}"
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Error de conexión con ClinicalTrials.gov: {e}") from e

    trials: list[ClinicalTrial] = []
    for study in data.get("studies", []):
        trial = _parse_trial(study)
        if trial is not None:
            trials.append(trial)

    return trials


def search_by_biomarkers(
    biomarkers: list[str],
    condition: str = "",
    max_results: int = 10,
) -> list[ClinicalTrial]:
    """
    Busca ensayos que involucren biomarcadores o genes específicos.
    Combina los biomarcadores como keywords adicionales.

    Args:
        biomarkers:  Lista de genes, anticuerpos o biomarcadores (ej: ["TTR", "anti-Hu"]).
        condition:   Condición base opcional para acotar la búsqueda.
        max_results: Número máximo de resultados.
    """
    keywords = " ".join(biomarkers[:5])  # Limitar para no saturar la query
    base_condition = condition or " ".join(biomarkers[:2])

    trials = search(
        condition=base_condition,
        keywords=keywords,
        max_results=max_results,
    )

    # La API combina los términos de query.term con AND: si los biomarcadores no
    # coinciden todos en un mismo ensayo la búsqueda queda vacía. Pasa siempre que
    # los biomarcadores del caso son hallazgos NEGATIVOS (ej: anti-Hu/Yo/Ri
    # descartados), que es información diagnóstica pero no sirve para filtrar
    # ensayos. En ese caso se reintenta con la condición sola.
    if not trials and keywords and base_condition:
        trials = search(condition=base_condition, max_results=max_results)

    return trials
