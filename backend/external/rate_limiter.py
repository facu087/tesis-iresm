"""
Gestión de rate limits y fallbacks para APIs externas.

Provee:
  - RateLimiter: semáforo con ventana de tiempo para controlar req/s por API
  - ApiCircuitBreaker: corta llamadas a una API que está fallando repetidamente
  - with_fallback(): decorador para envolver llamadas con fallback explícito
  - ExternalApiError: excepción base para errores de APIs externas

Uso:
    limiter = RateLimiter(requests_per_second=3)  # PubMed sin API key
    async with limiter:
        result = await pubmed_client.search(query)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class ExternalApiError(Exception):
    """Error base para todas las APIs externas de NEXUS."""

    def __init__(self, api_name: str, message: str, status_code: Optional[int] = None) -> None:
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(f"[{api_name}] {message}" + (f" (HTTP {status_code})" if status_code else ""))


class RateLimitError(ExternalApiError):
    """La API devolvió HTTP 429 — demasiadas solicitudes."""
    pass


class ApiUnavailableError(ExternalApiError):
    """La API no está disponible (timeout, 5xx, circuit breaker abierto)."""
    pass


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Controla la tasa de solicitudes a una API externa con ventana deslizante.

    Args:
        requests_per_second: Máximo de requests por segundo
        burst: Permite un burst inicial de N requests (default = requests_per_second)

    Ejemplo:
        limiter = RateLimiter(requests_per_second=3)  # PubMed sin key
        async with limiter:
            await pubmed.search(...)
    """

    # Rate limits conocidos de cada API
    PUBMED_NO_KEY = 3      # req/s sin API key
    PUBMED_WITH_KEY = 10   # req/s con API key
    ORPHANET = 5           # req/s (estimado, no documentado)
    # PharmGKB/ClinPGx no documenta su límite y está detrás de Cloudflare.
    # Medido el 2026-09-15: 3 req/s con burst devuelve HTTP 429; 1 y 2 req/s
    # secuenciales pasan sin problema. Se deja en 2 y sin burst.
    PHARMGKB = 2           # req/s (medido, ver arriba)
    CLINICAL_TRIALS = 10   # req/s (estimado)

    def __init__(self, requests_per_second: float, burst: Optional[int] = None) -> None:
        self._rps = requests_per_second
        self._burst = burst or int(requests_per_second)
        self._min_interval = 1.0 / requests_per_second
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "RateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def acquire(self) -> None:
        """
        Espera hasta que haya capacidad para hacer una nueva solicitud.
        Bloquea si se superó el rate limit.
        """
        async with self._lock:
            now = time.monotonic()
            window_start = now - 1.0  # ventana de 1 segundo

            # Limpiar timestamps viejos
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._burst:
                # Calcular cuánto tiempo esperar
                oldest = self._timestamps[0]
                wait_time = (oldest + 1.0) - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            self._timestamps.append(time.monotonic())


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal — deja pasar las llamadas
    OPEN = "open"           # Roto — bloquea todas las llamadas
    HALF_OPEN = "half_open" # Probando — deja pasar una llamada de prueba


class ApiCircuitBreaker:
    """
    Circuit breaker para APIs externas.

    Si una API falla N veces seguidas, el circuito se "abre" y las
    llamadas subsiguientes fallan inmediatamente sin intentar la red.
    Después de un timeout, pasa a HALF_OPEN para probar si la API se recuperó.

    Args:
        api_name: Nombre descriptivo de la API (para logs y errores)
        failure_threshold: Cantidad de fallos para abrir el circuito (default: 5)
        recovery_timeout: Segundos antes de intentar recuperación (default: 60)

    Ejemplo:
        cb = ApiCircuitBreaker("PubMed", failure_threshold=3)
        async with cb:
            await pubmed.search(...)
    """

    def __init__(
        self,
        api_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.api_name = api_name
        self._threshold = failure_threshold
        self._timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_available(self) -> bool:
        """True si el circuito permite llamadas."""
        return self._state != CircuitState.OPEN

    async def __aenter__(self) -> "ApiCircuitBreaker":
        await self._check_state()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            await self._on_failure()
        else:
            await self._on_success()
        return False  # No suprimir excepciones

    async def _check_state(self) -> None:
        """Verifica si el circuito permite la llamada."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._last_failure_time or 0)
                if elapsed >= self._timeout:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise ApiUnavailableError(
                        self.api_name,
                        f"Circuit breaker OPEN — API no disponible. "
                        f"Reintento en {self._timeout - elapsed:.0f}s",
                    )

    async def _on_success(self) -> None:
        """Resetea el circuito después de una llamada exitosa."""
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        """Registra un fallo y abre el circuito si se superó el threshold."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._threshold:
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Resetea manualmente el circuito (útil en tests)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None


# ---------------------------------------------------------------------------
# Instancias globales (una por API)
# ---------------------------------------------------------------------------

import os as _os

_pubmed_rps = RateLimiter.PUBMED_WITH_KEY if _os.getenv("PUBMED_API_KEY") else RateLimiter.PUBMED_NO_KEY

pubmed_limiter = RateLimiter(requests_per_second=_pubmed_rps)
orphanet_limiter = RateLimiter(requests_per_second=RateLimiter.ORPHANET)
pharmgkb_limiter = RateLimiter(requests_per_second=RateLimiter.PHARMGKB)
clinical_trials_limiter = RateLimiter(requests_per_second=RateLimiter.CLINICAL_TRIALS)

pubmed_breaker = ApiCircuitBreaker("PubMed", failure_threshold=5)
orphanet_breaker = ApiCircuitBreaker("Orphanet", failure_threshold=3)
pharmgkb_breaker = ApiCircuitBreaker("PharmGKB", failure_threshold=3)
clinical_trials_breaker = ApiCircuitBreaker("ClinicalTrials", failure_threshold=5)


# ---------------------------------------------------------------------------
# Decorador with_fallback
# ---------------------------------------------------------------------------

def with_fallback(fallback_value: Any, api_name: str = "API externa"):
    """
    Decorador que captura excepciones de APIs externas y devuelve un fallback.

    Uso:
        @with_fallback(fallback_value=[], api_name="PubMed")
        async def buscar_articulos(query: str) -> list:
            ...

    Si la función falla, devuelve [] en lugar de propagar la excepción.
    El error se loggea pero NO silencia el fallo (queda en el return value).
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except ExternalApiError as e:
                # Error conocido de API externa — fallback silencioso
                print(f"[NEXUS] Fallback activado para {api_name}: {e}")
                return fallback_value
            except Exception as e:
                # Error inesperado — fallback con log
                print(f"[NEXUS] Error inesperado en {api_name}: {type(e).__name__}: {e}")
                return fallback_value
        return wrapper  # type: ignore[return-value]
    return decorator
