"""
Controles de seguridad del servidor HTTP (Sprint 5, tarjeta #57).

Antes de este módulo, la lista de orígenes permitidos se leía en dos lugares con
criterios distintos: `main.py` la partía por coma sin recortar espacios (con
`a, b` el segundo origen jamás coincidía, en silencio) y `auth/origen.py` sí los
recortaba. Y nada impedía configurar `ALLOWED_ORIGINS=*`: con
`allow_credentials=True`, Starlette responde con el origen de quien pregunta, así
que cualquier sitio habría podido leer respuestas autenticadas con la cookie de
sesión del médico.

Qué hay acá
-----------
- `origenes_permitidos()`: la única lectura de `ALLOWED_ORIGINS`. Valida y
  **falla al arrancar** si la configuración es insegura, en vez de aceptarla.
- `es_produccion()`: la única decisión de "producción". La usan el HSTS, la
  cookie `Secure` y la documentación interactiva, así no pueden discrepar.
- `EncabezadosDeSeguridad`: middleware ASGI que agrega los encabezados de
  seguridad a toda respuesta HTTP.
- `hosts_permitidos()`: lista opcional de `Host` aceptados.

Qué NO hace, y se dice
----------------------
No termina TLS: el backend corre detrás de un proxy inverso que lo hace
(ver "Despliegue" en `.claude/CLAUDE.md`). Tampoco pone encabezados en una
respuesta 500 sin manejar: esa la arma el middleware más externo de Starlette,
por fuera de este.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ENV_ORIGENES = "ALLOWED_ORIGINS"
ENV_HOSTS = "ALLOWED_HOSTS"
ORIGEN_POR_DEFECTO = "http://localhost:3000"

# Hosts donde `http` es aceptable aun en producción: el tráfico no sale de la máquina.
_HOSTS_LOCALES = frozenset({"localhost", "127.0.0.1", "::1"})

# Métodos y encabezados de pedido que el frontend realmente usa (api.ts): sin
# esto, CORS aceptaba cualquier método y cualquier header ("*").
METODOS_CORS = ["GET", "POST", "PUT"]
ENCABEZADOS_CORS = ["Content-Type"]

# Rutas de la documentación interactiva: Swagger UI carga scripts de un CDN y
# usa estilos en línea, así que una CSP `default-src 'none'` la rompería.
_RUTAS_DOCUMENTACION = ("/docs", "/redoc", "/openapi.json")

_CSP_API = "default-src 'none'; frame-ancestors 'none'"
_HSTS = "max-age=31536000; includeSubDomains"


class ConfiguracionInsegura(RuntimeError):
    """La configuración de seguridad no es aceptable: el servidor no debe arrancar."""


def es_produccion() -> bool:
    """`ENVIRONMENT=production`, sin distinguir mayúsculas ni espacios."""
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


def _normalizar_origen(valor: str) -> str:
    """
    Devuelve el origen en su forma canónica (`esquema://host[:puerto]`, en
    minúsculas) o levanta `ConfiguracionInsegura` diciendo por qué no sirve.
    """
    if valor == "*":
        raise ConfiguracionInsegura(
            f"{ENV_ORIGENES}=* no está permitido: con la cookie de sesión equivale a "
            "aceptar a cualquier sitio. Listá los orígenes uno por uno."
        )
    partes = urlsplit(valor)
    try:
        partes.port  # noqa: B018 — levanta ValueError si el puerto es inválido
    except ValueError:
        raise ConfiguracionInsegura(f"Origen con puerto inválido en {ENV_ORIGENES}: {valor!r}.") from None
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ConfiguracionInsegura(
            f"Origen inválido en {ENV_ORIGENES}: {valor!r}. "
            "Tiene que ser esquema://host[:puerto], con http o https."
        )
    if partes.path not in ("", "/") or partes.query or partes.fragment or partes.username:
        raise ConfiguracionInsegura(
            f"Origen inválido en {ENV_ORIGENES}: {valor!r}. "
            "Un origen no lleva ruta, parámetros ni credenciales."
        )
    if es_produccion() and partes.scheme == "http" and partes.hostname.lower() not in _HOSTS_LOCALES:
        raise ConfiguracionInsegura(
            f"En producción los orígenes tienen que ser https: {valor!r} no lo es."
        )
    return f"{partes.scheme}://{partes.netloc}".lower()


def origenes_permitidos() -> list[str]:
    """
    La lista de orígenes de `ALLOWED_ORIGINS`, validada y sin duplicados.

    Sin definir cae en el origen de desarrollo. Definida pero vacía es un error:
    casi seguro es una configuración rota y no una decisión.
    """
    crudo = os.environ.get(ENV_ORIGENES)
    if crudo is None:
        return [ORIGEN_POR_DEFECTO]
    candidatos = [c.strip() for c in crudo.split(",") if c.strip()]
    if not candidatos:
        raise ConfiguracionInsegura(f"{ENV_ORIGENES} está definida pero vacía.")
    vistos: dict[str, None] = {}
    for candidato in candidatos:
        vistos[_normalizar_origen(candidato)] = None
    return list(vistos)


def hosts_permitidos() -> list[str] | None:
    """`ALLOWED_HOSTS` (coma separada), o `None` si no se definió: no se restringe."""
    crudo = os.environ.get(ENV_HOSTS, "")
    hosts = [h.strip().lower() for h in crudo.split(",") if h.strip()]
    if not hosts:
        return None
    if "*" in hosts:
        raise ConfiguracionInsegura(f"{ENV_HOSTS}=* equivale a no restringir nada: quitalo o listá los hosts.")
    return hosts


def urls_de_documentacion() -> dict[str, str | None]:
    """La documentación interactiva (`/docs`, `/redoc`) solo existe fuera de producción."""
    if es_produccion():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


class EncabezadosDeSeguridad:
    """
    Middleware ASGI que agrega encabezados de seguridad a toda respuesta HTTP.

    Es ASGI puro, no `BaseHTTPMiddleware`: este último ejecuta la app en otra
    tarea y rompe lo que dependa de `contextvars` (la telemetría de costos lo usa).
    Usa `setdefault`: si una ruta fijó un encabezado a propósito, se respeta.
    """

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    def _encabezados(self, ruta: str) -> dict[str, str]:
        fijos = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
            "Cross-Origin-Opener-Policy": "same-origin",
        }
        if not ruta.startswith(_RUTAS_DOCUMENTACION):
            fijos["Content-Security-Policy"] = _CSP_API
        if ruta.startswith("/api/"):
            # Datos clínicos y de sesión: ni el navegador ni un proxy los guardan.
            fijos["Cache-Control"] = "no-store"
        if self.hsts:
            fijos["Strict-Transport-Security"] = _HSTS
        return fijos

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        fijos = self._encabezados(scope.get("path", ""))

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                encabezados = MutableHeaders(scope=mensaje)
                for nombre, valor in fijos.items():
                    encabezados.setdefault(nombre, valor)
            await send(mensaje)

        await self.app(scope, receive, enviar)
