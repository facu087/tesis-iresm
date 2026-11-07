"""
Demo — Endurecimiento HTTP: CORS, encabezados de seguridad y producción (tarjeta #57).

Muestra, sin red ni cuota, qué cambió respecto de la configuración anterior:

  1. ALLOWED_ORIGINS: qué valores se aceptan y cuáles hacen que el servidor no
     arranque. Incluye el caso `*`, que antes se aceptaba.
  2. CORS: un preflight por cada caso, contra la configuración ANTERIOR
     (reconstruida: métodos y headers "*") y contra la aplicación real.
  3. El riesgo concreto del `*` con credenciales, medido en la configuración
     anterior: cualquier sitio recibe permiso para leer con la cookie.
  4. Encabezados de seguridad en una respuesta real.
  5. Producción: HSTS, documentación apagada, http rechazado fuera de localhost.

    python scripts/demo_seguridad_http.py

Artefactos en output/demo_seguridad_http/:
    resultado.txt → la corrida completa
    resumen.json  → los números

Sale con código 1 si alguna comprobación falla.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.pop("ENVIRONMENT", None)
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ.pop("ALLOWED_HOSTS", None)
os.environ.setdefault("SECRET_KEY", "clave-demo-seguridad-no-usar-en-produccion")

_RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(_RAIZ))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.seguridad import ConfiguracionInsegura, origenes_permitidos

_SEP = "═" * 78
_SUB = "─" * 78
_OUT_DIR = _RAIZ / "output" / "demo_seguridad_http"
_PERMITIDO = "http://localhost:3000"
_AJENO = "https://sitio-malicioso.example"


def _app_anterior(origenes: list[str]) -> TestClient:
    """La configuración de CORS de `main.py` antes del cambio, tal cual estaba."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware, allow_origins=origenes, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/api/cuenta")
    def cuenta():
        return {"cuenta": "datos de la sesion"}

    return TestClient(app)


def _preflight(cliente: TestClient, origen: str, metodo: str, headers: str = "") -> str:
    pedido = {"Origin": origen, "Access-Control-Request-Method": metodo}
    if headers:
        pedido["Access-Control-Request-Headers"] = headers
    r = cliente.options("/api/cuenta", headers=pedido)
    if r.status_code == 200 and r.headers.get("access-control-allow-origin") == origen:
        return "PERMITE"
    return "rechaza" if r.status_code == 400 else "sin permiso"


def _en_produccion() -> dict:
    """La aplicación real arrancada con ENVIRONMENT=production, en un proceso aparte."""
    codigo = (
        "import json,sys;from fastapi.testclient import TestClient;"
        "from backend.main import app;c=TestClient(app);"
        "h=c.get('/health').headers;"
        "print(json.dumps({'hsts':h.get('strict-transport-security'),"
        "'docs':c.get('/docs').status_code,'openapi':c.get('/openapi.json').status_code}))"
    )
    entorno = {**os.environ, "ENVIRONMENT": "production",
               "ALLOWED_ORIGINS": "https://nexus.example", "ALLOWED_HOSTS": "",
               "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-c", codigo], cwd=_RAIZ, env=entorno,
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> None:
    lineas: list[str] = []
    comprobaciones: dict[str, bool] = {}

    def emitir(texto: str = "") -> None:
        print(texto)
        lineas.append(texto)

    emitir(_SEP)
    emitir("DEMO — Endurecimiento HTTP del backend (tarjeta #57)")
    emitir(_SEP)

    # ── 1. ALLOWED_ORIGINS ──────────────────────────────────────────────────
    emitir(f"\n{_SUB}\n1. ALLOWED_ORIGINS: qué acepta el servidor y qué lo hace no arrancar\n{_SUB}")
    casos = [
        ("http://localhost:3000", True), (" http://localhost:3000 , https://nexus.example ", True),
        ("HTTPS://Nexus.Example/", True), ("*", False), ("localhost:3000", False),
        ("https://nexus.example/app", False), ("http://localhost:abc", False), ("", False),
    ]
    emitir(f"  {'valor de ALLOWED_ORIGINS':42} {'resultado'}")
    for valor, debe_aceptar in casos:
        os.environ["ALLOWED_ORIGINS"] = valor
        try:
            salida = f"acepta  -> {origenes_permitidos()}"
            acepto = True
        except ConfiguracionInsegura:
            salida, acepto = "NO ARRANCA (configuración insegura)", False
        emitir(f"  {valor!r:42} {salida}")
        comprobaciones[f"origenes: {valor!r}"] = acepto == debe_aceptar
    os.environ["ALLOWED_ORIGINS"] = _PERMITIDO

    # ── 2. CORS antes y ahora ───────────────────────────────────────────────
    emitir(f"\n{_SUB}\n2. CORS: un preflight por caso, antes y ahora\n{_SUB}")
    from backend.main import app as app_real

    antes, ahora = _app_anterior([_PERMITIDO]), TestClient(app_real)
    escenarios = [
        ("POST desde el origen propio, header Content-Type", _PERMITIDO, "POST", "content-type", "PERMITE"),
        ("PUT desde el origen propio", _PERMITIDO, "PUT", "", "PERMITE"),
        ("DELETE (el frontend no lo usa)", _PERMITIDO, "DELETE", "", "rechaza"),
        ("header inventado X-Cabecera", _PERMITIDO, "POST", "x-cabecera-inventada", "rechaza"),
        ("POST desde un sitio ajeno", _AJENO, "POST", "content-type", "rechaza"),
    ]
    emitir(f"  {'caso':50} {'ANTES':>12} {'AHORA':>12}")
    for nombre, origen, metodo, headers, esperado in escenarios:
        a, b = _preflight(antes, origen, metodo, headers), _preflight(ahora, origen, metodo, headers)
        emitir(f"  {nombre:50} {a:>12} {b:>12}")
        comprobaciones[f"cors: {nombre}"] = b == esperado

    # ── 3. El riesgo del `*` ────────────────────────────────────────────────
    emitir(f"\n{_SUB}\n3. El riesgo del '*' con credenciales (configuración anterior, medido)\n{_SUB}")
    peligrosa = _app_anterior(["*"])
    r = peligrosa.get("/api/cuenta", headers={"Origin": _AJENO, "Cookie": "nexus_session=abc"})
    permiso = r.headers.get("access-control-allow-origin")
    emitir(f"  Pedido con cookie desde {_AJENO}")
    emitir(f"  Access-Control-Allow-Origin devuelto : {permiso}")
    emitir(f"  Access-Control-Allow-Credentials     : {r.headers.get('access-control-allow-credentials')}")
    emitir("  -> un sitio cualquiera queda autorizado a leer la respuesta autenticada.")
    emitir("  Ahora ese valor impide que el servidor arranque (sección 1).")
    comprobaciones["el riesgo del * existía en la configuración anterior"] = permiso == _AJENO

    # ── 4. Encabezados de seguridad ─────────────────────────────────────────
    emitir(f"\n{_SUB}\n4. Encabezados de seguridad en una respuesta real (GET /api/cuenta)\n{_SUB}")
    r_antes = antes.get("/api/cuenta", headers={"Origin": _PERMITIDO})
    r_ahora = ahora.get("/api/cuenta", headers={"Origin": _PERMITIDO})
    esperados = ["x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy",
                 "cross-origin-opener-policy", "content-security-policy", "cache-control"]
    emitir(f"  {'encabezado':30} {'ANTES':>8}   AHORA")
    for nombre in esperados:
        valor = r_ahora.headers.get(nombre)
        emitir(f"  {nombre:30} {'sí' if nombre in r_antes.headers else 'no':>8}   {valor}")
        comprobaciones[f"encabezado {nombre}"] = valor is not None and nombre not in r_antes.headers

    # ── 5. Producción ───────────────────────────────────────────────────────
    emitir(f"\n{_SUB}\n5. Producción (ENVIRONMENT=production, proceso aparte)\n{_SUB}")
    prod = _en_produccion()
    emitir(f"  Strict-Transport-Security : {prod['hsts']}")
    emitir(f"  GET /docs                 : {prod['docs']}   (en desarrollo: 200)")
    emitir(f"  GET /openapi.json         : {prod['openapi']}   (en desarrollo: 200)")
    os.environ["ENVIRONMENT"] = "production"
    os.environ["ALLOWED_ORIGINS"] = "http://nexus.example"
    try:
        origenes_permitidos()
        http_rechazado = False
    except ConfiguracionInsegura:
        http_rechazado = True
    os.environ.pop("ENVIRONMENT"); os.environ["ALLOWED_ORIGINS"] = _PERMITIDO
    emitir(f"  http://nexus.example como origen: {'NO ARRANCA (en producción exige https)' if http_rechazado else 'acepta'}")
    comprobaciones["producción: HSTS"] = bool(prod["hsts"]) and "max-age=31536000" in prod["hsts"]
    comprobaciones["producción: /docs apagado"] = prod["docs"] == 404 and prod["openapi"] == 404
    comprobaciones["producción: http rechazado"] = http_rechazado

    # ── Resumen ─────────────────────────────────────────────────────────────
    todo_ok = all(comprobaciones.values())
    emitir(f"\n{_SEP}")
    fallidas = [k for k, v in comprobaciones.items() if not v]
    emitir(f"{'[OK]' if todo_ok else '[X]'} {sum(comprobaciones.values())} de {len(comprobaciones)} comprobaciones."
           + (f" Fallan: {fallidas}" if fallidas else ""))
    emitir("\nAlcance: no termina TLS (eso lo hace el proxy inverso del despliegue) y no pone")
    emitir("Content-Security-Policy en el frontend: Next inyecta scripts en línea y una CSP")
    emitir("estricta exige nonces por pedido, que hay que probar antes de activar.")
    emitir(_SEP)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "resultado.txt").write_text("\n".join(lineas), encoding="utf-8")
    (_OUT_DIR / "resumen.json").write_text(json.dumps(
        {"comprobaciones": comprobaciones, "todo_ok": todo_ok, "produccion": prod},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nArtefactos: {_OUT_DIR}")
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
