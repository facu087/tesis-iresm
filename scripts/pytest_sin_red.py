"""
Plugin de pytest que bloquea toda conexión de red saliente (salvo localhost).

Uso: PYTHONPATH=scripts pytest -p pytest_sin_red tests/...
Lo usa scripts/demo_tests_rag_hermeticos.py como evidencia del hallazgo B.
Un test que falla con esto activo NO es hermético: depende de la red.
Cada intento de conexión queda registrado con el host de destino.
"""
import socket

_real_connect = socket.socket.connect
_real_create_connection = socket.create_connection
_real_getaddrinfo = socket.getaddrinfo
INTENTOS: list[str] = []


def _es_local(host) -> bool:
    return str(host) in ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _bloquear(host) -> None:
    INTENTOS.append(str(host))
    raise ConnectionError(f"[sin_red] conexión bloqueada a {host}")


def _connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if not _es_local(host):
        _bloquear(host)
    return _real_connect(self, address)


def _create_connection(address, *args, **kwargs):
    if not _es_local(address[0]):
        _bloquear(address[0])
    return _real_create_connection(address, *args, **kwargs)


def _getaddrinfo(host, *args, **kwargs):
    if host is not None and not _es_local(host):
        _bloquear(host)
    return _real_getaddrinfo(host, *args, **kwargs)


def pytest_configure(config):
    socket.socket.connect = _connect
    socket.create_connection = _create_connection
    socket.getaddrinfo = _getaddrinfo


def pytest_terminal_summary(terminalreporter):
    hosts = sorted(set(INTENTOS))
    terminalreporter.write_line(f"[sin_red] intentos de conexión bloqueados: {len(INTENTOS)}")
    for h in hosts:
        terminalreporter.write_line(f"[sin_red]   -> {h} ({INTENTOS.count(h)} veces)")
