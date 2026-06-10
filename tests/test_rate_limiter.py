"""Tests para RateLimiter, CircuitBreaker y with_fallback."""

import asyncio
import pytest

from backend.external.rate_limiter import (
    RateLimiter,
    ApiCircuitBreaker,
    CircuitState,
    ExternalApiError,
    ApiUnavailableError,
    with_fallback,
)


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limiter_permite_llamadas_dentro_del_limite():
    limiter = RateLimiter(requests_per_second=10)
    # 5 llamadas deben pasar sin espera significativa
    start = asyncio.get_event_loop().time()
    for _ in range(5):
        async with limiter:
            pass
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 1.0  # No debería haber esperado


@pytest.mark.asyncio
async def test_rate_limiter_como_context_manager():
    limiter = RateLimiter(requests_per_second=100)
    async with limiter:
        pass  # No debe explotar


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_estado_inicial_closed():
    cb = ApiCircuitBreaker("TestAPI")
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available is True


@pytest.mark.asyncio
async def test_circuit_breaker_se_abre_al_superar_threshold():
    cb = ApiCircuitBreaker("TestAPI", failure_threshold=3)

    for _ in range(3):
        try:
            async with cb:
                raise ValueError("Simulated failure")
        except ValueError:
            pass

    assert cb.state == CircuitState.OPEN
    assert cb.is_available is False


@pytest.mark.asyncio
async def test_circuit_breaker_abierto_lanza_api_unavailable():
    cb = ApiCircuitBreaker("TestAPI", failure_threshold=2, recovery_timeout=9999)

    for _ in range(2):
        try:
            async with cb:
                raise ValueError("Simulated failure")
        except ValueError:
            pass

    with pytest.raises(ApiUnavailableError):
        async with cb:
            pass


@pytest.mark.asyncio
async def test_circuit_breaker_reset_manual():
    cb = ApiCircuitBreaker("TestAPI", failure_threshold=1)
    try:
        async with cb:
            raise ValueError("fail")
    except ValueError:
        pass

    cb.reset()
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_exito_resetea_contador():
    cb = ApiCircuitBreaker("TestAPI", failure_threshold=3)

    # 2 fallos — no suficiente para abrir
    for _ in range(2):
        try:
            async with cb:
                raise ValueError("fail")
        except ValueError:
            pass

    # 1 éxito — resetea contador
    async with cb:
        pass

    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


# ---------------------------------------------------------------------------
# with_fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_fallback_devuelve_resultado_normal():
    @with_fallback(fallback_value=[], api_name="TestAPI")
    async def buscar():
        return ["resultado"]

    result = await buscar()
    assert result == ["resultado"]


@pytest.mark.asyncio
async def test_with_fallback_captura_external_api_error():
    @with_fallback(fallback_value=[], api_name="TestAPI")
    async def buscar():
        raise ExternalApiError("TestAPI", "timeout")

    result = await buscar()
    assert result == []


@pytest.mark.asyncio
async def test_with_fallback_captura_exception_generica():
    @with_fallback(fallback_value={"error": True}, api_name="TestAPI")
    async def buscar():
        raise ConnectionError("network error")

    result = await buscar()
    assert result == {"error": True}


@pytest.mark.asyncio
async def test_with_fallback_preserva_nombre_funcion():
    @with_fallback(fallback_value=None, api_name="TestAPI")
    async def mi_funcion():
        pass

    assert mi_funcion.__name__ == "mi_funcion"
