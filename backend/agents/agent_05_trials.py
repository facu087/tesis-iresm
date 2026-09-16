"""
Agente 05 — Navegador de Ensayos
Modelo: openai/gpt-oss-120b via Groq (arquitectura final: ver .claude/CLAUDE.md)
Rol: encontrar ensayos clínicos activos relacionados con las hipótesis del caso
     y estimar, de forma orientativa y nunca diagnóstica, su compatibilidad con
     el perfil del paciente.

Es un agente **híbrido**: el LLM solo traduce hipótesis a términos de búsqueda
en inglés y etiqueta compatibilidad; todo lo que puede quitar un ensayo de la
vista del médico (filtros de edad y sexo, saneamiento de términos, orden del
resultado) es determinista y vive en `pipeline/trial_matching.py`.

No participa del debate adversarial: expone `navigate()`, no `run()`.

Privacidad: a ClinicalTrials.gov y Orphanet solo viajan términos saneados en
inglés. La edad y el sexo se usan para filtrar localmente y nunca salen del
proceso. Los logs registran el paso y el tipo de excepción, nunca el mensaje
—`extract_json` mete la respuesta del LLM adentro— ni texto clínico.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field

from ..external import clinical_trials
from ..external.orphanet import OrphanetClient
from ..external.rate_limiter import (
    clinical_trials_breaker,
    clinical_trials_limiter,
    orphanet_breaker,
)
from ..models.report import AgentOutput
from ..models.trial import (
    ApiStatus,
    ClinicalTrial,
    Compatibility,
    RareDiseaseMatch,
    StepStatus,
    TrialCandidate,
    TrialNavigationInput,
    TrialNavigationResult,
    TrialSearchSummary,
)
from ..pipeline.trial_matching import (
    MAX_TRIALS,
    TrialHit,
    apply_hard_filters,
    merge_trials,
    names_match,
    sanitize_terms,
    sort_trials,
)
from .base_agent import GROQ_MAIN, BaseAgent

# Estados de reclutamiento que se consultan: los que reclutan hoy y los que
# todavía no abrieron. Un ensayo que abre en tres meses es accionable (D14).
_TRIAL_STATUSES: tuple[str, ...] = ("RECRUITING", "NOT_YET_RECRUITING")

_MAX_SYNONYMS = 2                 # Sinónimos por candidata
_BASE_MAX_RESULTS = 10            # Resultados de la búsqueda base
_CANDIDATE_MAX_RESULTS = 5        # Resultados por hipótesis candidata
_MAX_CRITERIA_CHARS = 1500        # Truncado de eligibility_criteria para el LLM
_MAX_RATIONALE_CHARS = 600        # Truncado del fundamento que devuelve el LLM
_MAX_CRITERIA_ITEMS = 5           # Criterios a verificar por ensayo
_MAX_CRITERION_CHARS = 200        # Largo de cada criterio

_VALID_COMPATIBILITY = {
    Compatibility.ALTA.value,
    Compatibility.MEDIA.value,
    Compatibility.BAJA.value,
}


@dataclass
class TermPlan:
    """Términos de búsqueda en inglés para una hipótesis candidata."""

    candidate: TrialCandidate
    condition_en: str
    synonyms: list[str] = field(default_factory=list)

    @property
    def terms(self) -> list[str]:
        """Término principal seguido de sus sinónimos, en orden de uso."""
        return [self.condition_en, *self.synonyms]


@dataclass
class _SearchOutcome:
    """Resultado de un grupo de consultas a ClinicalTrials.gov."""

    hits: list[TrialHit] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    ok: int = 0
    failed: int = 0


@dataclass
class _Evaluation:
    """Etiqueta de compatibilidad que el LLM le puso a un ensayo."""

    compatibility: str
    rationale: str | None = None
    criteria: list[str] = field(default_factory=list)


class TrialNavigatorAgent(BaseAgent):
    """Agente 05 — Navegador de Ensayos."""

    AGENT_ID = "05"
    AGENT_NAME = "Navegador de Ensayos"
    MODEL = GROQ_MAIN
    SYSTEM_PROMPT = """Sos un especialista en investigación clínica que ayuda a un médico a
encontrar ensayos clínicos potencialmente relevantes para un caso complejo.

Tu rol tiene dos tareas, según lo que te pidan en cada mensaje:
1. Traducir hipótesis de investigación escritas en español a términos de condición en
   inglés médico, tal como los indexa ClinicalTrials.gov.
2. Estimar, de forma orientativa, qué tan compatible es cada ensayo con el perfil
   clínico del paciente.

REGLAS CRÍTICAS:
1. NO emitas diagnósticos. Las hipótesis son líneas de investigación, no enfermedades
   confirmadas del paciente.
2. NO afirmes que el paciente es elegible para un ensayo ni recomiendes inscribirlo:
   la elegibilidad la determina el equipo investigador de cada ensayo.
3. NUNCA descartes un ensayo. Si un ensayo parece poco compatible, etiquetalo como
   "baja" y explicá por qué: la decisión es del médico responsable.
4. NUNCA inventes identificadores NCT. Solo podés referirte a los NCT ID que te
   envían en el mensaje.
5. Los términos de búsqueda deben ser nombres de condiciones o enfermedades en inglés,
   sin datos del paciente (edad, sexo, la palabra "patient"), de 8 palabras como máximo.
6. Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni markdown."""

    # ── Interfaz del debate: este agente no participa ─────────────────

    def run(self, clinical_context: str) -> AgentOutput:
        """
        No implementado a propósito.

        El Agente 05 no genera hipótesis ni debate con los demás: navega
        ensayos a partir de las hipótesis que ya produjo el pipeline.
        """
        raise NotImplementedError(
            "El Agente 05 no participa del debate: usar navigate()"
        )

    # ── Punto de entrada ──────────────────────────────────────────────

    async def navigate(self, entrada: TrialNavigationInput) -> TrialNavigationResult:
        """
        Busca ensayos para el caso y los devuelve evaluados y ordenados.

        Nunca lanza por una falla externa: cada paso tiene su fallback y el
        estado de la búsqueda queda en el resumen para que el reporte distinga
        "no hay ensayos" de "no se pudo consultar".

        Args:
            entrada: Contrato neutral armado por
                     `pipeline.trial_matching.build_navigation_input()`.

        Returns:
            TrialNavigationResult con los ensayos, las enfermedades raras
            marcadas y el resumen de la búsqueda.
        """
        planes, planificacion = await self._plan_terms(entrada)

        hits, terminos, estado_ct = await self._search_trials(entrada, planes)
        raras, terminos_orphanet, estado_orphanet = await self._match_rare_diseases(planes)

        # Ensayos únicos antes de los filtros duros.
        unicos: dict[str, ClinicalTrial] = {}
        for hit in hits:
            unicos.setdefault(hit.trial.nct_id, hit.trial)
        encontrados = len(unicos)

        conservados, conteo = apply_hard_filters(
            list(unicos.values()), entrada.demographics
        )
        permitidos = {t.nct_id for t in conservados}
        trials = merge_trials(
            [h for h in hits if h.trial.nct_id in permitidos], limit=MAX_TRIALS
        )

        evaluaciones, estado_evaluacion, descartadas = await self._evaluate(
            entrada, trials
        )
        trials = sort_trials(_apply_evaluations(trials, evaluaciones))

        consultados = list(dict.fromkeys(terminos + terminos_orphanet))
        return TrialNavigationResult(
            trials=trials,
            rare_diseases=raras,
            summary=TrialSearchSummary(
                estado_clinicaltrials=estado_ct,
                estado_orphanet=estado_orphanet,
                planificacion=planificacion,
                evaluacion=estado_evaluacion,
                terminos_consultados=consultados,
                encontrados=encontrados,
                excluidos_por_edad=conteo.por_edad,
                excluidos_por_sexo=conteo.por_sexo,
                evaluaciones_descartadas=descartadas,
            ),
        )

    # ── 1. Planificación de términos (LLM) ────────────────────────────

    async def _plan_terms(
        self, entrada: TrialNavigationInput
    ) -> tuple[list[TermPlan], str]:
        """
        Traduce las hipótesis candidatas a términos de condición en inglés.

        Una sola llamada al LLM por análisis. Ante cualquier falla devuelve una
        lista vacía y `fallback`: el pipeline sigue con la búsqueda base.
        """
        if not entrada.candidates:
            return [], StepStatus.SIN_CANDIDATAS.value

        prompt = _build_planning_prompt(entrada)
        try:
            raw = await asyncio.to_thread(self._call_llm, prompt)
            datos = self.extract_json(raw)
        except Exception as exc:
            self._log_fallback("planificación de términos", exc)
            return [], StepStatus.FALLBACK.value

        planes: list[TermPlan] = []
        usados: set[int] = set()
        for item in datos.get("terms", []):
            if not isinstance(item, dict):
                continue
            indice = _as_index(item.get("candidate"), len(entrada.candidates))
            if indice is None or indice in usados:
                # Índice fuera de rango: el LLM se refiere a una candidata que
                # no existe. Se ignora y no genera consultas.
                continue
            crudos = [str(item.get("condition_en") or "")]
            sinonimos = item.get("synonyms_en") or []
            if isinstance(sinonimos, list):
                crudos += [str(s) for s in sinonimos]
            validos = sanitize_terms(crudos, limit=_MAX_SYNONYMS + 1)
            if not validos:
                continue
            usados.add(indice)
            planes.append(
                TermPlan(
                    candidate=entrada.candidates[indice],
                    condition_en=validos[0],
                    synonyms=validos[1:],
                )
            )

        if not planes:
            return [], StepStatus.FALLBACK.value
        return planes, StepStatus.OK.value

    # ── 2. Búsqueda en ClinicalTrials.gov (determinista) ──────────────

    async def _search_once(
        self, condition: str, keywords: str, max_results: int
    ) -> list[ClinicalTrial]:
        """Una consulta a ClinicalTrials.gov, con rate limit y circuit breaker."""
        async with clinical_trials_limiter:
            async with clinical_trials_breaker:
                return await asyncio.to_thread(
                    clinical_trials.search,
                    condition=condition,
                    keywords=keywords,
                    max_results=max_results,
                    statuses=_TRIAL_STATUSES,
                )

    async def _base_search(self, entrada: TrialNavigationInput) -> _SearchOutcome:
        """
        Búsqueda base, equivalente a la vigente antes del Agente 05.

        Condición en inglés más hasta 5 biomarcadores como palabras clave, con
        reintento solo por la condición si la combinación no devuelve nada (la
        API combina las palabras clave con AND y los biomarcadores del caso
        suelen ser hallazgos negativos).
        """
        resultado = _SearchOutcome()
        condicion = entrada.condition_en or " ".join(entrada.biomarker_terms[:2])
        if not condicion:
            # Sin condición en inglés ni biomarcadores no hay búsqueda base: el
            # motivo de consulta en español da 0 resultados y es texto del caso.
            return resultado

        keywords = " ".join(entrada.biomarker_terms[:5])
        resultado.terms.append(condicion)
        try:
            trials = await self._search_once(condicion, keywords, _BASE_MAX_RESULTS)
            resultado.ok += 1
        except Exception as exc:
            resultado.failed += 1
            self._log_fallback("búsqueda base", exc)
            return resultado

        if not trials and keywords:
            try:
                trials = await self._search_once(condicion, "", _BASE_MAX_RESULTS)
                resultado.ok += 1
            except Exception as exc:
                resultado.failed += 1
                self._log_fallback("búsqueda base (reintento)", exc)

        resultado.hits = [TrialHit(trial=t, term=condicion) for t in trials]
        return resultado

    async def _candidate_search(self, plan: TermPlan) -> _SearchOutcome:
        """Consulta el término principal de una hipótesis y, si no da, sus sinónimos."""
        resultado = _SearchOutcome()
        for termino in plan.terms:
            resultado.terms.append(termino)
            try:
                trials = await self._search_once(termino, "", _CANDIDATE_MAX_RESULTS)
                resultado.ok += 1
            except Exception as exc:
                resultado.failed += 1
                self._log_fallback("búsqueda por hipótesis", exc)
                continue
            if trials:
                resultado.hits = [
                    TrialHit(trial=t, term=termino, hypothesis=plan.candidate.text)
                    for t in trials
                ]
                break
        return resultado

    async def _search_trials(
        self, entrada: TrialNavigationInput, planes: list[TermPlan]
    ) -> tuple[list[TrialHit], list[str], str]:
        """
        Ejecuta la búsqueda base y la de cada hipótesis, en paralelo acotado.

        Una consulta que falla no cancela las demás: `return_exceptions=True` y
        cada coroutine ya atrapa sus propias fallas.
        """
        tareas = [self._base_search(entrada)] + [
            self._candidate_search(plan) for plan in planes
        ]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)

        hits: list[TrialHit] = []
        terminos: list[str] = []
        ok = 0
        failed = 0
        for resultado in resultados:
            if isinstance(resultado, BaseException):
                # Red de seguridad: una coroutine que igual se rompió.
                failed += 1
                self._log_fallback("búsqueda de ensayos", resultado)
                continue
            hits.extend(resultado.hits)
            terminos.extend(resultado.terms)
            ok += resultado.ok
            failed += resultado.failed

        return hits, list(dict.fromkeys(terminos)), _api_status(ok, failed)

    # ── 3. Orphanet (determinista) ────────────────────────────────────

    async def _match_rare_diseases(
        self, planes: list[TermPlan]
    ) -> tuple[list[RareDiseaseMatch], list[str], str]:
        """
        Marca las hipótesis que corresponden a una enfermedad rara catalogada.

        Solo ante coincidencia **exacta** normalizada con el nombre preferido de
        Orphanet: etiquetar mal una hipótesis clínica es peor que no marcarla.
        Se consulta siempre, haya o no `ORPHANET_API_KEY` (la API responde sin
        credencial). El cliente ya aplica `orphanet_limiter` internamente, así
        que acá solo se envuelve en `orphanet_breaker` (design D9).
        """
        if not planes:
            return [], [], ApiStatus.SIN_CONSULTA.value

        marcas: list[RareDiseaseMatch] = []
        terminos: list[str] = []
        ok = 0
        failed = 0

        try:
            async with OrphanetClient() as client:
                for plan in planes:
                    marca, consultados, aciertos, fallos = await self._match_one(
                        client, plan
                    )
                    terminos.extend(consultados)
                    ok += aciertos
                    failed += fallos
                    if marca is not None:
                        marcas.append(marca)
        except Exception as exc:
            failed += 1
            self._log_fallback("consulta a Orphanet", exc)

        return marcas, list(dict.fromkeys(terminos)), _api_status(ok, failed)

    async def _match_one(
        self, client: OrphanetClient, plan: TermPlan
    ) -> tuple[RareDiseaseMatch | None, list[str], int, int]:
        """Busca la coincidencia exacta de una hipótesis, término por término."""
        consultados: list[str] = []
        ok = 0
        failed = 0

        for termino in plan.terms:
            consultados.append(termino)
            try:
                async with orphanet_breaker:
                    candidatas = await client.search(termino)
                ok += 1
            except Exception as exc:
                failed += 1
                self._log_fallback("consulta a Orphanet", exc)
                continue

            for candidata in candidatas:
                if names_match(termino, candidata.name):
                    return (
                        RareDiseaseMatch(
                            orpha_code=candidata.orpha_code,
                            name=candidata.name,
                            url=candidata.url,
                            hypothesis=plan.candidate.text,
                            matched_term=termino,
                        ),
                        consultados,
                        ok,
                        failed,
                    )

        return None, consultados, ok, failed

    # ── 4. Evaluación de compatibilidad (LLM) ─────────────────────────

    async def _evaluate(
        self, entrada: TrialNavigationInput, trials: list[ClinicalTrial]
    ) -> tuple[dict[str, _Evaluation], str, int]:
        """
        Pide al LLM una etiqueta de compatibilidad por ensayo, en una sola llamada.

        La salida se valida contra los ensayos que se enviaron: un NCT ID que no
        estaba se descarta y se cuenta. El LLM nunca excluye un ensayo.
        """
        if not trials:
            return {}, StepStatus.SIN_ENSAYOS.value, 0

        prompt = _build_evaluation_prompt(entrada, trials)
        try:
            raw = await asyncio.to_thread(self._call_llm, prompt)
            datos = self.extract_json(raw)
        except Exception as exc:
            self._log_fallback("evaluación de compatibilidad", exc)
            return {}, StepStatus.FALLBACK.value, 0

        enviados = {t.nct_id for t in trials}
        evaluaciones: dict[str, _Evaluation] = {}
        descartadas = 0

        for item in datos.get("evaluations", []):
            if not isinstance(item, dict):
                descartadas += 1
                continue
            nct = str(item.get("nct_id") or "").strip()
            if nct not in enviados:
                descartadas += 1
                continue
            if nct in evaluaciones:
                # Duplicado: gana la primera evaluación.
                continue
            etiqueta = str(item.get("compatibility") or "").strip().lower()
            if etiqueta not in _VALID_COMPATIBILITY:
                etiqueta = Compatibility.SIN_EVALUAR.value
            evaluaciones[nct] = _Evaluation(
                compatibility=etiqueta,
                rationale=_clip(item.get("rationale"), _MAX_RATIONALE_CHARS),
                criteria=_clip_list(item.get("criteria_to_verify")),
            )

        if descartadas:
            print(
                f"[NEXUS] Agente {self.AGENT_ID} — evaluación de compatibilidad: "
                f"{descartadas} evaluación(es) descartada(s) por NCT ID desconocido",
                file=sys.stderr,
            )

        return evaluaciones, StepStatus.OK.value, descartadas

    # ── Logs sin texto clínico ────────────────────────────────────────

    def _log_fallback(self, paso: str, exc: BaseException) -> None:
        """
        Registra un fallback con el tipo de excepción y nada más.

        Nunca `str(exc)`: `extract_json` mete la respuesta del LLM en el mensaje
        y los errores HTTP repiten el término consultado (design D12).
        """
        print(
            f"[NEXUS] Agente {self.AGENT_ID} — {paso}: fallback ({type(exc).__name__})",
            file=sys.stderr,
        )


# ── Helpers de estado y validación ─────────────────────────────────────────────

def _api_status(ok: int, failed: int) -> str:
    """Traduce el conteo de consultas al estado que informa el reporte."""
    if ok == 0 and failed == 0:
        return ApiStatus.SIN_CONSULTA.value
    if failed == 0:
        return ApiStatus.OK.value
    if ok == 0:
        return ApiStatus.NO_DISPONIBLE.value
    return ApiStatus.PARCIAL.value


def _as_index(valor: object, total: int) -> int | None:
    """Convierte el número de candidata (1-based) del LLM a un índice válido."""
    try:
        numero = int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if 1 <= numero <= total:
        return numero - 1
    return None


def _clip(valor: object, largo: int) -> str | None:
    """Trunca un texto del LLM, o None si no hay nada utilizable."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if not texto:
        return None
    return texto[:largo]


def _clip_list(valor: object) -> list[str]:
    """Trunca la lista de criterios a verificar en cantidad y en largo."""
    if not isinstance(valor, list):
        return []
    criterios: list[str] = []
    for item in valor[:_MAX_CRITERIA_ITEMS]:
        texto = _clip(item, _MAX_CRITERION_CHARS)
        if texto:
            criterios.append(texto)
    return criterios


def _apply_evaluations(
    trials: list[ClinicalTrial], evaluaciones: dict[str, _Evaluation]
) -> list[ClinicalTrial]:
    """
    Copia cada ensayo con su etiqueta de compatibilidad.

    Un ensayo que el LLM omitió queda `sin_evaluar` y se conserva igual.
    """
    evaluados: list[ClinicalTrial] = []
    for trial in trials:
        evaluacion = evaluaciones.get(trial.nct_id)
        if evaluacion is None:
            evaluados.append(trial)
            continue
        evaluados.append(
            trial.model_copy(
                update={
                    "compatibility": evaluacion.compatibility,
                    "compatibility_rationale": evaluacion.rationale,
                    "criteria_to_verify": evaluacion.criteria,
                }
            )
        )
    return evaluados


# ── Prompts ────────────────────────────────────────────────────────────────────

def _build_planning_prompt(entrada: TrialNavigationInput) -> str:
    """Arma el mensaje de planificación: solo hipótesis y condición, sin perfil."""
    lineas = [
        "Traducí cada hipótesis de investigación a un término de condición en inglés "
        "médico, tal como lo indexa ClinicalTrials.gov, con hasta "
        f"{_MAX_SYNONYMS} sinónimos.",
        "",
    ]
    if entrada.condition_en:
        lineas.append(f"CONDICIÓN DEL CASO (inglés): {entrada.condition_en}")
        lineas.append("")
    lineas.append("HIPÓTESIS:")
    for i, candidata in enumerate(entrada.candidates, start=1):
        lineas.append(f"{i}. {candidata.text}")
    lineas += [
        "",
        "Si la hipótesis corresponde a una enfermedad rara, incluí como sinónimo el "
        "nombre preferido con el que la cataloga Orphanet.",
        "No incluyas datos del paciente en los términos (edad, sexo, la palabra 'patient').",
        "",
        "Respondé ÚNICAMENTE con JSON válido:",
        '{"terms": [{"candidate": 1, "condition_en": "...", "synonyms_en": ["...", "..."]}]}',
    ]
    return "\n".join(lineas)


def _build_evaluation_prompt(
    entrada: TrialNavigationInput, trials: list[ClinicalTrial]
) -> str:
    """Arma el mensaje de evaluación: perfil estructurado más los ensayos."""
    lineas = [
        "Estimá qué tan compatible es cada ensayo con el perfil clínico del paciente.",
        "No afirmes elegibilidad: indicá qué criterios habría que verificar.",
        "",
        "PERFIL CLÍNICO:",
        entrada.eligibility_profile or "No disponible.",
        "",
        "ENSAYOS:",
    ]
    for trial in trials:
        lineas.append(f"- {trial.nct_id}: {trial.title}")
        if trial.conditions:
            lineas.append(f"  Condiciones: {', '.join(trial.conditions[:5])}")
        if trial.min_age or trial.max_age:
            lineas.append(
                f"  Rango etario: {trial.min_age or 'sin mínimo'} – "
                f"{trial.max_age or 'sin máximo'}"
            )
        if trial.sex:
            lineas.append(f"  Sexo admitido: {trial.sex}")
        if trial.eligibility_criteria:
            criterios = trial.eligibility_criteria[:_MAX_CRITERIA_CHARS]
            lineas.append(f"  Criterios: {criterios}")
    lineas += [
        "",
        "Evaluá TODOS los ensayos de la lista y ninguno más: los NCT ID que uses "
        "tienen que estar arriba.",
        "Etiquetas permitidas: alta, media, baja.",
        "",
        "Respondé ÚNICAMENTE con JSON válido:",
        '{"evaluations": [{"nct_id": "NCT...", "compatibility": "alta", '
        '"rationale": "fundamento breve en español", '
        '"criteria_to_verify": ["criterio 1", "criterio 2"]}]}',
    ]
    return "\n".join(lineas)
