"""
Tarifas por modelo, para estimar el costo de un análisis a partir de sus
tokens (control de costos, Sprint 4 — D5).

Los valores de Groq son cero: es el tier gratuito que usa el sistema hoy. Los
de la arquitectura de destino (Claude Opus, GPT-4o, Gemini Pro — ver
`.claude/CLAUDE.md`, sección "Modelo de IA") quedan comentados como
referencia: activarlos es cargar la tarifa real cuando se haga el swap de
proveedor.

El valor real de la tabla no es contar lo que Groq no cobra: es poder
responder "¿cuánto costaría este mismo caso con Claude Opus?" recalculando
sobre un registro ya guardado (`usage.recalculate()`), sin correr nada.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class ModelPrice:
    """Tarifa de un modelo, en USD por millón de tokens."""

    input_per_million: float
    output_per_million: float


# Tarifas por defecto. Un modelo que no figura acá se reporta con costo cero
# y queda señalado como sin tarifa (D5): que falte un precio no puede tumbar
# un análisis clínico.
DEFAULT_PRICES: dict[str, ModelPrice] = {
    "openai/gpt-oss-120b": ModelPrice(input_per_million=0.0, output_per_million=0.0),
    "openai/gpt-oss-20b": ModelPrice(input_per_million=0.0, output_per_million=0.0),
    # Arquitectura de destino — comentados a propósito. Los valores son de
    # lista pública al momento de escribir esto y hay que revisarlos antes de
    # usarlos para el capítulo de viabilidad de la tesis.
    # "claude-opus-4-...": ModelPrice(input_per_million=15.0, output_per_million=75.0),
    # "gpt-4o": ModelPrice(input_per_million=2.5, output_per_million=10.0),
    # "gemini-1.5-pro": ModelPrice(input_per_million=1.25, output_per_million=5.0),
}


def price_for(
    model: str, table: dict[str, ModelPrice] | None = None
) -> ModelPrice | None:
    """Tarifa configurada de un modelo, o `None` si no figura en la tabla."""
    tabla = table if table is not None else DEFAULT_PRICES
    return tabla.get(model)


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    table: dict[str, ModelPrice] | None = None,
) -> tuple[float, bool]:
    """
    Estima el costo en USD de un consumo de tokens para un modelo dado.

    Args:
        prompt_tokens:     Tokens de entrada acumulados.
        completion_tokens: Tokens de salida acumulados.
        model:              Modelo del proveedor.
        table:              Tabla de tarifas a usar. Por defecto, `DEFAULT_PRICES`.

    Returns:
        Tupla `(costo_usd, tiene_tarifa)`. Un modelo sin tarifa configurada
        devuelve `(0.0, False)`, nunca una excepción: el costo del análisis
        completo se sigue pudiendo calcular igual, solo que ese modelo queda
        señalado como sin tarifa.
    """
    precio = price_for(model, table)
    if precio is None:
        return 0.0, False
    costo = (
        (prompt_tokens / 1_000_000) * precio.input_per_million
        + (completion_tokens / 1_000_000) * precio.output_per_million
    )
    return costo, True
