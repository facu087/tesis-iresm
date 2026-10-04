"""
Tests de `POST /api/login`, `POST /api/logout` y la sesión resultante
(tareas 2.2, 2.3, 2.4 y 3.1).

Usa las fixtures de `conftest.py`: `client` (Origin permitido por default),
`cuenta_medico_verificada`, `cuenta_admin`.
"""

from backend.auth.login import MAX_INTENTOS_FALLIDOS


class TestLoginExitoso:
    def test_credenciales_correctas_devuelve_200(self, client, cuenta_medico_verificada):
        resp = client.post(
            "/api/login",
            json={"email": cuenta_medico_verificada.email, "password": "ContraseñaSegura123"},
        )
        assert resp.status_code == 200

    def test_login_exitoso_fija_cookie_httponly(self, client, cuenta_medico_verificada):
        client.post(
            "/api/login",
            json={"email": cuenta_medico_verificada.email, "password": "ContraseñaSegura123"},
        )
        cookie = next(c for c in client.cookies.jar if c.name == "nexus_sesion")
        assert cookie.value
        # Los flags de cookie (HttpOnly, sin valor) quedan como claves en `_rest`.
        assert "HttpOnly" in cookie._rest
        assert cookie._rest.get("SameSite", "").lower() == "lax"

    def test_medico_pendiente_puede_loguearse(self, client, cuenta_medico_pendiente):
        resp = client.post(
            "/api/login",
            json={"email": cuenta_medico_pendiente.email, "password": "ContraseñaSegura123"},
        )
        assert resp.status_code == 200


class TestSinEnumeracionDeUsuarios:
    def test_email_inexistente_devuelve_401_generico(self, client):
        resp = client.post(
            "/api/login", json={"email": "no-existe@hospital.example", "password": "cualquiera123"}
        )
        assert resp.status_code == 401
        detalle_inexistente = resp.json()["detail"]

        resp2 = client.post(
            "/api/login", json={"email": "no-existe@hospital.example", "password": "otra-mas123"}
        )
        assert resp2.json()["detail"] == detalle_inexistente

    def test_contrasena_incorrecta_devuelve_el_mismo_mensaje_generico(
        self, client, cuenta_medico_verificada
    ):
        resp_inexistente = client.post(
            "/api/login", json={"email": "no-existe@hospital.example", "password": "x1234567"}
        )
        resp_incorrecta = client.post(
            "/api/login",
            json={"email": cuenta_medico_verificada.email, "password": "contraseña-incorrecta"},
        )
        assert resp_incorrecta.status_code == 401
        assert resp_incorrecta.json()["detail"] == resp_inexistente.json()["detail"]


class TestSesion:
    def test_solicitud_posterior_usa_la_sesion_activa(self, client_medico_verificado):
        resp = client_medico_verificado.get("/api/cuenta")
        assert resp.status_code == 200
        assert resp.json()["estado"] == "verificado"

    def test_logout_invalida_la_sesion(self, client_medico_verificado):
        resp_logout = client_medico_verificado.post("/api/logout")
        assert resp_logout.status_code == 200

        resp_luego = client_medico_verificado.get("/api/cuenta")
        assert resp_luego.status_code == 401

    def test_sesion_de_cuenta_admin_queda_identificada_como_admin(self, client_admin):
        resp = client_admin.get("/api/cuenta")
        assert resp.status_code == 200
        assert resp.json()["rol"] == "admin"

    def test_sesion_de_cuenta_medico_queda_identificada_como_medico(self, client_medico_verificado):
        resp = client_medico_verificado.get("/api/cuenta")
        assert resp.json()["rol"] == "medico"


class TestLimiteDeIntentos:
    def test_supera_el_limite_bloquea_intentos_posteriores(self, client, cuenta_medico_verificada):
        email = cuenta_medico_verificada.email
        for _ in range(MAX_INTENTOS_FALLIDOS):
            resp = client.post("/api/login", json={"email": email, "password": "incorrecta-1234"})
            assert resp.status_code == 401

        # Ahora, aunque la contraseña sea correcta, la cuenta está bloqueada.
        resp_correcta = client.post(
            "/api/login", json={"email": email, "password": "ContraseñaSegura123"}
        )
        assert resp_correcta.status_code == 401


class TestValidacionDeOrigenLoginYLogout:
    def test_login_con_origen_ajeno_devuelve_403_sin_validar_credenciales(
        self, client, cuenta_medico_verificada
    ):
        resp = client.post(
            "/api/login",
            json={"email": cuenta_medico_verificada.email, "password": "lo-que-sea"},
            headers={"Origin": "https://sitio-ajeno.example"},
        )
        assert resp.status_code == 403

    def test_login_con_origen_permitido_continua(self, client, cuenta_medico_verificada):
        resp = client.post(
            "/api/login",
            json={"email": cuenta_medico_verificada.email, "password": "ContraseñaSegura123"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200

    def test_logout_con_origen_ajeno_devuelve_403(self, client_medico_verificado):
        resp = client_medico_verificado.post(
            "/api/logout", headers={"Origin": "https://sitio-ajeno.example"}
        )
        assert resp.status_code == 403
