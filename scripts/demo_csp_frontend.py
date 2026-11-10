"""
Demo — Content-Security-Policy del frontend con nonce por pedido (Sprint 5,
pendiente de la tarjeta #57).

Antes de este cambio, el frontend no mandaba Content-Security-Policy: Next
inyecta scripts en línea para hidratar y una política estricta exige un nonce
distinto en cada pedido. Ahora `frontend/src/proxy.ts` genera ese nonce, arma
la política (`frontend/src/lib/csp.ts`) y Next lo agrega a sus propios scripts.

Este script levanta el build de producción del frontend (`next start`) en un
puerto libre, pide cada ruta y comprueba, sobre las respuestas reales:

  1. que cada página trae la política, sin 'unsafe-inline' ni 'unsafe-eval'
     para scripts;
  2. que todo <script> ejecutable de la página lleva el nonce del encabezado,
     incluido el script del tema de `app/layout.tsx`;
  3. que el nonce cambia en cada pedido;
  4. que `connect-src` deja llamar al backend y nada más, y que la página no
     se puede embeber (`frame-ancestors 'none'`).

No usa red externa, ni el backend, ni cuota. Lo que un navegador hace con la
política (que la página hidrata y que un <img onerror> inyectado se bloquea)
se verificó aparte, con un navegador sin interfaz: ver la tarjeta de Trello.

    cd frontend && npm run build && cd ..
    python scripts/demo_csp_frontend.py          # usa el build existente
    python scripts/demo_csp_frontend.py --build  # lo construye antes

Artefactos en output/demo_csp_frontend/:
    resultado.txt → la corrida completa
    resumen.json  → política, nonces y comprobaciones

Sale con código 1 si alguna comprobación falla y con 2 si no hay build.
"""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_RAIZ = Path(__file__).parent.parent
_FRONTEND = _RAIZ / "frontend"
_OUT_DIR = _RAIZ / "output" / "demo_csp_frontend"
_SEP = "═" * 78
_RUTAS = ("/", "/registro", "/ingresar", "/cuenta", "/analizar", "/analyzing",
          "/report", "/admin/pendientes", "/ruta-que-no-existe")
_lineas: list[str] = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _p(texto: str = "") -> None:
    """Imprime y guarda la línea para resultado.txt."""
    print(texto)
    _lineas.append(texto)


def _puerto_libre() -> int:
    """Pide al sistema un puerto TCP libre en localhost."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pedir(url: str) -> tuple[int, dict[str, str], str]:
    """GET sin seguir el estado de error: devuelve código, encabezados y cuerpo."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode()


def _directivas(csp: str) -> dict[str, list[str]]:
    """Separa el valor del encabezado en directiva → fuentes."""
    resultado: dict[str, list[str]] = {}
    for parte in csp.split(";"):
        nombre, *fuentes = parte.split()
        resultado[nombre] = fuentes
    return resultado


def _scripts_ejecutables(html: str) -> list[str]:
    """Etiquetas <script> que el navegador ejecutaría (no los bloques JSON-LD)."""
    etiquetas = re.findall(r"<script\b[^>]*>", html)
    return [e for e in etiquetas if "application/ld+json" not in e]


def _comprobar_ruta(base: str, ruta: str) -> dict:
    """Pide una ruta y evalúa las comprobaciones 1, 2 y 4 sobre esa respuesta."""
    estado, encabezados, html = _pedir(base + ruta)
    csp = encabezados.get("content-security-policy", "")
    directivas = _directivas(csp) if csp else {}
    scripts = directivas.get("script-src", [])
    nonce = next((f[len("'nonce-"):-1] for f in scripts if f.startswith("'nonce-")), None)
    etiquetas = _scripts_ejecutables(html)
    sin_nonce = [e for e in etiquetas if f'nonce="{nonce}"' not in e]
    tema = next((m for m in re.findall(r"<script\b[^>]*>[^<]*", html) if "nexus-theme" in m), "")
    comprobaciones = {
        "trae la política": bool(csp),
        "scripts solo con nonce": bool(nonce) and "'unsafe-inline'" not in scripts
                                  and "'unsafe-eval'" not in scripts,
        "todo <script> lleva el nonce": bool(etiquetas) and not sin_nonce,
        "el script del tema lleva el nonce": f'nonce="{nonce}"' in tema,
        "no se puede embeber": directivas.get("frame-ancestors") == ["'none'"],
    }
    return {"ruta": ruta, "estado_http": estado, "nonce": nonce, "scripts": len(etiquetas),
            "sin_nonce": sin_nonce, "csp": csp, "connect_src": directivas.get("connect-src"),
            "comprobaciones": comprobaciones}


def main() -> int:
    """Levanta el frontend, corre las comprobaciones y guarda los artefactos."""
    if "--build" in sys.argv:
        subprocess.run(["npm", "run", "build"], cwd=_FRONTEND, check=True)
    if not (_FRONTEND / ".next" / "BUILD_ID").exists():
        print("No hay build de producción: corré `cd frontend && npm run build` "
              "o este script con --build.")
        return 2

    puerto = _puerto_libre()
    base = f"http://127.0.0.1:{puerto}"
    servidor = subprocess.Popen(
        ["npx", "next", "start", "-p", str(puerto), "-H", "127.0.0.1"], cwd=_FRONTEND,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        for _ in range(60):
            try:
                _pedir(base + "/")
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.5)
        else:
            print("El frontend no respondió en 30 s.")
            return 1

        _p(_SEP)
        _p("CSP DEL FRONTEND — build de producción servido con `next start`")
        _p(_SEP)
        _p("Antes: ninguna respuesta del frontend traía Content-Security-Policy.")
        _p("")
        rutas = [_comprobar_ruta(base, ruta) for ruta in _RUTAS]
        politica = rutas[0]["csp"]
        _p("Política que recibe el navegador (ruta /):")
        for directiva in politica.split("; "):
            _p(f"  {directiva}")
        _p("")
        _p("Por ruta — nonce del encabezado y <script> ejecutables que lo llevan:")
        for r in rutas:
            ok = all(r["comprobaciones"].values())
            _p(f"  [{'OK' if ok else 'FALLA'}] {r['ruta']:<20} HTTP {r['estado_http']}  "
               f"nonce={r['nonce']}  scripts={r['scripts']}  sin nonce={len(r['sin_nonce'])}")
            for nombre, valor in r["comprobaciones"].items():
                if not valor:
                    _p(f"         falla: {nombre}")

        nonces = [_comprobar_ruta(base, "/")["nonce"] for _ in range(3)]
        distintos = len(set(nonces)) == len(nonces) and None not in nonces
        _p("")
        _p("Tres pedidos seguidos a / — el nonce cambia en cada uno:")
        for n in nonces:
            _p(f"  {n}")

        conexiones = rutas[0]["connect_src"] or []
        backend = conexiones[1:] if conexiones[:1] == ["'self'"] else []
        _p("")
        _p(f"connect-src: el propio origen y el backend {', '.join(backend) or '(ninguno)'}")

        generales = {
            "el nonce cambia en cada pedido": distintos,
            "connect-src: propio origen y un solo backend": len(backend) == 1,
        }
        fallas = [f"{r['ruta']}: {c}" for r in rutas for c, ok in r["comprobaciones"].items()
                  if not ok] + [c for c, ok in generales.items() if not ok]
        _p("")
        for nombre, ok in generales.items():
            _p(f"  [{'OK' if ok else 'FALLA'}] {nombre}")
        _p("")
        _p(_SEP)
        _p("[OK] Todas las comprobaciones pasan." if not fallas
           else "[FALLA] " + "; ".join(fallas))
        _p(_SEP)

        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        (_OUT_DIR / "resultado.txt").write_text("\n".join(_lineas) + "\n", encoding="utf-8")
        (_OUT_DIR / "resumen.json").write_text(json.dumps(
            {"politica": politica, "rutas": rutas, "nonces_seguidos": nonces,
             "comprobaciones": generales}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nArtefactos: {_OUT_DIR}")
        return 1 if fallas else 0
    finally:
        os.killpg(servidor.pid, signal.SIGTERM)
        servidor.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
