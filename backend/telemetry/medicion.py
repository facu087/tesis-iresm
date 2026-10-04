"""
Lógica pura de la medición de costos (control de costos, Sprint 4 — tareas
4.2, 5.4, 7.2 y 7.3).

Todo lo que está acá opera sobre datos ya obtenidos —registros de telemetría,
particiones, etiquetas, hipótesis— y no toca la red, el LLM ni el disco, así que
se prueba sin cuota. `scripts/medir_costos.py` es el único que orquesta las
llamadas reales y usa estas funciones para interpretarlas.

Nada de lo que devuelven estas funciones incluye texto clínico: trabajan con
conteos, índices, identificadores NCT y etiquetas. Las hipótesis se comparan
por su texto, pero solo para decidir si cambiaron; el texto no se devuelve.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping, Sequence

from ..agents import model_tasks
from ..models.arbitration import ArbitrationStatus
from ..models.hypothesis import Hypothesis
from ..models.report import AgentOutput
from .usage import CallRecord

# Cuota diaria del tier gratuito de Groq para el modelo principal.
DAILY_TOKEN_QUOTA = 200_000


# ── Holgura de techos y casos por día ─────────────────────────────────────────

def headroom(ceiling: int, max_observed: int | None) -> dict:
    """
    Holgura de una tarea: cuánto le sobra al techo sobre la salida más larga.

    Una holgura de 0 o negativa significa que la salida llegó al techo (y
    probablemente se cortó). Sin observaciones no hay holgura que calcular.
    """
    if max_observed is None:
        return {"ceiling": ceiling, "max_observed": None, "slack": None, "slack_pct": None}
    holgura = ceiling - max_observed
    return {
        "ceiling": ceiling,
        "max_observed": max_observed,
        "slack": holgura,
        "slack_pct": round(100 * holgura / ceiling, 1) if ceiling else None,
    }


def cases_per_day(tokens_per_case: int, quota: int = DAILY_TOKEN_QUOTA) -> int | None:
    """
    Cuántos análisis completos entran en la cuota diaria.

    `None` si no hay consumo medido (p. ej. modo mock): dividir por cero o
    inventar un número sería peor que no informarlo.
    """
    if tokens_per_case <= 0:
        return None
    return quota // tokens_per_case


# ── Comparación de la agrupación del Árbitro ──────────────────────────────────

def partitions_equal(a: Sequence[Sequence[int]], b: Sequence[Sequence[int]]) -> bool:
    """Dos particiones son iguales si tienen los mismos grupos, en cualquier orden."""
    return {frozenset(g) for g in a} == {frozenset(g) for g in b}


def classify_grouping(
    proposed: Sequence[Sequence[int]] | None,
    final: Sequence[Sequence[int]],
    status: ArbitrationStatus,
) -> str:
    """
    Qué pasó con la salida cruda del modelo al agrupar.

    - ``"aceptada"``: la validación determinista no tuvo que cambiar nada.
    - ``"reparada"``: la salida se usó, pero `normalize_partition()` tuvo que
      descartar índices repetidos o agregar hipótesis omitidas.
    - ``"fallback"``: la salida no se pudo usar (el modelo falló, no devolvió
      JSON o no tenía la clave ``groups``) y quedó la partición trivial.

    `proposed` es lo que recibió `normalize_partition()`, ya sin los índices
    fuera de rango que descarta `_as_index()` antes de llegar ahí.
    """
    if proposed is None or status is not ArbitrationStatus.OK:
        return "fallback"
    if [list(g) for g in proposed] == [list(g) for g in final]:
        return "aceptada"
    return "reparada"


# ── Comparación de etiquetas y términos del Agente 05 ─────────────────────────

def compare_labels(a: Mapping[str, str], b: Mapping[str, str]) -> dict:
    """
    Compara las etiquetas de compatibilidad por NCT ID de dos modelos.

    Solo se comparan los ensayos que evaluaron los dos; los que evaluó uno solo
    se listan aparte.
    """
    comunes = sorted(set(a) & set(b))
    coinciden = [n for n in comunes if a[n] == b[n]]
    distintas = {n: {"a": a[n], "b": b[n]} for n in comunes if a[n] != b[n]}
    return {
        "common": len(comunes),
        "matching": len(coinciden),
        "differing": distintas,
        "only_a": sorted(set(a) - set(b)),
        "only_b": sorted(set(b) - set(a)),
        "agreement_pct": round(100 * len(coinciden) / len(comunes), 1) if comunes else None,
    }


def _norm_term(termino: str) -> str:
    return " ".join(termino.lower().split())


def compare_terms(a: Mapping[int, Sequence[str]], b: Mapping[int, Sequence[str]]) -> dict:
    """
    Compara los términos planificados por dos modelos, por índice de candidata.

    Cada mapa lleva, por candidata, el término principal seguido de los
    sinónimos. Se informa cuántas candidatas tienen el mismo término principal
    y cuántas el mismo conjunto completo de términos (sin importar el orden ni
    las mayúsculas).
    """
    comunes = sorted(set(a) & set(b))
    principal = 0
    exactos = 0
    for i in comunes:
        ta = [_norm_term(t) for t in a[i]]
        tb = [_norm_term(t) for t in b[i]]
        if ta and tb and ta[0] == tb[0]:
            principal += 1
        if set(ta) == set(tb):
            exactos += 1
    return {
        "candidates_a": len(a),
        "candidates_b": len(b),
        "common": len(comunes),
        "main_term_matches": principal,
        "exact_matches": exactos,
        "only_a": sorted(set(a) - set(b)),
        "only_b": sorted(set(b) - set(a)),
    }


# ── Resumen de telemetría ─────────────────────────────────────────────────────

def max_completion(calls: Sequence[CallRecord]) -> int | None:
    valores = [c.completion_tokens for c in calls if c.completion_tokens is not None]
    return max(valores) if valores else None


def summarize_tasks(
    calls: Sequence[CallRecord], budgets: Mapping[str, model_tasks.TaskBudget]
) -> list[dict]:
    """
    Una fila por tarea: llamadas, salida máxima observada, techo, holgura y
    cuántas respuestas se cortaron por alcanzar el techo (tarea 4.2).
    """
    por_tarea: dict[str, list[CallRecord]] = {}
    for c in calls:
        por_tarea.setdefault(c.task, []).append(c)

    filas: list[dict] = []
    for tarea, grupo in por_tarea.items():
        maximo = max_completion(grupo)
        presupuesto = budgets.get(tarea)
        base = headroom(presupuesto.max_tokens, maximo) if presupuesto else {
            "ceiling": None, "max_observed": maximo, "slack": None, "slack_pct": None,
        }
        filas.append({
            "task": tarea,
            "models": sorted({c.model for c in grupo}),
            "calls": len(grupo),
            "failed_calls": sum(1 for c in grupo if not c.ok),
            "prompt_tokens": sum(c.prompt_tokens or 0 for c in grupo),
            "completion_tokens": sum(c.completion_tokens or 0 for c in grupo),
            "max_completion_tokens": maximo,
            "ceiling": base["ceiling"],
            "slack": base["slack"],
            "slack_pct": base["slack_pct"],
            "truncated_calls": sum(1 for c in grupo if c.truncated),
        })
    return filas


def summarize_agents(calls: Sequence[CallRecord]) -> list[dict]:
    """Una fila por agente (`None` agrupa las llamadas que no vienen de un agente)."""
    por_agente: dict[str | None, list[CallRecord]] = {}
    for c in calls:
        por_agente.setdefault(c.agent_id, []).append(c)

    filas: list[dict] = []
    for agent_id, grupo in por_agente.items():
        entrada = sum(c.prompt_tokens or 0 for c in grupo)
        salida = sum(c.completion_tokens or 0 for c in grupo)
        filas.append({
            "agent_id": agent_id,
            "agent_name": next((c.agent_name for c in grupo if c.agent_name), None),
            "calls": len(grupo),
            "prompt_tokens": entrada,
            "completion_tokens": salida,
            "total_tokens": entrada + salida,
        })
    return filas


def summarize_totals(calls: Sequence[CallRecord], wall_clock_seconds: float) -> dict:
    """Total por caso: tokens, latencia y cuántos casos entran en la cuota diaria."""
    entrada = sum(c.prompt_tokens or 0 for c in calls)
    salida = sum(c.completion_tokens or 0 for c in calls)
    return {
        "calls": len(calls),
        "failed_calls": sum(1 for c in calls if not c.ok),
        "calls_without_usage": sum(1 for c in calls if c.ok and c.prompt_tokens is None),
        "truncated_calls": sum(1 for c in calls if c.truncated),
        "prompt_tokens": entrada,
        "completion_tokens": salida,
        "total_tokens": entrada + salida,
        "wall_clock_seconds": wall_clock_seconds,
        "sum_call_latency_seconds": round(sum(c.latency_seconds for c in calls), 3),
        "daily_quota": DAILY_TOKEN_QUOTA,
        "cases_per_day": cases_per_day(entrada + salida),
    }


# ── Rondas 3 y 4 del debate ───────────────────────────────────────────────────

def _compare_agent_round(r3: Sequence[Hypothesis], r4: Sequence[Hypothesis]) -> dict:
    """Cambio de un agente entre dos rondas, emparejando hipótesis por enunciado."""
    por_texto_3 = {h.text: h for h in r3}
    por_texto_4 = {h.text: h for h in r4}
    comunes = [t for t in por_texto_3 if t in por_texto_4]

    nivel = sum(1 for t in comunes if por_texto_3[t].evidence_level != por_texto_4[t].evidence_level)
    prioridad = sum(1 for t in comunes if por_texto_3[t].priority != por_texto_4[t].priority)
    sin_cambio = sum(
        1 for t in comunes
        if por_texto_3[t].evidence_level == por_texto_4[t].evidence_level
        and por_texto_3[t].priority == por_texto_4[t].priority
    )
    retiradas = len(por_texto_3) - len(comunes)
    agregadas = len(por_texto_4) - len(comunes)
    return {
        "hypotheses_round_3": len(r3),
        "hypotheses_round_4": len(r4),
        "unchanged": sin_cambio,
        "level_changed": nivel,
        "priority_changed": prioridad,
        "removed": retiradas,
        "added": agregadas,
        "text_changed": max(retiradas, agregadas),
        "identical": retiradas == 0 and agregadas == 0 and nivel == 0 and prioridad == 0,
    }


def compare_rounds(round_3: Sequence[AgentOutput], round_4: Sequence[AgentOutput]) -> dict:
    """
    Cuánto cambió cada agente entre la Ronda 3 y la Ronda 4 (tarea 7.3).

    Una hipótesis "cambió de enunciado" si su texto de la Ronda 3 ya no está en
    la Ronda 4 (el modelo la reformuló o la reemplazó). `text_changed` toma el
    mayor entre retiradas y agregadas: una reformulación aparece como una de
    cada, y cuenta una sola vez. `changed_hypotheses` del total suma, por
    agente, las hipótesis con algún cambio de enunciado, nivel o prioridad.
    """
    por_agente_3 = {o.agent_id: o for o in round_3}
    por_agente_4 = {o.agent_id: o for o in round_4}

    resultado: dict[str, dict] = {}
    for agent_id in por_agente_3:
        if agent_id in por_agente_4:
            resultado[agent_id] = _compare_agent_round(
                por_agente_3[agent_id].hypotheses, por_agente_4[agent_id].hypotheses
            )

    cambiadas = sum(
        r["text_changed"] + r["level_changed"] + r["priority_changed"] for r in resultado.values()
    )
    return {
        "by_agent": resultado,
        "only_in_round_3": sorted(set(por_agente_3) - set(por_agente_4)),
        "only_in_round_4": sorted(set(por_agente_4) - set(por_agente_3)),
        "totals": {
            "hypotheses_round_3": sum(r["hypotheses_round_3"] for r in resultado.values()),
            "hypotheses_round_4": sum(r["hypotheses_round_4"] for r in resultado.values()),
            "changed_hypotheses": cambiadas,
            "agents_identical": sum(1 for r in resultado.values() if r["identical"]),
            "agents_compared": len(resultado),
        },
    }


# ── Cambio temporal de modelo ─────────────────────────────────────────────────

@contextlib.contextmanager
def swapped_model(
    task: str,
    model: str,
    budgets: dict[str, model_tasks.TaskBudget] | None = None,
) -> Iterator[None]:
    """
    Reemplaza el modelo de una tarea en `TASK_BUDGETS` y lo restaura siempre.

    Los `TaskBudget` son inmutables, así que se reemplaza la entrada entera
    conservando el techo. La restauración está en un `finally`: una excepción
    en la rama que se está midiendo no puede dejar el mapa de producción con el
    modelo cambiado. Levanta `KeyError` ante una tarea no registrada sin tocar
    nada.
    """
    mapa = model_tasks.TASK_BUDGETS if budgets is None else budgets
    original = mapa[task]
    mapa[task] = model_tasks.TaskBudget(model, original.max_tokens)
    try:
        yield
    finally:
        mapa[task] = original


# ── Resumen legible ───────────────────────────────────────────────────────────

def _celda(valor: object) -> str:
    return "-" if valor is None else str(valor)


def format_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Tabla de texto con columnas alineadas a la izquierda."""
    filas = [[_celda(c) for c in fila] for fila in rows]
    anchos = [
        max(len(h), *(len(f[i]) for f in filas)) if filas else len(h)
        for i, h in enumerate(headers)
    ]
    linea = lambda celdas: "  ".join(c.ljust(anchos[i]) for i, c in enumerate(celdas)).rstrip()
    return "\n".join([
        linea(list(headers)),
        "  ".join("-" * a for a in anchos),
        *(linea(f) for f in filas),
    ])


def render_summary(medicion: Mapping) -> str:
    """
    Arma el `resumen.txt` legible a partir del dict de `medicion.json`.

    Tolera un dict parcial (una medición interrumpida a mitad de camino): cada
    sección se imprime solo si existe, y un error de una etapa se muestra en
    lugar de ocultarse.
    """
    out: list[str] = []
    if medicion.get("mock"):
        out += [
            "*" * 70,
            "MODO MOCK: respuestas grabadas, sin llamadas reales al LLM.",
            "Los tokens y las latencias NO son una medición. No usar en la tesis.",
            "*" * 70,
            "",
        ]
    out += ["MEDICIÓN DE COSTOS DEL PIPELINE NEXUS", ""]
    out.append(f"Generada: {_celda(medicion.get('generated_at'))}")
    out.append("")

    etapas = medicion.get("stages", {})
    if etapas:
        out += ["ETAPAS", format_table(
            ["etapa", "estado", "segundos", "error"],
            [[n, e.get("status"), e.get("seconds"), e.get("error")] for n, e in etapas.items()],
        ), ""]

    base = medicion.get("base")
    if base:
        t = base["totals"]
        out += [
            "7.2 TOTAL POR CASO (pasada base)",
            f"  llamadas: {t['calls']} ({t['failed_calls']} fallidas, "
            f"{t['calls_without_usage']} sin consumo informado)",
            f"  tokens: {t['total_tokens']} ({t['prompt_tokens']} entrada / "
            f"{t['completion_tokens']} salida)",
            f"  latencia total: {t['wall_clock_seconds']} s "
            f"(suma de llamadas: {t['sum_call_latency_seconds']} s)",
            f"  casos por cuota diaria de {t['daily_quota']} tokens: {_celda(t['cases_per_day'])}",
            "",
            "7.2 POR PASO (tarea)",
            format_table(
                ["tarea", "modelo", "llamadas", "entrada", "salida"],
                [[r["task"], ",".join(r["models"]), r["calls"], r["prompt_tokens"],
                  r["completion_tokens"]] for r in base["tasks"]],
            ),
            "",
            "7.2 POR AGENTE",
            format_table(
                ["agente", "nombre", "llamadas", "entrada", "salida", "total"],
                [[r["agent_id"], r["agent_name"], r["calls"], r["prompt_tokens"],
                  r["completion_tokens"], r["total_tokens"]] for r in base["agents"]],
            ),
            "",
            "4.2 TRUNCADOS Y HOLGURA",
            format_table(
                ["tarea", "llamadas", "salida máx.", "techo", "holgura", "holgura %", "cortadas"],
                [[r["task"], r["calls"], r["max_completion_tokens"], r["ceiling"], r["slack"],
                  r["slack_pct"], r["truncated_calls"]] for r in base["tasks"]],
            ),
            f"  respuestas cortadas por techo en total: {t['truncated_calls']}",
            "",
        ]

    rondas = medicion.get("debate_rounds_3_4")
    if rondas:
        out.append("7.3 CAMBIO ENTRE RONDA 3 Y RONDA 4")
        if not rondas.get("available", True):
            out.append(f"  no disponible: {rondas.get('reason')}")
        else:
            out.append(format_table(
                ["agente", "R3", "R4", "sin cambio", "nivel", "prioridad", "enunciado", "idéntico"],
                [[a, r["hypotheses_round_3"], r["hypotheses_round_4"], r["unchanged"],
                  r["level_changed"], r["priority_changed"], r["text_changed"], r["identical"]]
                 for a, r in rondas["by_agent"].items()],
            ))
            tot = rondas["totals"]
            out.append(
                f"  agentes idénticos: {tot['agents_identical']}/{tot['agents_compared']}; "
                f"hipótesis con algún cambio: {tot['changed_hypotheses']}"
            )
        out.append("")

    comp = medicion.get("comparison")
    if comp:
        out.append("5.4 COMPARACIÓN GROQ_MAIN vs GROQ_FAST (mismas entradas)")
        out += _render_comparison(comp)
    return "\n".join(out).rstrip() + "\n"


def _render_comparison(comp: Mapping) -> list[str]:
    out: list[str] = []
    for clave, titulo in (
        ("grouping", "Agrupación del Árbitro"),
        ("terms", "Agente 05 — planificación de términos"),
        ("evaluation", "Agente 05 — evaluación de compatibilidad"),
    ):
        bloque = comp.get(clave)
        if not bloque:
            continue
        out.append(f"  {titulo}")
        if bloque.get("status") == "omitida":
            out += [f"    omitida: {bloque.get('reason')}", ""]
            continue
        filas = []
        for modelo, r in bloque.get("by_model", {}).items():
            filas.append([modelo, r.get("status"), r.get("outcome"), r.get("usage_summary"),
                          r.get("error")])
        out.append(format_table(["modelo", "estado", "resultado", "uso", "error"], filas))
        if bloque.get("comparison") is not None:
            out.append(f"    comparación: {bloque['comparison']}")
        out.append("")
    return out
