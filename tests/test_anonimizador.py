"""
Tests de la anonimización de texto clínico (backend/ingestion/anonimizador.py).

Herméticos: reglas deterministas, sin red ni LLM.

Los tests están escritos en dos direcciones, y las dos importan igual:
qué se enmascara (privacidad) y **qué NO se enmascara** (el texto clínico que
el sistema necesita leer). Una anonimización que destruye el caso no sirve.
"""

import re
from pathlib import Path

import pytest

from backend.ingestion.anonimizador import (
    ETIQUETAS,
    InformeAnonimizacion,
    anonimizar,
)

_RAIZ = Path(__file__).parent.parent


def _mascaras(texto: str) -> str:
    return anonimizar(texto)[0]


# ── Lo que tiene que enmascararse ─────────────────────────────────────────────

class TestDocumentos:
    @pytest.mark.parametrize("texto", [
        "DNI 32.456.789",
        "D.N.I. 32456789",
        "dni: 32.456.789",
        "documento 32456789",
        "LC 5.123.456",
        "CUIL 20-32456789-3",
        "CUIT 30-12345678-9",
    ])
    def test_documentos_argentinos(self, texto):
        assert ETIQUETAS["documento"] in _mascaras(texto)
        assert "32456789" not in _mascaras(texto).replace(".", "")


class TestHistoriaClinica:
    @pytest.mark.parametrize("texto", [
        "Historia clínica N° HC-44821",
        "historia clinica 123456",
        "H.C. 998877",
        "afiliado 4455667",
        "legajo 00123",
    ])
    def test_identificadores_de_registro(self, texto):
        assert ETIQUETAS["historia_clinica"] in _mascaras(texto)


class TestContacto:
    @pytest.mark.parametrize("texto", [
        "Tel: 0351 155-678901",
        "Teléfono 351 678-9012",
        "Celular: +54 9 351 6789012",
        "contacto 4567890",
    ])
    def test_telefonos(self, texto):
        assert ETIQUETAS["telefono"] in _mascaras(texto)

    def test_email(self):
        salida = _mascaras("Email: jcperez@example.com")
        assert ETIQUETAS["email"] in salida
        assert "jcperez" not in salida


class TestFechas:
    @pytest.mark.parametrize("texto", [
        "Fecha de nacimiento: 14/07/1983",
        "ingresó el 3-11-24",
        "Primera consulta el 3 de marzo de 2024",
        "nacido el 12 de setiembre de 1981",
    ])
    def test_fechas_de_calendario(self, texto):
        assert ETIQUETAS["fecha"] in _mascaras(texto)


class TestNombres:
    @pytest.mark.parametrize("texto,nombre", [
        ("Paciente: Juan Carlos Pérez", "Juan Carlos Pérez"),
        ("Sr. Roberto Gómez", "Roberto Gómez"),
        ("Sra. Ana María de la Fuente", "Ana María de la Fuente"),
        ("Derivado por la Dra. María Elena Gutiérrez", "María Elena Gutiérrez"),
        ("Atendido por Lic. Ana Gómez", "Ana Gómez"),
        ("a cargo de el Dr. Pedro Álvarez", "Pedro Álvarez"),
    ])
    def test_nombres_con_marcador(self, texto, nombre):
        salida = _mascaras(texto)
        assert ETIQUETAS["nombre"] in salida
        assert nombre.split()[-1] not in salida

    def test_el_titulo_se_conserva_y_el_nombre_no(self):
        """
        El título dice de quién se habla (médico vs. paciente) sin identificar
        a nadie. Si se enmascarara el título en vez del nombre —que es lo que
        pasaba cuando "Dra" entraba como nombre— el dato personal sobreviviría.
        """
        salida = _mascaras("Derivado por la Dra. María Elena Gutiérrez")
        assert "Dra." in salida
        assert "Gutiérrez" not in salida


class TestDomicilio:
    def test_direccion_con_abreviatura(self):
        """
        Las direcciones están llenas de abreviaturas con punto. Cortar en el
        primer punto dejaba la calle a la vista.
        """
        salida = _mascaras("Domicilio: Av. Colón 1234, Villa Carlos Paz")
        assert ETIQUETAS["domicilio"] in salida
        assert "Colón" not in salida
        assert "1234" not in salida


# ── Lo que NO tiene que tocarse ───────────────────────────────────────────────

class TestNoDestruyeElTextoClinico:
    @pytest.mark.parametrize("texto", [
        "Tensión arterial 120/80 mmHg",
        "Fuerza 4/5 en miembros inferiores",
        "HbA1c 8.2%",
        "Creatinina 1.2 mg/dl",
        "Leucocitos 5400, neutrófilos 3200",
        "Se descarta enfermedad de Charcot-Marie-Tooth",
        "síndrome de Guillain-Barré",
        "Anticuerpos anti-Hu, anti-Yo y anti-Ri negativos",
        "pregabalina 150 mg/día",
        "Panel genético CMT de 40 genes negativo",
        "paciente masculino de 42 años",
        "variante p.Val30Met en el gen TTR",
        "18 meses de evolución",
    ])
    def test_contenido_clinico_intacto(self, texto):
        assert _mascaras(texto) == texto

    def test_el_caso_base_del_proyecto_no_se_modifica(self):
        """
        El caso de prueba de la tesis ya viene anonimizado a mano. Si la
        anonimización lo tocara, estaría destruyendo contenido clínico.
        """
        fuente = (_RAIZ / "scripts" / "poc_test.py").read_text(encoding="utf-8")
        caso = re.search(r'CASO_CLINICO = """(.*?)"""', fuente, re.S).group(1).strip()
        salida, informe = anonimizar(caso)
        assert salida == caso
        assert not informe.hubo_hallazgos


# ── El informe ────────────────────────────────────────────────────────────────

class TestInforme:
    def test_cuenta_por_categoria(self):
        _, informe = anonimizar("Paciente: Juan Pérez. DNI 32.456.789. Email: a@b.com")
        assert informe.reemplazos["nombre"] == 1
        assert informe.reemplazos["documento"] == 1
        assert informe.reemplazos["email"] == 1
        assert informe.total == 3

    def test_el_informe_no_contiene_los_valores_encontrados(self):
        """
        El informe va a los logs y al reporte. Si trajera lo que se acaba de
        enmascarar, la anonimización no serviría de nada.
        """
        texto = "Paciente: Juan Carlos Pérez. DNI 32.456.789. Email: jcperez@example.com"
        _, informe = anonimizar(texto)
        resumen = informe.resumen()
        for secreto in ("Juan", "Pérez", "32.456.789", "32456789", "jcperez", "example.com"):
            assert secreto not in resumen
        assert secreto not in repr(informe.reemplazos)

    def test_sin_hallazgos(self):
        informe = anonimizar("Paciente masculino de 42 años con neuropatía axonal.")[1]
        assert not informe.hubo_hallazgos
        assert "no se detectaron" in informe.resumen()

    def test_texto_vacio(self):
        salida, informe = anonimizar("")
        assert salida == ""
        assert informe.total == 0

    def test_informe_vacio_por_defecto(self):
        assert InformeAnonimizacion().total == 0


# ── Integración con el pipeline ───────────────────────────────────────────────

class TestIntegracionConElRouter:
    def test_el_router_anonimiza_antes_de_construir_el_caso(self):
        """
        Guarda contra regresión del orden: si alguien mueve la anonimización
        después de `ClinicalCase(...)`, el texto identificable ya habría salido
        hacia los agentes.
        """
        fuente = (_RAIZ / "backend" / "api" / "router.py").read_text(encoding="utf-8")
        pos_anonimizar = fuente.index("anonimizar, normalized")
        pos_caso = fuente.index("ClinicalCase(raw_text=normalized)")
        assert pos_anonimizar < pos_caso
