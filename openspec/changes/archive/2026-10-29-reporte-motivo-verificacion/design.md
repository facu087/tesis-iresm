## Context

En un análisis, PubMed se consulta en dos lugares:

1. `router.py` llama a `verify_report_sources()` sobre las fuentes del debate.
2. `agent_04_arbiter.py` llama a `verify_sources()` sobre las fuentes nuevas de la Ronda 5. Esta segunda consulta solo ocurre si hubo recitación.

Las dos terminan en `verify_sources()`. Esa función hace una sola consulta batch (`PubMedClient.fetch_metadata`, con 3 intentos vía `tenacity` y `reraise=True`, así que llega la excepción original). Si la consulta falla, la función atrapa la excepción, la imprime por stderr y marca todas las fuentes con PMID como `NO_VERIFICABLE`. Devuelve un `dict[str, SourceVerification]`, y el Árbitro actualiza ese dict en el lugar con los veredictos de la Ronda 5.

`report_builder._build_verification_summary()` cuenta los veredictos para armar el `VerificationSummary`. Hoy ese conteo es la única huella del fallo que llega al reporte.

Para la motivación, ver proposal.md (sección Why). Los requisitos están en `specs/estado-verificacion-bibliografica/spec.md`.

## Goals / Non-Goals

**Goals:**
- Que el resultado de cada consulta (respondió, o falló por una causa) llegue del lugar donde se atrapa la excepción hasta el reporte, sin cambiar la firma de `verify_sources()` ni la de `arbitrate()`.
- Una sola tabla de clasificación de la causa, probada con un test por categoría.

**Non-Goals:**
- Cambiar la política de reintentos de `PubMedClient`.
- Reintentar la verificación cuando falla.
- Mostrar la causa en el resumen ejecutivo del Agente 06.
- Distinguir un fallo por PMID: la consulta es batch, así que responde o falla entera.

## Decisions

### D1. El resultado de cada consulta se registra en un `contextvar` por análisis

`verification.py` expone un administrador de contexto, `registro_de_consultas()`. El router lo abre alrededor del pipeline, igual que abre el registro de telemetría. Cada vez que `verify_sources()` consulta PubMed, anota un `ResultadoConsulta(ok: bool, causa: CausaFallo | None)` en el registro activo. Si no hay ningún registro abierto (scripts o tests que llaman a la función suelta), anotar no hace nada.

**Por qué:** el resultado de la Ronda 5 se produce dentro del Árbitro, que hoy no devuelve nada sobre la consulta. Con un `contextvar`, lo que anota el Árbitro llega al router sin agregarle un campo a `ArbitrationResult` ni cambiar firmas. Es el mismo patrón que `backend/telemetry/usage.py`, que ya resolvió el aislamiento entre análisis concurrentes.

**Alternativas descartadas:**
- *Que `verify_sources()` devuelva un objeto `(veredictos, resultado)`.* Rompe a los llamadores y a los tests existentes, y obliga a que `arbitrate()` devuelva el resultado de su consulta, lo que agrega un campo a `ArbitrationResult` que no es del arbitraje.
- *Una subclase de `dict` con un atributo de estado.* Se pierde en el `update()` que hace el Árbitro y es frágil.

### D2. La causa se clasifica por el tipo de excepción, en una sola función

`clasificar_fallo(exc) -> CausaFallo` vive en `verification.py`:

| Excepción | Causa |
|---|---|
| `httpx.HTTPStatusError` con 429 | `limite_velocidad` |
| `httpx.HTTPStatusError` con 400, 401 o 403 | `configuracion` |
| `httpx.HTTPStatusError` con 5xx | `error_api` |
| `httpx.HTTPStatusError` con otro código | `error_api` |
| `httpx.TransportError` (timeout, conexión, red) | `red` |
| `ValueError` (incluye el `JSONDecodeError` de una respuesta ilegible) | `error_api` |
| cualquier otra | `desconocida` |

`CausaFallo` es un `str, Enum`, como `SourceStatus`. El mensaje por stderr sigue igual (con el texto de la excepción, que no tiene datos clínicos) y suma la categoría. Lo que se anota en el registro es solo la categoría.

**Por qué no por el texto del mensaje:** los mensajes de httpx cambian entre versiones y además contienen la URL con `api_key`.

### D3. El estado global se calcula al final, a partir de la lista de resultados

`estado_verificacion(resultados) -> tuple[EstadoVerificacion, CausaFallo | None]`:

- Sin resultados → `sin_consulta`.
- Todos ok → `completa`.
- Todos fallidos → `no_disponible`.
- Mezcla → `parcial`.
- Causa: la del primer resultado fallido, en orden de consulta (la verificación inicial va antes que la Ronda 5). Es la que afecta a más fuentes.

Es una función pura: se prueba sin red ni pipeline.

### D4. El contrato crece con dos campos opcionales en `VerificationSummary`

`estado: Literal["completa", "parcial", "no_disponible", "sin_consulta"] | None = None` y `causa: Literal[...] | None = None`. `build_export()` recibe un parámetro opcional con el par `(estado, causa)` y lo copia al resumen. Si no se le pasa, los dos quedan en `None`, que es lo que ve un reporte anterior al cambio. En el frontend, `types.ts` suma los dos campos como opcionales.

### D5. Un solo texto por causa en cada lado del contrato

El backend (PDF) y el frontend (`/report`) tienen cada uno un mapa `causa → frase en lenguaje llano`. No se comparte el texto por el contrato: el JSON lleva la categoría, y cada presentación la traduce. Las frases:

| Causa | Frase |
|---|---|
| `red` | PubMed no respondió (sin conexión o tiempo de espera agotado). |
| `limite_velocidad` | PubMed rechazó la consulta por exceso de pedidos. |
| `configuracion` | PubMed rechazó la consulta: posible clave de PubMed mal configurada en el servidor. |
| `error_api` | PubMed devolvió un error. |
| `desconocida` | Ocurrió un error no identificado al consultar PubMed. |

Hay un test en cada lado que recorre todas las categorías, para que una categoría nueva sin frase falle en CI.

### D6. Presentación

- **`/report`:** `VerificationBanner` pasa a tono de advertencia, con un ícono de advertencia, cuando `estado` es `parcial` o `no_disponible`. Dice "La verificación bibliográfica no se pudo hacer" o "quedó incompleta", la cantidad de `no_verificables` y la frase de la causa. Desaparece el "(fallo de red)" fijo. Sin `estado` (reporte anterior), se comporta como hoy, salvo que el texto de las no verificables ya no afirma una causa. El banner se muestra justo después del aviso de mock, en el orden actual de `report/page.tsx`.
- **PDF:** un párrafo en la portada, después del aviso de modo mock y con el mismo estilo de advertencia, solo cuando `estado` es `parcial` o `no_disponible`.

## Risks / Trade-offs

- [Un llamador nuevo de `verify_sources()` fuera del router no abre el registro, y su resultado no llega a ningún reporte.] → Es el comportamiento buscado para scripts y tests. El docstring de `registro_de_consultas()` lo dice, y un test del router verifica que el registro está abierto durante el pipeline.
- [Las tareas de `asyncio.gather` copian el contexto y no lo comparten.] → El registro guarda una lista mutable. Las tareas copian la referencia, así que todas anotan en la misma lista. Es el mismo mecanismo que usa la telemetría, y lo cubre un test con dos análisis concurrentes.
- [Con dos fallos de causas distintas se informa una sola causa.] → Es una decisión explícita de la spec. La segunda causa sigue en stderr.
- [Las frases del PDF y de `/report` pueden divergir.] → Los tests que recorren todas las categorías garantizan que estén todas, no que digan lo mismo. Es aceptable porque son dos presentaciones con espacio distinto.

## Migration Plan

Es un cambio aditivo, sin migración: los campos nuevos son opcionales y un reporte guardado en el navegador antes del cambio se sigue mostrando. Para revertir, alcanza con revertir el commit.
