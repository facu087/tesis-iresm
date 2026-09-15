## Why

El `evidence_level` (I, II, III) de cada hipótesis hoy lo **autodeclara el LLM** del agente
que la generó, y el reporte ordena por ese valor sin contrastarlo con nada. La verificación
bibliográfica ya existente (`backend/pipeline/verification.py`) mostró que 9 de cada 10
referencias citadas por los agentes eran discordantes, así que el nivel declarado no es
confiable: una hipótesis puede salir "Evidencia I" y a la vez "especulativa". Además, la
regla del proyecto —"hipótesis sin referencia verificable → `evidence_level: III`, no se
descarta"— está escrita en `CLAUDE.md` y en `openspec/config.yaml` pero **no está
implementada**. Es la tarjeta #54 del Sprint 4 y el Agente 04 (Árbitro Verificador, #52)
necesita estas reglas definidas para consumirlas.

## What Changes

- Nuevo módulo determinista `backend/pipeline/evidence.py` (sin LLM, sin red) con las reglas
  de clasificación EBM:
  - **Tope por evidencia verificada**: el nivel efectivo de una hipótesis es el nivel
    declarado por el agente, limitado por el mejor nivel que permiten sus fuentes
    **verificadas** contra PubMed, según el tipo de publicación que indexa PubMed
    (Meta-Analysis / Systematic Review / RCT → tope I; estudios observacionales, ensayos no
    aleatorizados, guías y artículos sin diseño identificable → tope II; reportes de caso,
    revisiones narrativas, cartas, editoriales, publicaciones retractadas → tope III). El
    tope **nunca sube** el nivel declarado.
  - **Sin fuente verificada → nivel III** (implementa la regla vigente del proyecto).
  - **Estado de la hipótesis** derivado de los veredictos de verificación: `respaldada`,
    `pendiente` (nuevo: la verificación no pudo ejecutarse, p. ej. PubMed caído) o
    `especulativa`. No existe el estado "descartada": ninguna hipótesis se elimina.
  - **Orden del reporte**: estado (respaldada → pendiente → especulativa), luego nivel
    efectivo (I → II → III), luego prioridad (HIGH → LOW), luego cantidad de fuentes
    verificadas; desempate estable por orden original.
  - Interfaz pública (`classify_hypothesis`, `prioritize`) pensada para que la llame el
    Agente 04 en la Ronda 5 y el Agente 06 al reemplazar `report_builder.py`.
- `PubMedClient._esummary()` / `fetch_metadata()` devuelven además los tipos de publicación
  (`pubtypes`) que PubMed ya incluye en la misma respuesta: **sin llamadas de red extra**.
- `SourceVerification` conserva los tipos de publicación del artículo verificado.
- `report_builder._rank_hypotheses()` delega la clasificación y el orden en `evidence.py`.
  **Cambio de comportamiento**: `evidence_level` del reporte pasa a ser el nivel
  **efectivo** (topeado), y el orden pone el nivel de evidencia por delante de la prioridad.
- `StructuredReport` crece **solo de forma aditiva**:
  - `RankedHypothesis.declared_evidence_level` (lo que declaró el agente) y
    `RankedHypothesis.evidence_note` (explicación en español de por qué quedó ese nivel).
  - `RankedHypothesis.status` admite el valor nuevo `"pendiente"`.
  - `Source.publication_types` (solo para fuentes verificadas).
  - `VerificationSummary.hipotesis_pendientes` y `VerificationSummary.hipotesis_topeadas`.
- La clasificación ignora cualquier campo de verificación que el LLM haya escrito en sus
  fuentes: solo cuentan los veredictos de `verification.py`.
- Vista de reporte (frontend) y PDF: agrupan las hipótesis en "respaldadas", "pendientes de
  verificación" y "especulativas", y muestran el nivel declarado cuando fue topeado.
- Script de evidencia `scripts/demo_priorizacion_evidencia.py` y tests en `tests/`.

## Capabilities

### New Capabilities
- `clasificacion-evidencia-ebm`: reglas deterministas para asignar el nivel de evidencia EBM
  efectivo de cada hipótesis a partir de sus fuentes verificadas, derivar su estado
  (respaldada / pendiente / especulativa), ordenarlas en el reporte y exponer el resultado
  de forma aditiva en el contrato de exportación.

### Modified Capabilities
<!-- openspec/specs/ está vacío: no hay capacidades previas que modificar. -->

## Impact

- **Código backend**: `backend/pipeline/evidence.py` (nuevo), `backend/pipeline/verification.py`,
  `backend/pipeline/report_builder.py`, `backend/external/pubmed.py`,
  `backend/api/schemas.py`, `backend/models/hypothesis.py`, `backend/pipeline/pdf_exporter.py`.
- **Frontend**: `frontend/src/lib/types.ts`, `frontend/src/app/report/page.tsx`.
- **Contrato JSON** (`POST /api/analyze`, `POST /api/report/pdf`): solo campos nuevos con
  default y un valor nuevo en `status`. Cambia el **valor** de `evidence_level` (ahora
  efectivo) y el **orden** de `hypotheses`.
- **Sin cambios** en `api/router.py`, `pipeline/orchestrator.py`, `pipeline/debate.py` ni en
  los agentes: la verificación ya llega a `build_export()`.
- **Tests**: nuevo `tests/test_evidence.py`; se ajustan `tests/test_report_builder.py`
  (el test de orden por evidencia hoy depende del nivel autodeclarado),
  `tests/test_verification.py` (el caso sin verificaciones pasa a `pendiente`),
  `tests/test_pubmed.py` y `tests/test_pdf_exporter.py`.
- **Documentación**: `.claude/architecture.md` (cierra § "Pendiente — depende del Agente 04"),
  `.claude/CLAUDE.md`, `.claude/backlog.md`.
- **Dependencias**: ninguna nueva.
