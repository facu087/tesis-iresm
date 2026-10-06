"""
Aislamiento entre tests de los limitadores globales de `backend/external/rate_limiter.py`.

Los limitadores son objetos de módulo y cada test asíncrono corre en un event
loop propio. `RateLimiter.acquire()` duerme con el lock tomado cuando la ráfaga
del último segundo está agotada; si en ese momento hay otra corrutina esperando,
el lock queda ligado a ese loop. El test siguiente que vuelva a tener contención
recibe `RuntimeError: ... is bound to a different event loop`, que los clientes
externos tratan como una caída de la API: el resultado sale degradado en
silencio. Así fallaban de forma intermitente los tests del Agente 05.

Los dos tests de abajo provocan la misma contención, uno después del otro: sin
la fixture `_limitadores_aislados` de `tests/conftest.py`, el segundo falla.
"""

import asyncio
import time

import pytest

from backend.external.rate_limiter import clinical_trials_limiter


async def _dos_adquisiciones_con_rafaga_agotada() -> list[object]:
    """Agota la ráfaga del último segundo y pide dos turnos a la vez."""
    casi_vencido = time.monotonic() - 0.95  # la espera resultante ronda los 50 ms
    clinical_trials_limiter._timestamps.clear()
    clinical_trials_limiter._timestamps.extend(
        [casi_vencido] * clinical_trials_limiter._burst
    )
    return await asyncio.gather(
        clinical_trials_limiter.acquire(),
        clinical_trials_limiter.acquire(),
        return_exceptions=True,
    )


class TestLimitadorGlobalEntreTests:
    @pytest.mark.asyncio
    async def test_contencion_en_un_primer_loop(self):
        assert await _dos_adquisiciones_con_rafaga_agotada() == [None, None]

    @pytest.mark.asyncio
    async def test_contencion_en_un_segundo_loop(self):
        assert await _dos_adquisiciones_con_rafaga_agotada() == [None, None]

    def test_cada_test_arranca_sin_turnos_consumidos(self):
        assert len(clinical_trials_limiter._timestamps) == 0
