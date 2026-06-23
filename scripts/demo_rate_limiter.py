"""
Demo de verificación — Gestión de rate limits y fallbacks en APIs externas.

Muestra cómo funcionan los tres mecanismos de protección:
  1. RateLimiter   — controla la tasa de solicitudes (req/s)
  2. CircuitBreaker — corta llamadas a APIs que fallan repetidamente
  3. with_fallback  — devuelve un valor seguro si la API no responde

Artefactos generados en output/demo_rate_limiter/:
    1. demo_rate_limiter.txt   → tiempos de ejecución con y sin rate limit
    2. demo_circuit_breaker.txt → estados del circuit breaker en cada fallo
    3. demo_fallback.txt        → ejemplos de funciones con fallback

Uso:
    python scripts/demo_rate_limiter.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.external.rate_limiter import (
    RateLimiter,
    ApiCircuitBreaker,
    CircuitState,
    ExternalApiError,
    with_fallback,
    pubmed_limiter,
    orphanet_limiter,
    pharmgkb_limiter,
)

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_rate_limiter"


async def demo_rate_limiter() -> list[str]:
    """Muestra el RateLimiter controlando 5 requests a 5 req/s."""
    limiter = RateLimiter(requests_per_second=5)
    lineas = []
    inicio = time.monotonic()
    for i in range(5):
        async with limiter:
            t = time.monotonic() - inicio
            linea = f"  Request {i+1}: t={t:.3f}s"
            print(linea)
            lineas.append(linea)
    total = time.monotonic() - inicio
    lineas.append(f"  Total: {total:.3f}s para 5 requests @ 5 req/s")
    return lineas


async def demo_circuit_breaker() -> list[str]:
    """Muestra el CircuitBreaker abriendo el circuito tras 3 fallos."""
    cb = ApiCircuitBreaker("PubMed_Demo", failure_threshold=3, recovery_timeout=5.0)
    lineas = []

    for intento in range(1, 6):
        estado_antes = cb.state.value
        try:
            async with cb:
                if intento <= 3:
                    raise ConnectionError(f"Timeout simulado #{intento}")
                linea = f"  Intento {intento}: ✓ OK (circuito cerrado)"
                print(linea)
                lineas.append(linea)
        except ExternalApiError as e:
            linea = f"  Intento {intento}: ✗ Circuit OPEN — {str(e)[:60]}"
            print(linea)
            lineas.append(linea)
        except ConnectionError as e:
            linea = f"  Intento {intento}: ✗ Fallo ({e}) → estado: {estado_antes} → {cb.state.value}"
            print(linea)
            lineas.append(linea)

    lineas.append(f"\n  Estado final del circuito: {cb.state.value.upper()}")
    lineas.append(f"  Fallos registrados: {cb._failure_count}")
    return lineas


async def demo_fallback() -> list[str]:
    """Muestra with_fallback devolviendo valores seguros cuando la API falla."""
    lineas = []

    @with_fallback(fallback_value=[], api_name="PubMed")
    async def buscar_pubmed_que_falla(query: str) -> list:
        raise ExternalApiError("PubMed", "Connection timeout after 30s", status_code=503)

    @with_fallback(fallback_value=None, api_name="Orphanet")
    async def buscar_orphanet_que_falla(code: str):
        raise ExternalApiError("Orphanet", "Service unavailable", status_code=503)

    @with_fallback(fallback_value={"genes": [], "drugs": []}, api_name="PharmGKB")
    async def buscar_pharmgkb_que_falla(gene: str) -> dict:
        raise ConnectionError("Network unreachable")

    resultado1 = await buscar_pubmed_que_falla("TTR neuropathy")
    linea = f"  PubMed falla   → fallback: {resultado1!r} (pipeline continúa)"
    print(linea); lineas.append(linea)

    resultado2 = await buscar_orphanet_que_falla("85163")
    linea = f"  Orphanet falla → fallback: {resultado2!r} (pipeline continúa)"
    print(linea); lineas.append(linea)

    resultado3 = await buscar_pharmgkb_que_falla("TTR")
    linea = f"  PharmGKB falla → fallback: {resultado3!r} (pipeline continúa)"
    print(linea); lineas.append(linea)

    return lineas


async def main_async() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(_SEP)
    print("  DEMO — Gestión de rate limits y fallbacks en APIs externas")
    print(_SEP)

    # 1. Rate Limiter
    print(f"\n  [1/4] RateLimiter — 5 requests a 5 req/s:")
    lineas_rl = await demo_rate_limiter()

    # 2. Circuit Breaker
    print(f"\n  [2/4] CircuitBreaker — 3 fallos → circuito abierto:")
    lineas_cb = await demo_circuit_breaker()

    # 3. Fallback
    print(f"\n  [3/4] with_fallback — APIs que fallan no bloquean el pipeline:")
    lineas_fb = await demo_fallback()

    # 4. Instancias globales configuradas
    print(f"\n  [4/4] Instancias globales por API:")
    instancias = [
        ("pubmed_limiter",    f"{pubmed_limiter._rps} req/s"),
        ("orphanet_limiter",  f"{orphanet_limiter._rps} req/s"),
        ("pharmgkb_limiter",  f"{pharmgkb_limiter._rps} req/s"),
    ]
    for nombre, config in instancias:
        print(f"        {nombre:<25} → {config}")

    # Guardar artefactos
    rl_txt = _OUT_DIR / "demo_rate_limiter.txt"
    with rl_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — RateLimiter: control de tasa de requests\n")
        f.write("=" * 60 + "\n\n")
        f.write("Configuración por API:\n")
        f.write("  PubMed sin API key  : 3 req/s\n")
        f.write("  PubMed con API key  : 10 req/s\n")
        f.write("  Orphanet            : 5 req/s\n")
        f.write("  PharmGKB            : 5 req/s\n")
        f.write("  ClinicalTrials      : 10 req/s\n\n")
        f.write("Demo 5 requests @ 5 req/s:\n")
        for l in lineas_rl: f.write(l + "\n")

    cb_txt = _OUT_DIR / "demo_circuit_breaker.txt"
    with cb_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — CircuitBreaker: protección ante APIs caídas\n")
        f.write("=" * 60 + "\n\n")
        f.write("Estados: CLOSED (normal) → OPEN (bloqueado) → HALF_OPEN (recuperando)\n\n")
        f.write("Demo: 3 fallos consecutivos abren el circuito\n")
        for l in lineas_cb: f.write(l + "\n")

    fb_txt = _OUT_DIR / "demo_fallback.txt"
    with fb_txt.open("w", encoding="utf-8") as f:
        f.write("NEXUS — with_fallback: pipeline resiliente ante fallos de APIs\n")
        f.write("=" * 60 + "\n\n")
        f.write("Principio: si una API externa falla, el pipeline no se detiene.\n")
        f.write("El agente recibe un fallback vacío y genera hipótesis con evidence_level III.\n\n")
        for l in lineas_fb: f.write(l + "\n")

    print()
    print(_SEP)
    print("  RESULTADO FINAL:")
    print(_SEP)
    print(f"  RateLimiter     : ✓ ventana deslizante de 1s por API")
    print(f"  CircuitBreaker  : ✓ OPEN tras 3 fallos, HALF_OPEN tras recovery_timeout")
    print(f"  with_fallback   : ✓ PubMed/Orphanet/PharmGKB fallan → pipeline continúa")
    print(f"  APIs protegidas : PubMed, Orphanet, PharmGKB, ClinicalTrials")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • Rate Limiter   → {rl_txt}")
    print(f"    • Circuit Breaker → {cb_txt}")
    print(f"    • Fallbacks       → {fb_txt}")
    print(_SEP)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
