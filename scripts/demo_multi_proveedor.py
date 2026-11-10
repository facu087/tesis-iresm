"""
Demo — Proveedor por agente con respaldo en Groq (Sprint 5, OpenSpec
`multi-proveedor-por-agente`).

La arquitectura de la tesis asigna un modelo a cada agente: Claude Opus a los
Agentes 01, 04 y 06, GPT-4o al 02 y Gemini Pro al 03. Con
`NEXUS_PROVEEDORES=destino`, `call_provider()` manda cada llamada al proveedor
de su agente; si falta la clave o el proveedor falla, la repite en Groq y lo
registra. Sin esa variable, todo va a Groq como siempre.

Este script corre sin red ni cuota: los clientes de Anthropic, OpenAI, Google y
Groq se reemplazan por dobles que responden un texto fijo. Hace una llamada por
agente (01, 02, 03, 04, 06), una del Agente 05 y la síntesis PICO, en cuatro
casos:

  1. todo en groq:            sin NEXUS_PROVEEDORES, con las tres claves cargadas
  2. destino con las claves:  cada agente en su proveedor
  3. destino sin Google:      el Agente 03 cae al respaldo por clave faltante
  4. Anthropic fallando:      los Agentes 01, 04 y 06 caen al respaldo por falla

  entrada: variables de entorno del caso
  salida:  quién recibió cada llamada, avisos de stderr y el bloque
           `metadata.proveedores` que llevaría el reporte

    python scripts/demo_multi_proveedor.py

Artefactos en output/demo_multi_proveedor/:
    resultado.txt  → la corrida completa
    resumen.json   → proveedor por agente en cada caso y comprobaciones

Sale con código 1 si algún caso no da lo esperado.
"""

import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import anthropic  # noqa: E402
import httpx2  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

from backend.agents.base_agent import call_provider  # noqa: E402
from backend.agents.model_tasks import GROQ_FAST, GROQ_MAIN  # noqa: E402
from backend.telemetry import usage  # noqa: E402

_OUT_DIR = _RAIZ / "output" / "demo_multi_proveedor"
_SEP = "═" * 78
_lineas: list[str] = []

# Una llamada por agente, más dos que no son de un agente con proveedor.
_LLAMADAS = (
    ("agente01_hipotesis", "01", "Analista de Literatura", GROQ_MAIN),
    ("agente02_hipotesis", "02", "Especialista Genómica", GROQ_MAIN),
    ("agente03_hipotesis", "03", "Consultor Clínico", GROQ_MAIN),
    ("arbitro_veredictos", "04", "Árbitro Verificador", GROQ_MAIN),
    ("agente06_sintesis", "06", "Sintetizador", GROQ_MAIN),
    ("agente05_planificacion_terminos", "05", "Navegador de Ensayos", GROQ_FAST),
    ("pico_sintesis", None, None, GROQ_MAIN),
)

_CLAVES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")
_VARIABLES = ("NEXUS_PROVEEDORES", "NEXUS_MOCK_LLM", "GROQ_API_KEY", *_CLAVES)

_DESTINO = {"01": "anthropic", "02": "openai", "03": "google", "04": "anthropic",
            "06": "anthropic", "05": "groq"}
_TODO_GROQ = {agente: "groq" for agente in _DESTINO}

# Caso → (variables de entorno, ¿Anthropic falla?, proveedor esperado por agente,
#         motivo de respaldo esperado por agente)
_CASOS = {
    "1. todo en groq": (
        {"GROQ_API_KEY": "g", "ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o",
         "GOOGLE_API_KEY": "go"},
        False, _TODO_GROQ, {},
    ),
    "2. destino con las tres claves": (
        {"NEXUS_PROVEEDORES": "destino", "GROQ_API_KEY": "g", "ANTHROPIC_API_KEY": "a",
         "OPENAI_API_KEY": "o", "GOOGLE_API_KEY": "go"},
        False, _DESTINO, {},
    ),
    "3. destino sin la clave de Google": (
        {"NEXUS_PROVEEDORES": "destino", "GROQ_API_KEY": "g", "ANTHROPIC_API_KEY": "a",
         "OPENAI_API_KEY": "o"},
        False, {**_DESTINO, "03": "groq"}, {"03": "clave_faltante"},
    ),
    "4. destino con Anthropic fallando": (
        {"NEXUS_PROVEEDORES": "destino", "GROQ_API_KEY": "g", "ANTHROPIC_API_KEY": "a",
         "OPENAI_API_KEY": "o", "GOOGLE_API_KEY": "go"},
        True, {**_DESTINO, "01": "groq", "04": "groq", "06": "groq"},
        {"01": "falla", "04": "falla", "06": "falla"},
    ),
}


def _p(texto: str = "") -> None:
    """Imprime y guarda la línea para resultado.txt."""
    print(texto)
    _lineas.append(texto)


def _respuesta_chat(texto: str):
    respuesta = MagicMock()
    respuesta.choices = [MagicMock(message=MagicMock(content=texto, refusal=None),
                                   finish_reason="stop")]
    respuesta.usage = MagicMock(prompt_tokens=1000, completion_tokens=500)
    return respuesta


def _dobles(anthropic_falla: bool):
    """Clientes falsos de los cuatro SDK y el contador de quién recibió qué."""
    recibidas: list[str] = []

    @contextlib.contextmanager
    def stream(**_pedido):
        recibidas.append("anthropic")
        if anthropic_falla:
            respuesta = httpx2.Response(
                529, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"),
            )
            raise anthropic.APIStatusError("overloaded", response=respuesta, body=None)
        yield SimpleNamespace(get_final_message=lambda: SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="{}")],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=2000),
        ))

    def cliente_chat(nombre: str):
        cliente = MagicMock()

        def crear(**_pedido):
            recibidas.append(nombre)
            return _respuesta_chat("{}")

        cliente.chat.completions.create.side_effect = crear
        return cliente

    google = MagicMock()

    def generar(**_pedido):
        recibidas.append("google")
        return SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=genai_types.FinishReason.STOP)],
            text="{}",
            usage_metadata=SimpleNamespace(prompt_token_count=1000,
                                           candidates_token_count=500,
                                           thoughts_token_count=800),
        )

    google.models.generate_content.side_effect = generar
    parches = (
        patch("anthropic.Anthropic",
              lambda **_kw: SimpleNamespace(messages=SimpleNamespace(stream=stream))),
        patch("openai.OpenAI", MagicMock(return_value=cliente_chat("openai"))),
        patch("google.genai.Client", MagicMock(return_value=google)),
        patch("groq.Groq", MagicMock(return_value=cliente_chat("groq"))),
    )
    return parches, recibidas


def _correr_caso(nombre: str, entorno: dict[str, str], anthropic_falla: bool,
                 esperado: dict[str, str], motivos: dict[str, str]) -> dict:
    """Corre las siete llamadas de un caso y compara con lo esperado."""
    _p(_SEP)
    _p(f"CASO {nombre}")
    _p(_SEP)
    _p("Entrada:")
    _p(f"  NEXUS_PROVEEDORES = {entorno.get('NEXUS_PROVEEDORES', '(sin definir)')}")
    _p(f"  claves cargadas   = {', '.join(c for c in _CLAVES if c in entorno) or 'ninguna'}")
    _p(f"  Anthropic         = {'falla (529)' if anthropic_falla else 'responde'}")

    for variable in _VARIABLES:
        os.environ.pop(variable, None)
    os.environ.update(entorno)

    parches, recibidas = _dobles(anthropic_falla)
    stderr = io.StringIO()
    token = usage.open_registry()
    registro = usage.current()
    proveedor_por_llamada: dict[str, str] = {}
    try:
        with contextlib.ExitStack() as pila, contextlib.redirect_stderr(stderr):
            for parche in parches:
                pila.enter_context(parche)
            for tarea, agente, nombre_agente, modelo in _LLAMADAS:
                antes = len(recibidas)
                call_provider(system_prompt="s", user_message="caso anonimizado",
                              model=modelo, max_tokens=4096, task=tarea,
                              agent_id=agente, agent_name=nombre_agente)
                proveedor_por_llamada[agente or "pico"] = " → ".join(recibidas[antes:])
        bloque = usage.providers_by_agent(registro)
        costo = usage.build_summary(registro)["totals"]["cost_usd"]
    finally:
        usage._current.reset(token)

    _p("")
    _p("Salida — quién recibió cada llamada:")
    for tarea, agente, _nombre, _modelo in _LLAMADAS:
        _p(f"  {(agente or 'PICO'):>4}  {tarea:<34} {proveedor_por_llamada[agente or 'pico']}")
    _p("")
    _p("Avisos en stderr:")
    avisos = [linea for linea in stderr.getvalue().splitlines() if "respaldo" in linea]
    for linea in avisos or ["  (ninguno)"]:
        _p(f"  {linea}")
    _p("")
    _p("Bloque metadata.proveedores del reporte:")
    for entrada in bloque:
        motivo = f"  respaldo: {entrada['fallback_reason']}" if entrada["fallback_reason"] else ""
        _p(f"  {entrada['agent_id']}  {entrada['provider']:<10} {entrada['model']:<24}{motivo}")
    _p(f"Costo estimado con las tarifas de cada proveedor: USD {costo:.4f}")

    obtenido = {e["agent_id"]: e["provider"] for e in bloque}
    obtenidos_motivos = {e["agent_id"]: e["fallback_reason"] for e in bloque
                         if e["fallback_reason"]}
    comprobaciones = {
        "proveedor por agente": obtenido == esperado,
        "motivos de respaldo": obtenidos_motivos == motivos,
        "PICO en Groq": proveedor_por_llamada["pico"] == "groq",
        "un aviso por proveedor y motivo": len(avisos) == len({(e["provider"], m) for e in bloque
                                                               for m in [e["fallback_reason"]]
                                                               if m}),
        "sin el mensaje del error en stderr": "overloaded" not in stderr.getvalue(),
    }
    _p("")
    for nombre_comprobacion, ok in comprobaciones.items():
        _p(f"  [{'OK' if ok else 'FALLA'}] {nombre_comprobacion}")
    _p("")
    return {"proveedores": bloque, "avisos": avisos, "costo_usd": costo,
            "comprobaciones": comprobaciones}


def main() -> int:
    """Corre los cuatro casos, guarda los artefactos y devuelve el código de salida."""
    guardado = {variable: os.environ.get(variable) for variable in _VARIABLES}
    try:
        resultados = {nombre: _correr_caso(nombre, *caso) for nombre, caso in _CASOS.items()}
    finally:
        for variable, valor in guardado.items():
            if valor is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = valor

    fallas = [f"{caso}: {c}" for caso, r in resultados.items()
              for c, ok in r["comprobaciones"].items() if not ok]
    _p(_SEP)
    _p("[OK] Los cuatro casos dan lo esperado." if not fallas
       else "[FALLA] " + "; ".join(fallas))
    _p(_SEP)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "resultado.txt").write_text("\n".join(_lineas) + "\n", encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"\nArtefactos: {_OUT_DIR}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
