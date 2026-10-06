"""
Genera un archivo de respuestas del modo mock a partir de una grabación.

Convierte el `grabacion.json` que deja `scripts/medir_costos.py --grabar` en un
archivo con la forma de `backend/mock/grabadas.json`, con todas las respuestas
de cada tarea. La conversión vive en `backend/mock/regenerar.py`; esto es solo
la entrada por línea de comandos. No llama al modelo ni usa la red.

Las dos rutas son obligatorias: no hay destino por defecto, así que el archivo
versionado solo se reemplaza si se pasa su ruta a propósito. Si la grabación no
es válida no se escribe nada.

Uso:
    python3 scripts/regenerar_mock.py output/medicion_costos/grabacion.json salida.json
    python3 scripts/regenerar_mock.py grabacion.json salida.json --fecha 2026-10-06

Después de reemplazar `backend/mock/grabadas.json` hay que correr
`pytest tests/test_mock_responses.py`: verifica que cada respuesta atraviese el
parseo real de su sitio de llamada, cosa que este script no puede comprobar.
Las respuestas pueden contener texto del caso: revisarlas antes de versionarlas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

from backend.mock import regenerar
from backend.mock.responses import RespuestasGrabadasInvalidas


def main(argv: list[str] | None = None) -> int:
    """Devuelve 0 si escribió el archivo y 2 si la grabación no se pudo usar."""
    parser = argparse.ArgumentParser(
        description="Genera el archivo de respuestas del modo mock desde una grabación."
    )
    parser.add_argument("grabacion", type=Path,
                        help="grabacion.json de scripts/medir_costos.py --grabar")
    parser.add_argument("salida", type=Path,
                        help="archivo a escribir (se reemplaza si ya existe)")
    parser.add_argument("--fecha", default=None,
                        help="fecha de la corrida, AAAA-MM-DD (por defecto, la de la grabación)")
    args = parser.parse_args(argv)

    try:
        resumen = regenerar.regenerar_archivo(
            args.grabacion, args.salida, recorded_at=args.fecha
        )
    except (regenerar.GrabacionInvalida, RespuestasGrabadasInvalidas) as exc:
        print(f"ERROR: {exc}. No se escribió ningún archivo.", file=sys.stderr)
        return 2

    print(
        f"[regenerar_mock] {resumen['entries']} respuesta(s) de {resumen['tasks']} "
        f"tarea(s) en {args.salida}",
        file=sys.stderr,
    )
    if resumen["truncated"]:
        print(
            f"[regenerar_mock] ADVERTENCIA: {resumen['truncated']} respuesta(s) cortada(s) "
            "por el techo de tokens; es probable que no atraviesen el parseo.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
