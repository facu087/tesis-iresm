"""
Tests de la revisión admin de cuentas pendientes (sección 5 de tasks.md).
"""

from sqlmodel import Session, select

from backend.models.auditoria import DecisionAuditoria, DecisionTipo


class TestAccesoRestringido:
    def test_medico_recibe_403(self, client_medico_verificado):
        resp = client_medico_verificado.get("/api/admin/pendientes")
        assert resp.status_code == 403

    def test_admin_accede(self, client_admin):
        resp = client_admin.get("/api/admin/pendientes")
        assert resp.status_code == 200


class TestListadoDePendientes:
    def test_listado_incluye_los_datos_de_registro(self, client_admin, cuenta_medico_pendiente):
        resp = client_admin.get("/api/admin/pendientes")
        assert resp.status_code == 200
        cuentas = resp.json()
        assert len(cuentas) == 1
        fila = cuentas[0]
        assert fila["nombre"] == cuenta_medico_pendiente.nombre
        assert fila["dni"] == cuenta_medico_pendiente.dni
        assert fila["matricula"] == cuenta_medico_pendiente.matricula
        assert fila["email"] == cuenta_medico_pendiente.email

    def test_listado_no_incluye_cuentas_verificadas(
        self, client_admin, cuenta_medico_pendiente, cuenta_medico_verificada
    ):
        resp = client_admin.get("/api/admin/pendientes")
        emails = [c["email"] for c in resp.json()]
        assert cuenta_medico_pendiente.email in emails
        assert cuenta_medico_verificada.email not in emails

    def test_enlace_refeps_presente(self, client_admin, cuenta_medico_pendiente):
        resp = client_admin.get("/api/admin/pendientes")
        assert resp.json()[0]["enlace_refeps"].startswith("https://")

    def test_enlace_provincial_no_configurado_no_rompe(
        self, client_admin, cuenta_medico_pendiente, monkeypatch
    ):
        monkeypatch.delenv("PROVINCIAL_LICENSE_SEARCH_URL", raising=False)
        resp = client_admin.get("/api/admin/pendientes")
        assert resp.status_code == 200
        assert resp.json()[0]["enlace_provincial"] is None


class TestAprobacion:
    def test_aprobar_pasa_la_cuenta_a_verificado(self, client_admin, cuenta_medico_pendiente):
        resp = client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/aprobar",
            json={"fuente_consultada": "Buscador Nacional REFEPS"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "verificado"

    def test_aprobar_sin_fuente_falla(self, client_admin, cuenta_medico_pendiente):
        resp = client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/aprobar",
            json={"fuente_consultada": ""},
        )
        assert resp.status_code == 422

    def test_aprobar_genera_auditoria(
        self, client_admin, cuenta_medico_pendiente, cuenta_admin, _base_de_datos_temporal
    ):
        client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/aprobar",
            json={"fuente_consultada": "Buscador Nacional REFEPS"},
        )
        with Session(_base_de_datos_temporal) as session:
            registros = session.exec(
                select(DecisionAuditoria).where(
                    DecisionAuditoria.cuenta_id == cuenta_medico_pendiente.id
                )
            ).all()
            assert len(registros) == 1
            assert registros[0].decision == DecisionTipo.APROBADO
            assert registros[0].admin_id == cuenta_admin.id
            assert registros[0].fuente_consultada == "Buscador Nacional REFEPS"


class TestRechazo:
    def test_rechazar_sin_motivo_falla_y_no_cambia_estado(
        self, client_admin, cuenta_medico_pendiente, _base_de_datos_temporal
    ):
        resp = client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/rechazar",
            json={"motivo": ""},
        )
        assert resp.status_code == 422

        from backend.models.cuenta import CuentaMedico, EstadoCuenta

        with Session(_base_de_datos_temporal) as session:
            cuenta = session.get(CuentaMedico, cuenta_medico_pendiente.id)
            assert cuenta.estado == EstadoCuenta.PENDIENTE

    def test_rechazar_con_motivo(self, client_admin, cuenta_medico_pendiente):
        resp = client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/rechazar",
            json={"motivo": "Los datos no coinciden con el buscador público."},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "rechazado"

    def test_rechazar_genera_auditoria(
        self, client_admin, cuenta_medico_pendiente, _base_de_datos_temporal
    ):
        client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/rechazar",
            json={"motivo": "Matrícula no coincide."},
        )
        with Session(_base_de_datos_temporal) as session:
            registros = session.exec(
                select(DecisionAuditoria).where(
                    DecisionAuditoria.cuenta_id == cuenta_medico_pendiente.id
                )
            ).all()
            assert len(registros) == 1
            assert registros[0].decision == DecisionTipo.RECHAZADO
            assert registros[0].motivo == "Matrícula no coincide."


class TestBootstrapAdmin:
    def test_crear_admin_crea_la_cuenta(self, _base_de_datos_temporal):
        from backend.cli import crear_admin

        admin = crear_admin("nuevo.admin@nexus.local", "ContraseñaSegura123", engine_=_base_de_datos_temporal)
        assert admin.id is not None
        assert admin.rol.value == "admin"

    def test_crear_admin_duplicado_falla(self, _base_de_datos_temporal):
        from backend.cli import crear_admin

        crear_admin("dup@nexus.local", "ContraseñaSegura123", engine_=_base_de_datos_temporal)
        try:
            crear_admin("dup@nexus.local", "OtraContraseña123", engine_=_base_de_datos_temporal)
            assert False, "debía fallar por email duplicado"
        except ValueError:
            pass

    def test_instalacion_sin_bootstrap_no_tiene_admin(self, _base_de_datos_temporal):
        from backend.models.cuenta import CuentaMedico, RolCuenta

        with Session(_base_de_datos_temporal) as session:
            admins = session.exec(
                select(CuentaMedico).where(CuentaMedico.rol == RolCuenta.ADMIN)
            ).all()
            assert admins == []


class TestValidacionDeOrigenEnAprobarYRechazar:
    def test_aprobar_con_origen_ajeno_devuelve_403_y_no_cambia_nada(
        self, client_admin, cuenta_medico_pendiente, _base_de_datos_temporal
    ):
        resp = client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/aprobar",
            json={"fuente_consultada": "REFEPS"},
            headers={"Origin": "https://sitio-ajeno.example"},
        )
        assert resp.status_code == 403

        from backend.models.cuenta import CuentaMedico, EstadoCuenta

        with Session(_base_de_datos_temporal) as session:
            cuenta = session.get(CuentaMedico, cuenta_medico_pendiente.id)
            assert cuenta.estado == EstadoCuenta.PENDIENTE
            assert (
                session.exec(
                    select(DecisionAuditoria).where(
                        DecisionAuditoria.cuenta_id == cuenta_medico_pendiente.id
                    )
                ).first()
                is None
            )

    def test_rechazar_con_origen_ajeno_devuelve_403_y_no_cambia_nada(
        self, client_admin, cuenta_medico_pendiente, _base_de_datos_temporal
    ):
        resp = client_admin.post(
            f"/api/admin/cuentas/{cuenta_medico_pendiente.id}/rechazar",
            json={"motivo": "Matrícula no coincide."},
            headers={"Origin": "https://sitio-ajeno.example"},
        )
        assert resp.status_code == 403

        from backend.models.cuenta import CuentaMedico, EstadoCuenta

        with Session(_base_de_datos_temporal) as session:
            cuenta = session.get(CuentaMedico, cuenta_medico_pendiente.id)
            assert cuenta.estado == EstadoCuenta.PENDIENTE
            assert (
                session.exec(
                    select(DecisionAuditoria).where(
                        DecisionAuditoria.cuenta_id == cuenta_medico_pendiente.id
                    )
                ).first()
                is None
            )
