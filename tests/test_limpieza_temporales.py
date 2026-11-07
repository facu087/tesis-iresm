"""
Tests de la limpieza automática de datos vencidos (Sprint 5 — tarjeta #56).

Herméticos: base SQLite en memoria, reloj pasado por parámetro y `dormir`
inyectado. Ningún `sleep` real, ninguna llamada a la red. Se corren también
con el bloqueador de red para dejarlo documentado:

    PYTHONPATH=scripts pytest tests/test_limpieza_temporales.py -p pytest_sin_red -q

Cubren tres cosas:

1. La purga borra exactamente las sesiones vencidas y ninguna viva.
2. El disparo automático (bucle de fondo + `lifespan`) y su tolerancia a
   fallos: nunca levanta, nunca rompe el arranque.
3. El invariante que reemplaza la premisa original de la tarjeta: un análisis
   completo no deja el documento clínico en disco. No hay archivos temporales
   que borrar porque nunca se crean, y este test lo fija para que una
   regresión futura rompa acá.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.auth.sesiones import crear_sesion, resolver_sesion
from backend.mantenimiento import limpieza
from backend.models.cuenta import CuentaMedico, RolCuenta
from backend.models.sesion import Sesion

_AHORA = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)


def _engine():
    """Engine en memoria con `StaticPool`: la base sobrevive entre sesiones."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _crear_cuenta(session: Session) -> CuentaMedico:
    cuenta = CuentaMedico(
        email="ana@hospital.example", password_hash="x", rol=RolCuenta.MEDICO
    )
    session.add(cuenta)
    session.commit()
    session.refresh(cuenta)
    return cuenta


def _sesion(cuenta_id: int, token: str, *, expira_en: datetime) -> Sesion:
    return Sesion(
        id=token,
        cuenta_id=cuenta_id,
        creada_en=expira_en - timedelta(minutes=60),
        expira_en=expira_en,
    )


def _ids_en_base(engine) -> set[str]:
    with Session(engine) as session:
        return {fila.id for fila in session.exec(select(Sesion)).all()}


# ── 1. Qué borra la purga ────────────────────────────────────────────────────


class TestPurgaDeSesionesExpiradas:
    """
    `purgar_sesiones_expiradas()` borra solo lo vencido, con el reloj que se le
    pasa. Nada de esperar: el borde se prueba fijando `ahora`.
    """

    def test_borra_la_vencida_y_deja_la_viva(self):
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            session.add(_sesion(cuenta.id, "viva", expira_en=_AHORA + timedelta(minutes=30)))
            session.add(_sesion(cuenta.id, "vencida", expira_en=_AHORA - timedelta(minutes=1)))
            session.commit()

            borradas = limpieza.purgar_sesiones_expiradas(session, ahora=_AHORA)

        assert borradas == 1
        assert _ids_en_base(engine) == {"viva"}

    def test_la_que_vence_exactamente_ahora_se_borra(self):
        """
        Mismo comparador que `resolver_sesion()` (`expira_en <= ahora`): una
        sesión que vence justo ahora ya era inservible, así que se borra.
        """
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            session.add(_sesion(cuenta.id, "al-borde", expira_en=_AHORA))
            session.commit()

            assert limpieza.purgar_sesiones_expiradas(session, ahora=_AHORA) == 1

        assert _ids_en_base(engine) == set()

    def test_sin_sesiones_vencidas_no_borra_nada(self):
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            for i in range(3):
                session.add(
                    _sesion(cuenta.id, f"viva-{i}", expira_en=_AHORA + timedelta(hours=i + 1))
                )
            session.commit()

            assert limpieza.purgar_sesiones_expiradas(session, ahora=_AHORA) == 0

        assert len(_ids_en_base(engine)) == 3

    def test_sobre_una_tabla_vacia_devuelve_cero(self):
        engine = _engine()
        with Session(engine) as session:
            assert limpieza.purgar_sesiones_expiradas(session, ahora=_AHORA) == 0

    def test_no_borra_la_cuenta_duena_de_la_sesion(self):
        """La limpieza toca `sesion`, nunca `cuenta_medico` ni la auditoría."""
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            session.add(_sesion(cuenta.id, "vencida", expira_en=_AHORA - timedelta(days=1)))
            session.commit()

            limpieza.purgar_sesiones_expiradas(session, ahora=_AHORA)

        with Session(engine) as session:
            assert session.get(CuentaMedico, 1) is not None


class TestLaPurgaNoCortaUnaSesionViva:
    """
    Integración con `auth.sesiones`: lo que la purga borra ya no servía, y lo
    que sobrevive sigue autenticando. Es la garantía de "no rompe nada en curso".
    """

    def test_la_sesion_viva_sigue_resolviendo_despues_de_la_purga(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
        monkeypatch.setenv("SESSION_TTL_MINUTES", "60")
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            cookie_viva = crear_sesion(session, cuenta)

            limpieza.purgar_sesiones_expiradas(session)

            resuelta = resolver_sesion(session, cookie_viva)
            assert resuelta is not None
            assert resuelta.id == cuenta.id

    def test_la_vencida_ya_no_resolvia_antes_de_borrarla(self, monkeypatch):
        """
        Antes de la purga, `resolver_sesion()` ya devolvía `None` para la fila
        vencida: borrarla no cambia el comportamiento observable de ninguna
        solicitud, solo deja de guardar el dato.
        """
        monkeypatch.setenv("SECRET_KEY", "clave-de-test-no-usar-en-produccion")
        monkeypatch.setenv("SESSION_TTL_MINUTES", "60")
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            vencida_hace_rato = datetime.now(timezone.utc) - timedelta(hours=3)
            cookie_vencida = crear_sesion(session, cuenta, ahora=vencida_hace_rato)

            assert resolver_sesion(session, cookie_vencida) is None  # ya inservible

            assert limpieza.purgar_sesiones_expiradas(session) == 1
            assert resolver_sesion(session, cookie_vencida) is None  # sigue igual


# ── 2. La pasada completa y su tolerancia a fallos ───────────────────────────


class TestEjecutarLimpieza:
    """`ejecutar_limpieza()` nunca levanta y nunca filtra identificadores."""

    def test_devuelve_el_conteo_y_ok(self):
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            session.add(_sesion(cuenta.id, "v1", expira_en=_AHORA - timedelta(minutes=1)))
            session.add(_sesion(cuenta.id, "v2", expira_en=_AHORA - timedelta(days=2)))
            session.add(_sesion(cuenta.id, "viva", expira_en=_AHORA + timedelta(minutes=5)))
            session.commit()

        resultado = limpieza.ejecutar_limpieza(engine=engine, ahora=_AHORA)

        assert resultado.ok is True
        assert resultado.fallo is None
        assert resultado.sesiones_expiradas_borradas == 2
        assert resultado.ejecutada_en == _AHORA
        assert resultado.duracion_segundos >= 0.0
        assert _ids_en_base(engine) == {"viva"}

    def test_un_fallo_de_la_base_no_levanta_y_deja_fallback_explicito(self):
        """
        Engine sobre una base sin el esquema: el `DELETE` falla. La pasada
        tiene que devolver `ok=False` con el tipo de excepción, no propagar —
        si propagara, tumbaría el arranque del backend.
        """
        engine_sin_esquema = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        resultado = limpieza.ejecutar_limpieza(engine=engine_sin_esquema, ahora=_AHORA)

        assert resultado.ok is False
        assert resultado.sesiones_expiradas_borradas == 0
        assert resultado.fallo == "OperationalError"

    def test_el_log_del_fallo_no_trae_el_mensaje_de_la_excepcion(self, capsys):
        """
        El mensaje de un error de base puede arrastrar valores de la fila. Se
        loguea el tipo de excepción y nada más.
        """
        engine_sin_esquema = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        limpieza.ejecutar_limpieza(engine=engine_sin_esquema, ahora=_AHORA)
        err = capsys.readouterr().err

        assert "OperationalError" in err
        assert "no such table" not in err.lower()
        assert "sesion" not in err  # tampoco el nombre de la tabla del SQL

    def test_usa_el_engine_activo_de_backend_db_si_no_se_le_pasa_uno(self, monkeypatch):
        """
        El engine se resuelve en cada llamada, no al importar: es lo que
        permite que el `lifespan` y los tests compartan el mismo mecanismo.
        """
        from backend import db as db_module

        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            session.add(_sesion(cuenta.id, "vencida", expira_en=_AHORA - timedelta(days=1)))
            session.commit()

        monkeypatch.setattr(db_module, "engine", engine)
        resultado = limpieza.ejecutar_limpieza(ahora=_AHORA)

        assert resultado.sesiones_expiradas_borradas == 1


class TestElLogNoFiltraDatosPersonales:
    """
    Regla del proyecto: los logs llevan conteos y rutas genéricas. Nada que
    identifique a una cuenta, a una sesión ni a un paciente.
    """

    def test_solo_informa_el_conteo(self, capsys):
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            token_secreto = "token-de-sesion-muy-secreto"
            session.add(_sesion(cuenta.id, token_secreto, expira_en=_AHORA - timedelta(hours=1)))
            session.commit()

        limpieza.ejecutar_limpieza(engine=engine, ahora=_AHORA)
        err = capsys.readouterr().err

        assert "1 sesiones expiradas borradas" in err
        assert token_secreto not in err
        assert "ana@hospital.example" not in err
        assert "hospital" not in err


# ── 3. El disparo automático ─────────────────────────────────────────────────


class TestIntervaloConfigurable:
    """`SESSION_CLEANUP_INTERVAL_MINUTES` decide cada cuánto corre y si corre."""

    def test_sin_la_variable_usa_el_default_de_15(self, monkeypatch):
        monkeypatch.delenv("SESSION_CLEANUP_INTERVAL_MINUTES", raising=False)
        assert limpieza.intervalo_minutos() == 15

    def test_vacia_usa_el_default(self, monkeypatch):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "   ")
        assert limpieza.intervalo_minutos() == 15

    def test_toma_el_valor_configurado(self, monkeypatch):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "5")
        assert limpieza.intervalo_minutos() == 5

    def test_cero_apaga_la_tarea(self, monkeypatch):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "0")
        assert limpieza.intervalo_minutos() == 0

    def test_un_valor_negativo_se_trata_como_apagada(self, monkeypatch):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "-10")
        assert limpieza.intervalo_minutos() == 0

    def test_un_valor_no_entero_cae_al_default_y_avisa(self, monkeypatch, capsys):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "cada-tanto")
        assert limpieza.intervalo_minutos() == 15
        assert "no es un número entero" in capsys.readouterr().err


class TestBucleDeFondo:
    """
    El bucle corre una pasada por intervalo. El reloj se controla inyectando
    `dormir`: cero `sleep` real, y el test termina en milisegundos.
    """

    @pytest.mark.asyncio
    async def test_corre_una_pasada_por_intervalo_sin_dormir_de_verdad(self):
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            for i in range(3):
                session.add(
                    _sesion(cuenta.id, f"vencida-{i}", expira_en=_AHORA - timedelta(hours=1))
                )
            session.commit()

        esperas: list[float] = []

        async def dormir_falso(segundos: float) -> None:
            esperas.append(segundos)
            if len(esperas) == 3:
                # Es la salida real: el `lifespan` cancela la tarea al apagar.
                raise asyncio.CancelledError

        arranque = time.perf_counter()
        with pytest.raises(asyncio.CancelledError):
            await limpieza.bucle_de_limpieza(
                intervalo_segundos=900, engine=engine, dormir=dormir_falso
            )
        transcurrido = time.perf_counter() - arranque

        assert esperas == [900, 900, 900]          # tres pasadas, un intervalo cada una
        assert transcurrido < 1.0                   # no durmió de verdad
        assert _ids_en_base(engine) == set()        # la primera pasada ya limpió

    @pytest.mark.asyncio
    async def test_la_primera_pasada_corre_antes_del_primer_dormir(self):
        """
        Importa para el caso "el backend estuvo caído más que el TTL": al
        volver, las vencidas se borran ya, no dentro de un intervalo.
        """
        engine = _engine()
        with Session(engine) as session:
            cuenta = _crear_cuenta(session)
            session.add(_sesion(cuenta.id, "vencida", expira_en=_AHORA - timedelta(days=1)))
            session.commit()

        estado_al_primer_dormir: list[set[str]] = []

        async def dormir_falso(_: float) -> None:
            estado_al_primer_dormir.append(_ids_en_base(engine))
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await limpieza.bucle_de_limpieza(
                intervalo_segundos=900, engine=engine, dormir=dormir_falso
            )

        assert estado_al_primer_dormir == [set()]

    @pytest.mark.asyncio
    async def test_una_pasada_que_falla_no_mata_el_bucle(self):
        """
        Con un engine sin esquema, cada pasada falla. El bucle tiene que seguir
        intentando: si muriera, el backend quedaría sin limpieza en silencio.
        """
        engine_roto = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        pasadas = 0

        async def dormir_falso(_: float) -> None:
            nonlocal pasadas
            pasadas += 1
            if pasadas == 3:
                raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await limpieza.bucle_de_limpieza(
                intervalo_segundos=900, engine=engine_roto, dormir=dormir_falso
            )

        assert pasadas == 3  # siguió después de fallar dos veces

    @pytest.mark.asyncio
    async def test_detener_tarea_cancela_y_no_levanta(self):
        engine = _engine()

        async def dormir_largo(_: float) -> None:
            await asyncio.sleep(3600)  # lo cancelamos antes; no se espera de verdad

        tarea = asyncio.create_task(
            limpieza.bucle_de_limpieza(
                intervalo_segundos=900, engine=engine, dormir=dormir_largo
            )
        )
        await asyncio.sleep(0)  # dejar que arranque

        await limpieza.detener_tarea(tarea)  # no debe levantar

        assert tarea.cancelled() or tarea.done()

    @pytest.mark.asyncio
    async def test_detener_tarea_tolera_none(self):
        await limpieza.detener_tarea(None)  # la tarea pudo no haber arrancado


class TestIniciarTarea:
    """`iniciar_tarea()` respeta la configuración y nunca rompe el arranque."""

    @pytest.mark.asyncio
    async def test_con_intervalo_positivo_crea_la_tarea(self, monkeypatch):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "15")
        engine = _engine()

        tarea = limpieza.iniciar_tarea(engine=engine)
        assert tarea is not None
        await limpieza.detener_tarea(tarea)

    @pytest.mark.asyncio
    async def test_con_cero_no_crea_la_tarea_y_lo_avisa(self, monkeypatch, capsys):
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "0")

        assert limpieza.iniciar_tarea() is None
        assert "apagada" in capsys.readouterr().err

    def test_sin_event_loop_devuelve_none_en_vez_de_levantar(self, monkeypatch, capsys):
        """
        `asyncio.create_task()` sin loop corriendo levanta `RuntimeError`. El
        backend tiene que arrancar igual, sin limpieza automática.
        """
        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "15")

        assert limpieza.iniciar_tarea() is None
        assert "no se pudo arrancar" in capsys.readouterr().err


class TestCableadoEnElLifespan:
    """
    El `lifespan` de FastAPI arranca la limpieza al levantar y la detiene al
    apagar. Se verifica con un espía sobre `ejecutar_limpieza`, sin tocar la red.
    """

    def test_levantar_la_app_corre_una_pasada_de_limpieza(self, monkeypatch):
        from fastapi.testclient import TestClient

        from backend.main import app

        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "15")
        pasadas: list[limpieza.ResultadoLimpieza] = []
        original = limpieza.ejecutar_limpieza

        def espia(**kwargs):
            resultado = original(**kwargs)
            pasadas.append(resultado)
            return resultado

        monkeypatch.setattr(limpieza, "ejecutar_limpieza", espia)

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

        assert len(pasadas) >= 1
        assert pasadas[0].ok is True

    def test_con_la_limpieza_apagada_la_app_levanta_igual(self, monkeypatch):
        from fastapi.testclient import TestClient

        from backend.main import app

        monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_MINUTES", "0")

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

    def test_si_la_limpieza_no_arranca_la_app_levanta_igual(self, monkeypatch):
        """
        El arranque del backend nunca depende de la limpieza: si
        `iniciar_tarea()` devolviera `None` por un fallo, `/health` responde.
        """
        from fastapi.testclient import TestClient

        from backend.main import app

        monkeypatch.setattr(limpieza, "iniciar_tarea", lambda **_: None)

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200


# ── 4. El invariante: el análisis no deja el documento en disco ───────────────


_CASO_CLINICO = (
    "Paciente masculino de 42 años con polineuropatía axonal sensitivomotora "
    "de cuatro años de evolución. Electromiograma con denervación distal."
)


class TestElAnalisisNoDejaArchivosEnDisco:
    """
    Invariante que reemplaza la premisa original de la tarjeta #56.

    No hay "archivos temporales de sesión" que borrar porque el pipeline nunca
    los crea: el PDF llega como bytes y se procesa en memoria. Estos tests
    fijan esa propiedad; si alguien agrega una escritura a disco del documento
    clínico, rompen acá en vez de pasar inadvertidos hasta la auditoría.
    """

    def test_la_extraccion_de_un_pdf_no_escribe_nada(self, tmp_path, monkeypatch):
        """`extract()` sobre un PDF real no deja ningún archivo en el cwd."""
        from backend.ingestion.extractor import extract

        pdf = _pdf_de_una_pagina(_CASO_CLINICO)
        monkeypatch.chdir(tmp_path)

        antes = _archivos(tmp_path)
        texto = extract("historia_clinica.pdf", pdf)
        despues = _archivos(tmp_path)

        assert "42" in texto  # efectivamente extrajo el contenido
        assert despues == antes == set()

    def test_el_analisis_completo_solo_escribe_la_telemetria_sin_texto_clinico(
        self, tmp_path, monkeypatch, client_medico_verificado_sin_relanzar
    ):
        """
        Un `POST /api/analyze` completo en modo mock, con el cwd en `tmp_path`:
        el único archivo que aparece es el JSONL de telemetría de costos, y no
        contiene ni un fragmento del texto clínico.
        """
        from backend.mock.mode import ENV_VAR

        monkeypatch.setenv(ENV_VAR, "1")
        monkeypatch.chdir(tmp_path)

        assert _archivos(tmp_path) == set()

        with (
            patch("backend.api.router.normalize", return_value=_CASO_CLINICO),
            patch(
                "backend.api.router.orchestrator.run_round_1",
                new_callable=AsyncMock,
                return_value=_reporte_vacio(),
            ),
            patch(
                "backend.api.router.debate.run_debate",
                new_callable=AsyncMock,
                return_value=_reporte_vacio(),
            ),
            patch(
                "backend.api.router.verify_report_sources",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "backend.api.router.TrialNavigatorAgent.navigate",
                new_callable=AsyncMock,
                return_value=_navegacion_vacia(),
            ),
        ):
            response = client_medico_verificado_sin_relanzar.post(
                "/api/analyze", data={"text": _CASO_CLINICO}
            )

        assert response.status_code == 200, response.text

        creados = _archivos(tmp_path)
        assert creados == {"output/costos.jsonl"}, (
            "el análisis escribió archivos inesperados en disco: "
            f"{sorted(creados - {'output/costos.jsonl'})}"
        )

        telemetria = (tmp_path / "output" / "costos.jsonl").read_text(encoding="utf-8")
        for fragmento in ("polineuropatía", "42 años", "Electromiograma"):
            assert fragmento not in telemetria

    def test_el_backend_no_usa_tempfile_ni_directorios_de_subida(self):
        """
        Guarda estructural: ningún módulo del backend crea archivos temporales
        ni un directorio de subidas. Si mañana alguien lo agrega, este test
        obliga a pasar por la discusión de privacidad en vez de deslizarlo.
        """
        import re

        raiz = Path(__file__).resolve().parents[1] / "backend"
        # Se busca uso real, no la mención en prosa: `limpieza.py` documenta
        # justamente que nada de esto aparece en el backend.
        prohibidos = (
            r"^\s*import\s+tempfile",
            r"^\s*from\s+tempfile\s+import",
            r"\btempfile\.",
            r"\bNamedTemporaryFile\(",
            r"\bmkstemp\(",
            r"\bmkdtemp\(",
            r"\bTemporaryDirectory\(",
        )
        hallazgos: list[str] = []

        for archivo in raiz.rglob("*.py"):
            texto = archivo.read_text(encoding="utf-8")
            for patron in prohibidos:
                if re.search(patron, texto, re.MULTILINE):
                    hallazgos.append(f"{archivo.name}: {patron}")

        assert hallazgos == [], (
            "apareció manejo de archivos temporales en el backend; hay que "
            f"decidir su ciclo de vida y limpieza: {hallazgos}"
        )


# ── Ayudantes del invariante ─────────────────────────────────────────────────


def _archivos(raiz: Path) -> set[str]:
    """Rutas relativas (con `/`) de todos los archivos bajo `raiz`."""
    return {
        p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file()
    }


def _pdf_de_una_pagina(texto: str) -> bytes:
    """PDF mínimo en memoria con `texto`, para no depender de un fixture binario."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.drawString(72, 750, texto[:90])
    c.showPage()
    c.save()
    return buffer.getvalue()


def _reporte_vacio():
    from backend.models.report import Report

    return Report(case_summary="resumen de test", hypotheses=[], agent_outputs=[])


def _navegacion_vacia():
    from backend.models.trial import TrialNavigationResult, TrialSearchSummary

    return TrialNavigationResult(
        summary=TrialSearchSummary(
            estado_clinicaltrials="sin_consulta", estado_orphanet="sin_consulta"
        )
    )
