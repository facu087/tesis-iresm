"""
Demo — Los tests de integración del RAG son herméticos (hallazgo B, tarjeta #75).

Corre tests/test_rag_integration.py y tests/test_rag.py con toda conexión de red
saliente bloqueada (plugin scripts/pytest_sin_red.py) y reporta cuántas
conexiones intentó cada archivo y cuánto tardó.

Medido antes del arreglo, con el mismo método:

    test_rag_integration.py   89 intentos de conexión   165 s
        39 a eutils.ncbi.nlm.nih.gov (PubMed)
        50 a huggingface.co (carga de PubMedBERT)
    test_rag.py                0 intentos                  4 s

Y pasaba igual con la red cortada: el texto de fallback del orquestador también
dice "LITERATURA CIENTÍFICA" y "evidence_level", que era todo lo que afirmaban
las aserciones. Contra un orquestador roto a propósito (la búsqueda del RAG
fallando siempre), los 6 tests viejos pasaban; de los nuevos fallan 2, los que
verifican que la literatura recuperada llega al agente.

No necesita conexión ni GROQ_API_KEY.

    python scripts/demo_tests_rag_hermeticos.py

Artefactos en output/demo_tests_rag_hermeticos/:
    resultado.txt  → salida de pytest con el detalle de conexiones por archivo
    resumen.json   → los números en JSON
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_RAIZ = Path(__file__).parent.parent
_OUT_DIR = _RAIZ / "output" / "demo_tests_rag_hermeticos"
_SEP = "═" * 78

_ARCHIVOS = ["tests/test_rag_integration.py", "tests/test_rag.py"]

_ANTES = {
    "tests/test_rag_integration.py": {"conexiones": 89, "segundos": 165.2},
    "tests/test_rag.py": {"conexiones": 0, "segundos": 4.0},
}


def _correr(archivo: str) -> dict:
    """Corre pytest sobre un archivo con la red bloqueada y parsea el resultado."""
    entorno = dict(os.environ, PYTHONPATH=str(_RAIZ / "scripts"), PYTHONIOENCODING="utf-8")
    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", archivo, "-q", "-p", "no:cacheprovider",
         "-p", "pytest_sin_red"],
        cwd=_RAIZ, env=entorno, capture_output=True, text=True, encoding="utf-8",
    )
    salida = proceso.stdout + proceso.stderr

    conexiones = re.search(r"intentos de conexión bloqueados: (\d+)", salida)
    pasaron = re.search(r"(\d+) passed", salida)
    fallaron = re.search(r"(\d+) failed", salida)
    tiempo = re.search(r"in ([\d.]+)s", salida)
    hosts = re.findall(r"\[sin_red\]\s+-> (.+)", salida)

    return {
        "archivo": archivo,
        "conexiones": int(conexiones.group(1)) if conexiones else None,
        "hosts": hosts,
        "pasaron": int(pasaron.group(1)) if pasaron else 0,
        "fallaron": int(fallaron.group(1)) if fallaron else 0,
        "segundos": float(tiempo.group(1)) if tiempo else None,
        "salida": salida,
    }


def main() -> None:
    print(_SEP)
    print("DEMO — Tests de integración del RAG con la red bloqueada")
    print(_SEP)

    resultados = [_correr(a) for a in _ARCHIVOS]

    print(f"\n{'Archivo':32} {'Conexiones':>22} {'Tiempo':>20} {'Resultado':>14}")
    print(f"{'':32} {'antes → ahora':>22} {'antes → ahora':>20}")
    print("─" * 78)
    for r in resultados:
        antes = _ANTES[r["archivo"]]
        conexiones = f"{antes['conexiones']} → {r['conexiones']}"
        tiempo = f"{antes['segundos']:.1f}s → {r['segundos']:.2f}s" if r["segundos"] else "?"
        estado = f"{r['pasaron']} ok" + (f", {r['fallaron']} fallan" if r["fallaron"] else "")
        print(f"{r['archivo']:32} {conexiones:>22} {tiempo:>20} {estado:>14}")
        for h in r["hosts"]:
            print(f"{'':34}↳ {h}")

    hermetico = all(r["conexiones"] == 0 and r["fallaron"] == 0 for r in resultados)
    print(f"\n{'✔' if hermetico else '✘'} " + (
        "Ningún test del RAG intenta conectarse a la red."
        if hermetico else
        "Hay tests que todavía intentan conectarse o fallan sin red."
    ))

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "resultado.txt").write_text(
        "\n\n".join(f"===== {r['archivo']} =====\n{r['salida']}" for r in resultados),
        encoding="utf-8",
    )
    (_OUT_DIR / "resumen.json").write_text(
        json.dumps(
            {"antes": _ANTES,
             "ahora": {r["archivo"]: {k: r[k] for k in ("conexiones", "hosts", "pasaron",
                                                         "fallaron", "segundos")}
                       for r in resultados},
             "hermetico": hermetico},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nArtefactos: {_OUT_DIR}")
    print(_SEP)
    sys.exit(0 if hermetico else 1)


if __name__ == "__main__":
    main()
