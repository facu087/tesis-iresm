"""
La suite no puede salir a la red (tests/conftest.py).

Un test que intenta conectarse a un host externo falla aunque el código atrape
el error: el fixture automático `_red_bloqueada` lo detecta al terminar.
Estos tests limpian el registro de intentos al final para no fallar ellos mismos.
"""

import socket

import pytest

from tests import conftest


@pytest.mark.parametrize(
    "conectar",
    [
        lambda: socket.getaddrinfo("example.com", 443),
        lambda: socket.create_connection(("example.com", 443), timeout=1),
        lambda: socket.socket().connect(("93.184.216.34", 443)),
    ],
    ids=["getaddrinfo", "create_connection", "connect"],
)
def test_conexion_externa_queda_bloqueada_y_registrada(conectar):
    with pytest.raises(ConnectionError, match="red bloqueada"):
        conectar()
    assert conftest.INTENTOS_DE_RED
    conftest.INTENTOS_DE_RED.clear()


def test_localhost_sigue_permitido():
    assert socket.getaddrinfo("localhost", 80)
    assert conftest.INTENTOS_DE_RED == []
