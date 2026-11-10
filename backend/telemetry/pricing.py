"""
Tarifas por modelo, para estimar el costo de un análisis a partir de sus
tokens (control de costos, Sprint 4 — D5).

Los valores de Groq son cero: es el tier gratuito que usa el sistema por
defecto. Los de la arquitectura de destino (Claude Opus, GPT-4o, Gemini Pro —
`NEXUS_PROVEEDORES=destino`, Sprint 5) son los de lista pública al 2026-11-09:
con esa arquitectura activa, el resumen de un análisis ya informa su costo
real. Si el modelo de un proveedor se cambia por variable de entorno
(`NEXUS_MODELO_*`) y no figura acá, el análisis sigue y el modelo queda
señalado como sin tarifa.

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
    # Arquitectura de destino. Precios de lista revisados el 2026-11-09: tabla
    # de modelos de Anthropic al 2026-11-03 (Claude Opus 5.5),
    # developers.openai.com/api/docs/pricing
    # (GPT-4o) y ai.google.dev/gemini-api/docs/pricing (Gemini 3.1 Pro Preview,
    # tramo de prompts de hasta 200k tokens: un caso clínico no lo supera).
    "claude-opus-5-5": ModelPrice(input_per_million=4.0, output_per_million=20.0),
    "gpt-4o": ModelPrice(input_per_million=2.5, output_per_million=10.0),
    "gemini-3.1-pro-preview": ModelPrice(input_per_million=2.0, output_per_million=12.0),
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
