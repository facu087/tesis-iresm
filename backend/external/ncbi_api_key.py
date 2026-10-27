"""
Lectura validada de PUBMED_API_KEY, la clave de las E-utilities de NCBI.

La comparten el cliente de PubMed, el de ClinVar y el limitador de velocidad
de NCBI (`rate_limiter.pubmed_limiter`). Vive en un módulo sin dependencias
para que los tres la usen sin importarse entre sí (tarjeta #79).
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

ENV_API_KEY_VAR = "PUBMED_API_KEY"

# Las claves de NCBI son alfanuméricas. El patrón es deliberadamente laxo —no
# valida el largo exacto— porque el objetivo no es adivinar el formato de NCBI
# sino descartar lo que evidentemente NO es una clave: un comentario, una ruta,
# una frase con espacios.
_API_KEY_VALIDA = re.compile(r"^[A-Za-z0-9]{8,64}$")


def leer_api_key() -> Optional[str]:
    """
    Lee PUBMED_API_KEY del entorno y la descarta si no parece una clave.

    Por qué hace falta validar algo "opcional": si en el `.env` la variable
    quedó escrita con el comentario en la misma línea —

        PUBMED_API_KEY=            # Opcional: aumenta el rate limit

    — python-dotenv carga el comentario entero como valor. Ese texto viajaba
    como `api_key` a PubMed, la API respondía 400 y `verify_report_sources()`
    caía al `except`, marcando **todas** las fuentes como `no_verificable`.

    El efecto era desproporcionado y silencioso: la verificación bibliográfica
    es lo que detecta que los agentes alucinan PMIDs, y un typo en el `.env` la
    desactivaba entera sin un solo error visible. El reporte salía igual, con
    HTTP 200, con todas las hipótesis en `pendiente` en vez de `respaldada` o
    `especulativa`, y sin Ronda 5 de recitación. Una corrida real de 450 s y su
    cuota de Groq se perdieron así, y solo se notó leyendo el log del backend.

    Ante una clave con formato inválido se avisa por stderr y se sigue **sin
    clave**: PubMed funciona igual a 3 req/s en vez de 10. Degradar el rate
    limit es mucho mejor que apagar la verificación.

    Returns:
        La clave sin espacios alrededor, o None si falta, está vacía o no
        tiene formato de clave.
    """
    crudo = os.getenv(ENV_API_KEY_VAR)
    if crudo is None:
        return None

    clave = crudo.strip()
    if not clave:
        return None

    if not _API_KEY_VALIDA.match(clave):
        # Solo el largo: puede ser una clave real mal copiada, y ni su
        # comienzo debe quedar en el log.
        print(
            f"[NEXUS][PubMed] {ENV_API_KEY_VAR} no parece una clave válida "
            f"(se leyeron {len(clave)} caracteres). "
            f"Revisá que en el .env el comentario no esté en la misma línea. "
            f"Se continúa SIN clave: la verificación sigue funcionando, a 3 "
            f"req/s en vez de 10.",
            file=sys.stderr,
        )
        return None

    return clave
