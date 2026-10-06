"""
Demo — La anonimización antes de que el texto salga del sistema (tarjeta #55).

Prueba que ningún identificador del paciente llega al modelo de lenguaje.

Cómo: se corre el pipeline COMPLETO (`POST /api/analyze`, con un médico
verificado, en memoria) sobre un caso al que se le inyectaron identificadores
—nombre, DNI, teléfono, correo, domicilio, fecha de nacimiento, historia
clínica, nombre del médico derivante— interceptando `call_provider()`, el
único punto por el que el sistema habla con el modelo. Cada prompt que sale
queda registrado y se revisa.

Se hace DOS veces, y la segunda es el control:

  1. Con la anonimización activa  → no debería filtrarse nada.
  2. Con la anonimización apagada → los identificadores SÍ tienen que aparecer.

Sin el control, "0 fugas" podría significar que el instrumento no ve nada. Que
detecte las fugas cuando las hay es lo que le da valor al resultado.

Corre en modo mock: sin Groq, sin cuota, sin red hacia el modelo. No lo cambies
a modo real a propósito: una corrida real gasta ~80.000 tokens y acá se corre
dos veces.

    python scripts/demo_anonimizacion.py

Artefactos en output/demo_anonimizacion/:
    resultado.txt → la comparación con y sin anonimización
    resumen.json  → los números y los hallazgos por identificador

Sale con código 1 si con la anonimización activa se filtra algo.
"""

import json
import os
import re
import sys
from pathlib import Path

# El modo mock se fuerza ANTES de importar el backend: load_dotenv() no pisa
# variables ya definidas, así que esto gana aunque el .env tenga el modo real.
os.environ["NEXUS_MOCK_LLM"] = "1"
os.environ.setdefault("SECRET_KEY", "clave-demo-anonimizacion-no-usar-en-produccion")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from backend import db as db_module
from backend.auth.security import hash_password
from backend.models.cuenta import CuentaMedico, EstadoCuenta, RolCuenta

# Defensa en profundidad: aun en modo mock, sin clave del proveedor en el entorno.
os.environ.pop("GROQ_API_KEY", None)

_ORIGEN = "http://localhost:3000"
_SEP = "═" * 78
_SUB = "─" * 78
_OUT_DIR = _RAIZ / "output" / "demo_anonimizacion"

# Cada identificador, tal como se escribió en el documento y en la forma en que
# podría reaparecer si se filtrara. Se busca sin distinguir mayúsculas.
_IDENTIFICADORES = {
    "nombre del paciente": ["Juan Carlos Pérez", "Juan Carlos Perez", "Pérez, Juan"],
    "apellido": ["Pérez", "Perez"],
    "DNI": ["32.456.789", "32456789"],
    "teléfono": ["155-678901", "155678901", "0351 155"],
    "correo": ["jcperez@example.com", "jcperez"],
    "domicilio": ["Av. Colón 1234", "Colón 1234"],
    "fecha de nacimiento": ["14/07/1983"],
    "historia clínica": ["HC-44821", "44821"],
    "médica derivante": ["María Elena Gutiérrez", "Gutiérrez"],
}

_ENCABEZADO = """Paciente: Juan Carlos Pérez. DNI 32.456.789. Historia clínica N° HC-44821.
Fecha de nacimiento: 14/07/1983.
Domicilio: Av. Colón 1234, Villa Carlos Paz
Tel: 0351 155-678901. Email: jcperez@example.com.
Derivado por la Dra. María Elena Gutiérrez.

"""


def _caso_base() -> str:
    fuente = (_RAIZ / "scripts" / "poc_test.py").read_text(encoding="utf-8")
    return re.search(r'CASO_CLINICO = """(.*?)"""', fuente, re.S).group(1).strip()


def _preparar_cliente() -> TestClient:
    """Base en memoria con un médico verificado, y sesión iniciada."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db_module.set_engine(engine)
    db_module.create_db_and_tables(bind=engine)
    with Session(engine) as s:
        s.add(CuentaMedico(
            nombre="Ana", apellido="Demo", dni="30111222", matricula="12345",
            jurisdiccion="Córdoba", email="demo@anonimizacion.example",
            password_hash=hash_password("ContraseñaDeDemo123"),
            rol=RolCuenta.MEDICO, estado=EstadoCuenta.VERIFICADO,
        ))
        s.commit()

    from backend.main import app

    cliente = TestClient(app, headers={"Origin": _ORIGEN})
    cliente.__enter__()
    r = cliente.post("/api/login", json={
        "email": "demo@anonimizacion.example", "password": "ContraseñaDeDemo123"})
    assert r.status_code == 200, r.text
    return cliente


def _interceptar_llamadas() -> list[str]:
    """
    Envuelve `call_provider()` en los tres módulos que lo importan por nombre y
    devuelve la lista donde se acumulan los prompts salientes.
    """
    import backend.agents.base_agent as base_agent
    import backend.ingestion.biomarker_extractor as biomarcadores
    import backend.pipeline.pico as pico

    salientes: list[str] = []
    original = base_agent.call_provider

    def espia(*args, **kwargs):
        salientes.append(f"{kwargs.get('system_prompt', '')}\n{kwargs.get('user_message', '')}")
        return original(*args, **kwargs)

    for modulo in (base_agent, biomarcadores, pico):
        modulo.call_provider = espia
    return salientes


def _restaurar(original) -> None:
    import backend.agents.base_agent as base_agent
    import backend.ingestion.biomarker_extractor as biomarcadores
    import backend.pipeline.pico as pico

    for modulo in (base_agent, biomarcadores, pico):
        modulo.call_provider = original


def _correr(cliente: TestClient, anonimizar_activo: bool) -> dict:
    """Corre el pipeline completo y revisa cada prompt saliente."""
    import backend.agents.base_agent as base_agent
    import backend.api.router as router

    original_call = base_agent.call_provider
    original_anon = router.anonimizar
    if not anonimizar_activo:
        # El control: la función existe pero no hace nada.
        router.anonimizar = lambda texto: (texto, original_anon("")[1])

    salientes = _interceptar_llamadas()
    try:
        respuesta = cliente.post(
            "/api/analyze", data={"text": _ENCABEZADO + _caso_base()}, timeout=900)
    finally:
        _restaurar(original_call)
        router.anonimizar = original_anon

    assert respuesta.status_code == 200, f"HTTP {respuesta.status_code}: {respuesta.text[:200]}"

    hallazgos: dict[str, int] = {}
    for categoria, variantes in _IDENTIFICADORES.items():
        n = sum(
            1 for prompt in salientes
            if any(v.lower() in prompt.lower() for v in variantes)
        )
        hallazgos[categoria] = n

    reporte = json.dumps(respuesta.json(), ensure_ascii=False).lower()
    en_reporte = [c for c, vs in _IDENTIFICADORES.items()
                  if any(v.lower() in reporte for v in vs)]

    return {
        "prompts_salientes": len(salientes),
        "prompts_con_etiquetas": sum(1 for p in salientes if "[NOMBRE]" in p or "[DOCUMENTO]" in p),
        "prompts_con_fuga": sum(
            1 for p in salientes
            if any(v.lower() in p.lower() for vs in _IDENTIFICADORES.values() for v in vs)),
        "fugas_por_identificador": hallazgos,
        "identificadores_en_el_reporte": en_reporte,
    }


def main() -> None:
    lineas: list[str] = []

    def emitir(texto: str = "") -> None:
        print(texto)
        lineas.append(texto)

    emitir(_SEP)
    emitir("DEMO — Anonimización: ¿qué identificadores llegan al modelo de lenguaje?")
    emitir(_SEP)
    emitir("\nENTRADA — encabezado inyectado al caso clínico de la tesis:\n")
    for l in _ENCABEZADO.strip().splitlines():
        emitir(f"    {l}")
    emitir(f"\n  + el caso base de neuropatía axonal (varón de 42 años), sin tocar.")
    emitir("\nModo mock (sin Groq ni cuota). Cada prompt saliente se intercepta en call_provider().")

    cliente = _preparar_cliente()
    try:
        emitir(f"\n{_SUB}\n1. CON la anonimización activa\n{_SUB}")
        con = _correr(cliente, anonimizar_activo=True)
        emitir(f"  prompts enviados al modelo : {con['prompts_salientes']}")
        emitir(f"  prompts con etiquetas      : {con['prompts_con_etiquetas']}  "
               f"(llevan [NOMBRE], [DOCUMENTO]... en lugar del dato)")
        emitir(f"  prompts con identificadores: {con['prompts_con_fuga']}")
        for cat, n in con["fugas_por_identificador"].items():
            emitir(f"      {cat:22} {'SE FILTRA en %d' % n if n else 'no aparece'}")
        emitir(f"  en el reporte final        : "
               f"{con['identificadores_en_el_reporte'] or 'ninguno'}")

        emitir(f"\n{_SUB}\n2. SIN la anonimización (control del instrumento)\n{_SUB}")
        sin = _correr(cliente, anonimizar_activo=False)
        emitir(f"  prompts enviados al modelo : {sin['prompts_salientes']}")
        emitir(f"  prompts con identificadores: {sin['prompts_con_fuga']}")
        for cat, n in sin["fugas_por_identificador"].items():
            emitir(f"      {cat:22} {'SE FILTRA en %d prompts' % n if n else 'no aparece'}")
    finally:
        cliente.__exit__(None, None, None)

    sin_fuga = con["prompts_con_fuga"] == 0 and not con["identificadores_en_el_reporte"]
    instrumento_valido = sin["prompts_con_fuga"] > 0

    emitir(f"\n{_SEP}")
    emitir(f"{'[OK]' if sin_fuga else '[X]'} Con anonimización: "
           f"{con['prompts_con_fuga']} de {con['prompts_salientes']} prompts con identificadores.")
    emitir(f"{'[OK]' if instrumento_valido else '[X]'} Sin anonimización: "
           f"{sin['prompts_con_fuga']} de {sin['prompts_salientes']} prompts con identificadores"
           f" — el instrumento {'detecta' if instrumento_valido else 'NO detecta'} las fugas.")
    emitir("\nAlcance: reglas deterministas sobre identificadores directos. Un nombre suelto,")
    emitir("sin marcador que lo anuncie, no se detecta (ver docstring del módulo).")
    emitir(_SEP)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "resultado.txt").write_text("\n".join(lineas), encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(json.dumps(
        {"con_anonimizacion": con, "sin_anonimizacion": sin,
         "sin_fuga": sin_fuga, "instrumento_valido": instrumento_valido},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nArtefactos: {_OUT_DIR}")

    sys.exit(0 if (sin_fuga and instrumento_valido) else 1)


if __name__ == "__main__":
    main()
