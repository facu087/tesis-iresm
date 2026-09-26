"""
Registro de consumo de tokens por llamada al LLM, agrupado por análisis
(control de costos, Sprint 4).

El registro vive en un contexto por análisis (`contextvars`), no en un
acumulador global (D2): FastAPI atiende análisis en paralelo, y un
acumulador global mezclaría el desglose de casos distintos sin que nadie lo
note. `contextvars` es lo que corresponde con `asyncio`: el contexto se
propaga solo a las corrutinas hijas y a los `asyncio.to_thread()` que usa el
pipeline, sin pasarlo por parámetro en cada llamada.

El identificador de un análisis es aleatorio (D3), nunca derivado del texto
clínico: un hash del caso sería un identificador pseudónimo persistente que
permitiría vincular dos análisis del mismo paciente a través de este archivo.

`output/costos.jsonl` acumula una línea JSON por análisis (D4): se puede
promediar con Python sin releer ni reescribir el archivo, y sobrevive a una
corrida interrumpida sin corromperse.

Nada de lo que se registra acá puede ser dato clínico: `record_call()` no
acepta ni el prompt ni la respuesta del modelo como parámetro, así que
estructuralmente no puede filtrarlos.
"""

from __future__ import annotations

import contextvars
import copy
import dataclasses
import json
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import pricing

_DEFAULT_OUTPUT_PATH = Path("output/costos.jsonl")


@dataclasses.dataclass(frozen=True)
class CallRecord:
    """
    Un intento de llamada al proveedor.

    Nunca contiene el prompt, la respuesta del modelo ni ningún fragmento de
    texto clínico: solo conteos, identificadores de agente y nombres de
    modelo.
    """

    task: str
    model: str
    ok: bool
    latency_seconds: float
    agent_id: str | None = None
    agent_name: str | None = None
    # None = el proveedor no informó su consumo (se registra igual, marcada;
    # nunca se omite: "Datos registrados por llamada", telemetria-de-costos).
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    truncated: bool = False  # la respuesta se cortó al alcanzar el techo de tokens
    mock: bool = False       # la respuesta vino del modo mock, no del proveedor real


class AnalysisUsage:
    """
    Registro de todas las llamadas de un análisis.

    El id es aleatorio (D3), generado al construirse. `record()` tiene su
    propio lock: el pipeline llama en paralelo desde varios
    `asyncio.to_thread()` (agentes de la Ronda 1, Agente 05), que corren en
    threads del sistema operativo de verdad, no solo coroutines del mismo hilo.
    """

    def __init__(self) -> None:
        self.analysis_id = secrets.token_hex(8)
        self.calls: list[CallRecord] = []
        self._lock = threading.Lock()

    def record(self, call: CallRecord) -> None:
        with self._lock:
            self.calls.append(call)


_current: contextvars.ContextVar[AnalysisUsage | None] = contextvars.ContextVar(
    "nexus_usage_registry", default=None
)


def open_registry() -> contextvars.Token:
    """
    Abre un registro nuevo y lo activa en el contexto actual.

    El router llama a esto al empezar un análisis. Devuelve el token que hay
    que pasarle a `close_registry()` para cerrarlo.
    """
    return _current.set(AnalysisUsage())


def current() -> AnalysisUsage | None:
    """Registro activo en el contexto actual, o `None` si no hay ninguno."""
    return _current.get()


def record_call(
    *,
    task: str,
    model: str,
    ok: bool,
    latency_seconds: float,
    agent_id: str | None = None,
    agent_name: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    truncated: bool = False,
    mock: bool = False,
) -> None:
    """
    Registra un intento de llamada en el registro activo del contexto actual.

    No hace nada si no hay un registro abierto: un script de demo o un test
    que llaman a `call_provider()` sin pasar por el router no deben fallar
    por esto. La telemetría nunca es condición para que algo funcione (D2).
    """
    registry = _current.get()
    if registry is None:
        return
    registry.record(CallRecord(
        task=task,
        model=model,
        ok=ok,
        latency_seconds=latency_seconds,
        agent_id=agent_id,
        agent_name=agent_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        truncated=truncated,
        mock=mock,
    ))


def build_summary(
    registry: AnalysisUsage,
    price_table: dict[str, pricing.ModelPrice] | None = None,
) -> dict:
    """
    Arma el resumen agregable de un análisis: totales y desglose por
    (agente, modelo).

    Es una función pura sobre `registry.calls`: no toca el contexto ni el
    disco. `close_registry()` la usa para lo que escribe a JSONL.
    """
    grupos: dict[tuple[str | None, str | None, str], dict] = {}
    for call in registry.calls:
        clave = (call.agent_id, call.agent_name, call.model)
        grupo = grupos.setdefault(clave, {
            "agent_id": call.agent_id,
            "agent_name": call.agent_name,
            "model": call.model,
            "calls": 0,
            "failed_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "calls_without_usage": 0,
            "truncated_calls": 0,
            "mock_calls": 0,
        })
        grupo["calls"] += 1
        if not call.ok:
            grupo["failed_calls"] += 1
        if call.prompt_tokens is not None:
            grupo["prompt_tokens"] += call.prompt_tokens
        if call.completion_tokens is not None:
            grupo["completion_tokens"] += call.completion_tokens
        if call.ok and call.prompt_tokens is None:
            grupo["calls_without_usage"] += 1
        if call.truncated:
            grupo["truncated_calls"] += 1
        if call.mock:
            grupo["mock_calls"] += 1

    by_agent = list(grupos.values())
    _price_groups(by_agent, price_table)

    totales = {
        "calls": sum(g["calls"] for g in by_agent),
        "failed_calls": sum(g["failed_calls"] for g in by_agent),
        "prompt_tokens": sum(g["prompt_tokens"] for g in by_agent),
        "completion_tokens": sum(g["completion_tokens"] for g in by_agent),
        "calls_without_usage": sum(g["calls_without_usage"] for g in by_agent),
        "truncated_calls": sum(g["truncated_calls"] for g in by_agent),
        "mock_calls": sum(g["mock_calls"] for g in by_agent),
        "cost_usd": sum(g["cost_usd"] for g in by_agent),
        "unpriced_models": sorted({g["model"] for g in by_agent if not g["priced"]}),
    }

    return {
        "analysis_id": registry.analysis_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "totals": totales,
        "by_agent": by_agent,
    }


def _price_groups(
    by_agent: list[dict], price_table: dict[str, pricing.ModelPrice] | None
) -> None:
    """Calcula `cost_usd` y `priced` de cada grupo, en el lugar."""
    for grupo in by_agent:
        costo, tiene_tarifa = pricing.estimate_cost(
            grupo["prompt_tokens"], grupo["completion_tokens"], grupo["model"], price_table,
        )
        grupo["cost_usd"] = costo
        grupo["priced"] = tiene_tarifa


def recalculate(record: dict, price_table: dict[str, pricing.ModelPrice]) -> dict:
    """
    Recalcula el costo de un registro ya guardado con otra tabla de tarifas.

    Es lo que responde "¿cuánto costaría este mismo análisis con Claude
    Opus?" a partir de los tokens ya contados, sin correr nada (task 3.4). No
    muta `record`: devuelve una copia.
    """
    nuevo = copy.deepcopy(record)
    _price_groups(nuevo["by_agent"], price_table)
    nuevo["totals"]["cost_usd"] = sum(g["cost_usd"] for g in nuevo["by_agent"])
    nuevo["totals"]["unpriced_models"] = sorted(
        {g["model"] for g in nuevo["by_agent"] if not g["priced"]}
    )
    return nuevo


def close_registry(
    token: contextvars.Token,
    *,
    price_table: dict[str, pricing.ModelPrice] | None = None,
    output_path: Path | str | None = None,
    mock: bool = False,
) -> dict | None:
    """
    Cierra el registro activo, arma su resumen, lo agrega al JSONL y emite el
    resumen legible por stderr.

    Devuelve `None` si no había ningún registro activo (nada que cerrar). Un
    fallo al escribir el archivo (permisos, disco lleno, ruta inexistente)
    nunca rompe el análisis: se avisa por stderr y se sigue — la telemetría
    no puede ser condición para que `POST /api/analyze` funcione.
    """
    registry = _current.get()
    _current.reset(token)
    if registry is None:
        return None

    resumen = build_summary(registry, price_table)
    resumen["mock"] = mock

    # Resuelto acá, no como valor por defecto del parámetro: un default de
    # función se fija en la definición, así que un test que sobreescribe
    # `_DEFAULT_OUTPUT_PATH` (para no escribir en el output/ real del repo)
    # no tendría efecto si el valor quedara atado al importarse el módulo.
    destino = Path(output_path) if output_path is not None else _DEFAULT_OUTPUT_PATH

    try:
        _append_jsonl(resumen, destino)
    except OSError as exc:
        print(
            f"[NEXUS] telemetría: no se pudo escribir el registro de consumo "
            f"({type(exc).__name__}). El análisis continúa igual.",
            file=sys.stderr,
        )

    _print_summary(resumen)
    return resumen


def _append_jsonl(record: dict, output_path: Path | str) -> None:
    """Agrega una línea JSON al archivo, creando el directorio si hace falta."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_summary(record: dict) -> None:
    """Emite el resumen legible por stderr al terminar el análisis."""
    totales = record["totals"]
    total_tokens = totales["prompt_tokens"] + totales["completion_tokens"]
    aviso_mock = " [modo mock: sin llamadas reales al proveedor]" if record.get("mock") else ""
    aviso_sin_tarifa = (
        f" (sin tarifa: {', '.join(totales['unpriced_models'])})"
        if totales["unpriced_models"] else ""
    )
    print(
        f"[NEXUS] Consumo del análisis {record['analysis_id']}: "
        f"{totales['calls']} llamadas ({totales['failed_calls']} fallidas), "
        f"{total_tokens} tokens ({totales['prompt_tokens']} entrada / "
        f"{totales['completion_tokens']} salida), "
        f"costo estimado USD {totales['cost_usd']:.6f}{aviso_sin_tarifa}{aviso_mock}",
        file=sys.stderr,
    )
