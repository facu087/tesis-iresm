"""
Tests del endurecimiento HTTP (backend/seguridad.py, tarjeta #57).

Herméticos: sin red ni LLM. Cubren las tres cosas que cambian: la validación de
`ALLOWED_ORIGINS` (el servidor no arranca con una configuración insegura), los
encabezados de seguridad y la superficie de CORS (solo lo que el frontend usa).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import seguridad
from backend.seguridad import (
    ConfiguracionInsegura,
    EncabezadosDeSeguridad,
    es_produccion,
    hosts_permitidos,
    origenes_permitidos,
    urls_de_documentacion,
)


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for var in ("ALLOWED_ORIGINS", "ALLOWED_HOSTS", "ENVIRONMENT"):
        monkeypatch.delenv(var, raising=False)


# ── Orígenes permitidos ───────────────────────────────────────────────────────

class TestOrigenesPermitidos:
    def test_sin_definir_cae_en_el_origen_de_desarrollo(self):
        assert origenes_permitidos() == ["http://localhost:3000"]

    def test_recorta_espacios_y_descarta_vacios(self, monkeypatch):
        """Antes main.py partía por coma sin recortar: el segundo origen nunca coincidía."""
        monkeypatch.setenv("ALLOWED_ORIGINS", " http://localhost:3000 , ,https://nexus.example ")
        assert origenes_permitidos() == ["http://localhost:3000", "https://nexus.example"]

    def test_normaliza_barra_final_y_mayusculas(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "HTTPS://Nexus.Example/")
        assert origenes_permitidos() == ["https://nexus.example"]

    def test_quita_duplicados_conservando_el_orden(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example,https://b.example,https://a.example/")
        assert origenes_permitidos() == ["https://a.example", "https://b.example"]

    def test_acepta_puerto(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
        assert origenes_permitidos() == ["http://localhost:5173"]

    @pytest.mark.parametrize("valor", [
        "*",
        "http://localhost:3000,*",
        "localhost:3000",              # sin esquema
        "ftp://nexus.example",
        "javascript:alert(1)",
        "https://nexus.example/app",   # con ruta
        "https://nexus.example?x=1",
        "https://usuario@nexus.example",
        "http://localhost:abc",        # puerto inválido
        "http://",
        "   ,  ",                      # definida pero vacía
        "",
    ])
    def test_rechaza_configuraciones_inseguras_o_rotas(self, monkeypatch, valor):
        monkeypatch.setenv("ALLOWED_ORIGINS", valor)
        with pytest.raises(ConfiguracionInsegura):
            origenes_permitidos()

    def test_el_comodin_explica_por_que_no(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "*")
        with pytest.raises(ConfiguracionInsegura, match="cualquier sitio"):
            origenes_permitidos()


class TestProduccion:
    def test_http_fuera_de_localhost_se_rechaza(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://nexus.example")
        with pytest.raises(ConfiguracionInsegura, match="https"):
            origenes_permitidos()

    def test_https_y_localhost_se_aceptan(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://nexus.example,http://localhost:3000")
        assert origenes_permitidos() == ["https://nexus.example", "http://localhost:3000"]

    def test_fuera_de_produccion_http_se_acepta(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://nexus.interno")
        assert origenes_permitidos() == ["http://nexus.interno"]

    @pytest.mark.parametrize("valor,esperado", [
        ("production", True), ("Production", True), (" PRODUCTION ", True),
        ("development", False), ("", False), ("prod", False),
    ])
    def test_es_produccion(self, monkeypatch, valor, esperado):
        monkeypatch.setenv("ENVIRONMENT", valor)
        assert es_produccion() is esperado

    def test_la_cookie_de_sesion_y_el_hsts_usan_la_misma_decision(self, monkeypatch):
        """
        Con 'Production' el HSTS se activaba pero la cookie salía sin `Secure`
        (comparaba el texto exacto). Las dos tienen que decidir igual.
        """
        from fastapi import Response

        from backend.auth.sesiones import set_session_cookie

        monkeypatch.setenv("ENVIRONMENT", "Production")
        respuesta = Response()
        set_session_cookie(respuesta, "valor")
        assert "secure" in respuesta.headers["set-cookie"].lower()

    def test_la_documentacion_interactiva_solo_existe_fuera_de_produccion(self, monkeypatch):
        assert urls_de_documentacion()["docs_url"] == "/docs"
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert urls_de_documentacion() == {"docs_url": None, "redoc_url": None, "openapi_url": None}


class TestHostsPermitidos:
    def test_sin_definir_no_restringe(self):
        assert hosts_permitidos() is None

    def test_lista_en_minusculas(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_HOSTS", "API.Nexus.Example, nexus.example")
        assert hosts_permitidos() == ["api.nexus.example", "nexus.example"]

    def test_el_comodin_se_rechaza(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_HOSTS", "*")
        with pytest.raises(ConfiguracionInsegura):
            hosts_permitidos()


# ── Encabezados de seguridad ──────────────────────────────────────────────────

def _app_con(hsts: bool = False) -> TestClient:
    app = FastAPI()

    @app.get("/api/dato")
    def dato():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/docs")
    def docs():
        return {"ok": True}

    @app.get("/api/propio")
    def propio():
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True}, headers={"Cache-Control": "max-age=60"})

    app.add_middleware(EncabezadosDeSeguridad, hsts=hsts)
    return TestClient(app)


class TestEncabezadosDeSeguridad:
    def test_toda_respuesta_los_lleva(self):
        r = _app_con().get("/health")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert "camera=()" in r.headers["permissions-policy"]
        assert r.headers["cross-origin-opener-policy"] == "same-origin"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]

    def test_los_datos_de_la_api_no_se_guardan_en_cache(self):
        assert _app_con().get("/api/dato").headers["cache-control"] == "no-store"

    def test_fuera_de_la_api_no_se_fuerza_cache(self):
        assert "cache-control" not in _app_con().get("/health").headers

    def test_un_encabezado_fijado_por_la_ruta_se_respeta(self):
        assert _app_con().get("/api/propio").headers["cache-control"] == "max-age=60"

    def test_la_documentacion_no_lleva_csp(self):
        """Swagger UI carga scripts de un CDN: una CSP 'none' la dejaría en blanco."""
        assert "content-security-policy" not in _app_con().get("/docs").headers

    def test_hsts_solo_cuando_se_pide(self):
        assert "strict-transport-security" not in _app_con(hsts=False).get("/health").headers
        hsts = _app_con(hsts=True).get("/health").headers["strict-transport-security"]
        assert "max-age=31536000" in hsts and "includeSubDomains" in hsts

    def test_las_respuestas_de_error_tambien_los_llevan(self):
        r = _app_con().get("/ruta-que-no-existe")
        assert r.status_code == 404
        assert r.headers["x-content-type-options"] == "nosniff"

    def test_el_cuerpo_no_se_altera(self):
        assert _app_con().get("/api/dato").json() == {"ok": True}


# ── La aplicación real ────────────────────────────────────────────────────────

@pytest.fixture
def cliente_real():
    from backend.main import app
    return TestClient(app)


_PERMITIDO = "http://localhost:3000"


class TestCorsDeLaAplicacion:
    def test_el_origen_permitido_recibe_credenciales(self, cliente_real):
        r = cliente_real.options("/api/login", headers={
            "Origin": _PERMITIDO, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"})
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == _PERMITIDO
        assert r.headers["access-control-allow-credentials"] == "true"

    def test_un_origen_ajeno_no_recibe_nada(self, cliente_real):
        r = cliente_real.options("/api/login", headers={
            "Origin": "https://sitio-malicioso.example",
            "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in r.headers

    def test_un_metodo_que_el_frontend_no_usa_se_rechaza(self, cliente_real):
        r = cliente_real.options("/api/cuenta", headers={
            "Origin": _PERMITIDO, "Access-Control-Request-Method": "DELETE"})
        assert r.status_code == 400

    def test_los_metodos_que_el_frontend_si_usa_se_aceptan(self, cliente_real):
        for metodo in ("GET", "POST", "PUT"):
            r = cliente_real.options("/api/cuenta", headers={
                "Origin": _PERMITIDO, "Access-Control-Request-Method": metodo})
            assert r.status_code == 200, metodo

    def test_un_header_arbitrario_se_rechaza(self, cliente_real):
        r = cliente_real.options("/api/login", headers={
            "Origin": _PERMITIDO, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-cabecera-inventada"})
        assert r.status_code == 400

    def test_el_preflight_tambien_lleva_encabezados_de_seguridad(self, cliente_real):
        r = cliente_real.options("/api/login", headers={
            "Origin": _PERMITIDO, "Access-Control-Request-Method": "POST"})
        assert r.headers["x-content-type-options"] == "nosniff"

    def test_la_aplicacion_real_usa_los_encabezados_y_no_guarda_cache(self, cliente_real):
        r = cliente_real.get("/api/cuenta")  # sin sesión: 401, pero con los encabezados
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["x-frame-options"] == "DENY"


class TestLaUnicaFuenteDeOrigenes:
    def test_la_validacion_de_csrf_y_el_cors_leen_la_misma_lista(self):
        """Una sola lectura de ALLOWED_ORIGINS: no puede haber dos criterios."""
        from backend.auth import origen

        assert origen._allowed_origins.__module__.endswith("origen")
        assert origen.origenes_permitidos is seguridad.origenes_permitidos

    def test_con_configuracion_invalida_la_validacion_no_permite_ninguno(self, monkeypatch):
        """Fail-closed: un `*` no abre la puerta a todos, la cierra."""
        from backend.auth.origen import _allowed_origins

        monkeypatch.setenv("ALLOWED_ORIGINS", "*")
        assert _allowed_origins() == []

    def test_el_origen_de_la_solicitud_se_compara_en_minusculas(self, monkeypatch):
        from fastapi import HTTPException

        from backend.auth.origen import validar_origen

        monkeypatch.setenv("ALLOWED_ORIGINS", "https://nexus.example")

        class _Pedido:
            headers = {"origin": "HTTPS://NEXUS.EXAMPLE"}

        validar_origen(_Pedido())  # no levanta

        class _Ajeno:
            headers = {"origin": "https://otro.example"}

        with pytest.raises(HTTPException):
            validar_origen(_Ajeno())
