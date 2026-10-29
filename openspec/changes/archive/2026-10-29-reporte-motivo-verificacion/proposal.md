## Why

Cuando la verificación bibliográfica no puede consultar PubMed, `verify_sources()` marca las fuentes como `no_verificable` y el motivo queda solo en stderr (`backend/pipeline/verification.py:182-189`). Ni `/report` ni el PDF dicen por qué. Peor: si PubMed no responde para ninguna fuente, el aviso de verificación de `/report` sale en verde y con el ícono de confirmado (`ReportNotices.tsx:131`, porque no hay discordantes) y dice "fallo de red" aunque la causa sea otra. El médico ve hipótesis en `pendiente` sin saber que la verificación no corrió. Es el mismo síntoma silencioso de la tarjeta #79, ahora del lado del reporte (tarjeta #91).

## What Changes

- La verificación bibliográfica pasa a devolver, además de los veredictos por fuente, un **estado global** (`completa`, `parcial`, `no_disponible`, `sin_consulta`) y, cuando hubo un fallo, una **causa en categorías** (`red`, `limite_velocidad`, `configuracion`, `error_api`, `desconocida`). Nunca el texto crudo de la excepción.
- El estado combina las dos consultas a PubMed del pipeline: la verificación inicial (`router.py`) y la re-verificación de la Ronda 5 (`agent_04_arbiter.py`). Si una responde y la otra no, el estado es `parcial`.
- `VerificationSummary` suma dos campos opcionales: `estado` y `causa`. El cambio es aditivo: un reporte anterior sin esos campos se sigue leyendo y se muestra como antes.
- `/report` muestra el estado y la causa con la misma visibilidad que el aviso de modo mock. El aviso de verificación ya no sale en verde ni con el ícono de confirmado cuando la verificación no corrió, y deja de afirmar "fallo de red" cuando la causa es otra.
- El PDF muestra el mismo aviso en la portada, junto al aviso de modo mock.
- Tests en `tests/` (clasificación de la causa, combinación del estado, resumen, PDF) y en Vitest (aviso de `/report`), más un `scripts/demo_*.py` como evidencia para Trello.

## Capabilities

### New Capabilities
- `estado-verificacion-bibliografica`: estado global y causa de un fallo de la verificación bibliográfica contra PubMed, cómo se calculan a partir de las consultas del pipeline y cómo se muestran en `/report` y en el PDF.

### Modified Capabilities
<!-- Ninguna: ningún requirement vigente describe la presentación de las fuentes no verificables. -->

## Impact

- **Backend:** `backend/pipeline/verification.py` (clasificación de la causa y estado), `backend/agents/agent_04_arbiter.py` (la re-verificación de la Ronda 5 informa su resultado), `backend/api/router.py` (combina los estados), `backend/pipeline/report_builder.py` (`_build_verification_summary`), `backend/api/schemas.py` (`VerificationSummary`), `backend/pipeline/pdf_exporter.py` (aviso en portada).
- **Frontend:** `frontend/src/lib/types.ts` (`VerificationSummary`), `frontend/src/components/report/ReportNotices.tsx` (`VerificationBanner`) y su test.
- **Contrato:** `POST /api/analyze` y `POST /api/report/pdf` reciben y devuelven dos campos opcionales nuevos; ningún campo existente cambia.
- **Sin dependencias nuevas** y sin costo de red adicional: no se agregan consultas a PubMed.
- **Privacidad:** la causa es una categoría fija; ningún texto de excepción, URL ni parámetro (por ejemplo `api_key`) llega al reporte.
