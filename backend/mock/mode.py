"""
Activación del modo mock del pipeline (control de costos, Sprint 4 — D7).

El modo mock reemplaza las llamadas al proveedor del LLM por respuestas
grabadas, para poder iterar en desarrollo sobre el pipeline sin gastar cuota
ni tocar la red. Se activa por variable de entorno, **apagado por defecto**,
y nunca por inferencia: que falte `GROQ_API_KEY` es un error de
configuración que tiene que fallar con un mensaje claro, no una señal para
caer en silencio a respuestas grabadas (spec `modo-mock-pipeline`,
"Activación explícita").
"""

import os

ENV_VAR = "NEXUS_MOCK_LLM"

_VALORES_APAGADO = frozenset({"", "0", "false", "no"})


def is_mock_active() -> bool:
    """
    True si el modo mock está activo.

    Cualquier valor de `NEXUS_MOCK_LLM` distinto de vacío/"0"/"false"/"no"
    (sin distinguir mayúsculas) lo activa. No definida: apagado, que es el
    default.
    """
    valor = os.environ.get(ENV_VAR, "").strip().lower()
    return valor not in _VALORES_APAGADO
