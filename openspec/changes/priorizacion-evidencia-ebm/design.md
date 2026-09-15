## Context

Motivación en `proposal.md` (§ Why). Requisitos en `specs/clasificacion-evidencia-ebm/spec.md`.

Estado actual relevante, relevado antes de proponer para no duplicar:

- **Lo que ya existe** (`backend/pipeline/verification.py`, tarjeta 16 del backlog): una sola
  consulta batch a `esummary` trae los metadatos de todos los PMIDs citados; cada fuente recibe
  un `SourceVerification` con `SourceStatus` (`verificada`, `discordante`, `inexistente`,
  `sin_pmid`, `no_verificable`). Ante un fallo de red todo queda `no_verificable` y nada se
  descarta.
- **Lo que ya existe** (`report_builder._rank_hypotheses`): `RankedHypothesis.status` con dos
  valores, `respaldada` (≥1 fuente verificada) y `especulativa`; `verified_sources`;
  `VerificationSummary` con conteos. El frontend (`report/page.tsx`) y el PDF ya pintan ese
  estado.
- **Lo que falta** y cubre este cambio: (1) el `evidence_level` se copia tal cual lo declaró el
  LLM; (2) la regla "sin referencia verificable → III" no se aplica: hoy puede salir
  "Evidencia I · Especulativa"; (3) no se distingue "PubMed no respondió" de "la cita es falsa";
  (4) el orden es prioridad → nivel, ambos autodeclarados; (5) `architecture.md` sigue listando
  `Hypothesis.estado` y la separación verificadas/especulativas como pendientes.
- **Hueco detectado**: `BaseAgent.parse_hypotheses()` construye `Source(**s)` con lo que mande
  el LLM, así que un agente puede emitir `verified: true`. `_annotate_source()` devuelve la
  fuente intacta si no hay veredicto, y el conteo usa `s.verified`: ese valor autodeclarado
  puede terminar marcando una hipótesis como `respaldada`.
- **Dato de PubMed medido** (esummary real, query "metformin vitamin B12 neuropathy", 15
  artículos): `pubtype` viene en la misma respuesta que ya se pide, pero la mayoría de los
  estudios observacionales llega solo como `["Journal Article"]`. Cohorte, caso-control y
  transversal son **términos MeSH**, no tipos de publicación; los diseños de nivel I
  (`Meta-Analysis`, `Randomized Controlled Trial`, `Systematic Review`) sí son tipos de
  publicación, y son la base de los filtros *Clinical Queries* de PubMed.

## Goals / Non-Goals

**Goals:**
- Reglas puras y deterministas (sin LLM, sin red) en un único módulo, testeables con dobles.
- Una interfaz que el Agente 04 (Ronda 5) y el Agente 06 (reemplazo de `report_builder`) puedan
  llamar sin reimplementar nada.
- Cero consultas extra a PubMed.
- Contrato `StructuredReport` estrictamente aditivo.

**Non-Goals:**
- Evaluar si el artículo verificado **respalda el contenido** de la hipótesis (pertinencia).
  Eso es razonamiento del Árbitro (#52); acá solo se acota el nivel.
- Cambiar prompts de los agentes, `debate.py`, `orchestrator.py` o `api/router.py`.
- Recalcular `Report.sources_summary` de `debate.py` (cuenta por nivel declarado, no se exporta).
- Clasificar con MeSH, abstracts o títulos.
- Sanear las fuentes en `BaseAgent.parse_hypotheses()` (lo tocan #51 y #52; ver Open Questions).

## Decisions

### D1. El nivel efectivo es un **tope** sobre el declarado, no una derivación
`nivel_efectivo = peor(nivel_declarado, mejor tope entre fuentes verificadas)`; sin fuentes
verificadas, III.

- *Alternativa descartada — mantener el autodeclarado*: es justamente lo que invalidó la
  verificación (9/10 citas discordantes). No cumple la tarjeta ("lógica de clasificación").
- *Alternativa descartada — derivar el nivel solo de los tipos de publicación*: subiría
  hipótesis que el propio agente marcó III por citar, por ejemplo, un meta-análisis tangencial.
  La verificación actual confirma que el PMID corresponde al título citado, **no** que el
  artículo sostenga la hipótesis; subir de nivel con esa evidencia sería sobre-afirmar.
- *Alternativa descartada — que un LLM clasifique el nivel*: no determinista, no testeable sin
  red, y repite el problema de origen (el nivel lo decide un modelo).

### D2. Fuente del tope: tipos de publicación de `esummary`
`PubMedClient._esummary()` agrega `pubtypes: doc.get("pubtype", [])` a cada entrada;
`SourceVerification` gana `publication_types: list[str]`, que `_verify_one()` copia de los
metadatos. La consulta batch no cambia.

- *Alternativa descartada — MeSH vía `efetch` XML* (`Cohort Studies`, `Case-Control Studies`):
  distinguiría cohortes de opinión, pero suma una consulta por reporte, un parseo XML más
  pesado y depende de que el artículo ya tenga indexación MeSH (los recientes no la tienen).
  Queda como refinamiento futuro, con la misma interfaz.
- *Alternativa descartada — palabras clave en el título real* ("randomized", "meta-analysis"):
  barato y determinista, pero frágil ("a meta-analysis is needed…") y difícil de defender en
  la tesis frente a un criterio que indexa la NLM.

### D3. Artículo sin tipo reconocible → tope **II** (no III)
Asimetría deliberada: la ausencia de un tipo de nivel I **es informativa** (la NLM indexa esos
diseños de forma sistemática), pero la ausencia de `Observational Study` **no lo es** (cohorte
y caso-control viven en MeSH). Con tope III, toda cohorte real quedaría igualada a opinión de
experto.

- *Alternativa descartada — tope III*: más conservador, pero degrada sistemáticamente la
  evidencia observacional, que es la mayoría de lo citable en el caso base.

### D4. Guías (`Practice Guideline`, `Guideline`) → tope **II** — *a confirmar en la revisión*
El prompt del Agente 03 grada las guías (A → I, B/C → II), pero PubMed no informa el grado de
recomendación. Tope II no impide que una guía respalde la hipótesis; solo evita que el grado A
autodeclarado pase sin control.

- *Alternativa — tope I*: respetaría la gradación del Agente 03 (el tope nunca sube lo
  declarado), a costa de aceptar el grado que declara el LLM. Si el usuario la prefiere, cambia
  una línea de la tabla y un escenario de la spec.

### D5. `Review` (narrativa) → tope III; retractada → III con prioridad sobre todo
Revisión narrativa = opinión de experto en la jerarquía EBM. Una publicación retractada no
puede sostener nivel I aunque además sea un RCT. Ver riesgo sobre revisiones sistemáticas
anteriores a 2019.

### D6. El estado es **derivado**, no un campo persistido en `Hypothesis`
`architecture.md` pedía `Hypothesis.estado`. Se resuelve con una función pura que recibe la
hipótesis y los veredictos y devuelve la evaluación; el estado viaja en `RankedHypothesis`
(el snapshot exportado), no en el modelo interno.

- *Alternativa descartada — agregar `status` a `Hypothesis`*: dos fuentes de verdad (el campo
  y los veredictos) y estado desactualizado cuando el Árbitro re-verifique o fusione
  hipótesis en la Ronda 5. Además `Hypothesis` es lo que parsea la salida del LLM.

### D7. Tres estados: `respaldada`, **`pendiente`**, `especulativa`; sin "descartada"
`pendiente` = ninguna fuente verificada y alguna fuente con PMID sin veredicto concluyente
(`no_verificable` o sin veredicto). Coincide con el "pendiente" del diseño original.
"descartada" se elimina del diseño: contradice la regla vigente (III, no se descarta).

- *Alternativa descartada — mantener el binario actual*: con PubMed caído el reporte presenta
  todas las hipótesis como si sus citas hubieran fallado, mientras el banner dice "no se
  invalidan". `pendiente` resuelve esa contradicción.
- Efecto colateral aceptado: `build_export()` sin veredictos (tests, demos) da `pendiente` en
  vez de `especulativa`. Se ajusta `test_sin_verificaciones_todo_queda_especulativo`.

### D8. Separación verificadas / especulativas = **lista única ordenada** + agrupación al presentar
El orden pone el estado como primer criterio, así que cada grupo queda contiguo y el `rank`
sigue siendo consecutivo. El frontend y el PDF agrupan por `status`.

- *Alternativa descartada — dos listas en `StructuredReport`*: rompe o duplica `hypotheses`
  (no aditivo) y vuelve ambiguo el `rank`.

### D9. `evidence_level` pasa a ser el **efectivo**; se agrega `declared_evidence_level`
- *Alternativa descartada — conservar `evidence_level` declarado y sumar
  `effective_evidence_level`*: todo consumidor que no se actualice seguiría mostrando el nivel
  del LLM. Con esta decisión los consumidores viejos muestran, sin tocarlos, el valor
  conservador. El tipo del campo no cambia.

### D10. Orden: estado → nivel efectivo → prioridad → fuentes verificadas → orden original — *a confirmar*
El nivel efectivo quedó anclado en evidencia externa; la prioridad sigue siendo opinión del
LLM. Lo anclado pesa más. Dado que toda hipótesis no respaldada tiene nivel III, "estado
primero" y "nivel primero" solo difieren en empates, y "estado primero" garantiza grupos
contiguos.

- *Alternativa — mantener prioridad primero* (orden actual): preserva la regla clínica del
  Agente 03 de "descartar primero lo tratable", pero contradice el título de la tarjeta
  ("priorización por nivel de evidencia"). Si el usuario la prefiere, cambia la clave de orden
  y dos escenarios de la spec.

### D11. Solo cuentan los veredictos de `verification.py`
La clasificación lee el dict de veredictos, nunca `Source.verified` ni
`Source.publication_types`. `_annotate_source()` limpia `verified`, `verification_status`,
`actual_title` y `publication_types` cuando la fuente no tiene veredicto, y solo completa
`publication_types` cuando el veredicto es `verificada` (los tipos de un PMID discordante son
de otro artículo).

### D12. Interfaz pública de `backend/pipeline/evidence.py`
```python
class HypothesisStatus(str, Enum):
    RESPALDADA = "respaldada"; PENDIENTE = "pendiente"; ESPECULATIVA = "especulativa"

class EvidenceAssessment(BaseModel):          # Pydantic, regla del proyecto
    declared_level: EvidenceLevel
    ceiling: EvidenceLevel                    # mejor tope entre fuentes verificadas (III si no hay)
    effective_level: EvidenceLevel
    status: HypothesisStatus
    verified_sources: int
    best_source_pmid: str | None
    best_source_types: list[str]
    note: str                                 # explicación en español
    @property
    def capped(self) -> bool: ...             # effective_level peor que declared_level

def source_ceiling(publication_types: Iterable[str]) -> EvidenceLevel: ...
def classify_hypothesis(
    hypothesis: Hypothesis, verifications: Mapping[str, SourceVerification]
) -> EvidenceAssessment: ...
def prioritize(
    hypotheses: Sequence[Hypothesis], verifications: Mapping[str, SourceVerification]
) -> list[tuple[Hypothesis, EvidenceAssessment]]: ...
```
- Las tablas de tipos son constantes `frozenset` en `UPPER_SNAKE_CASE`, comparadas en
  minúsculas y sin espacios circundantes.
- Uso previsto por el **Agente 04 (#52)**: tras la síntesis de la Ronda 5, llamar
  `verify_report_sources()` y luego `classify_hypothesis()` por hipótesis para su criterio de
  parada ("toda hipótesis del consenso respaldada") o `prioritize()` para el orden. No
  necesita tocar este módulo.
- Uso previsto por el **Agente 06 (#62)**: reemplazar `report_builder` llamando `prioritize()`
  y copiando la evaluación a `RankedHypothesis`.
- `report_builder._rank_hypotheses()` queda como adaptador fino: arma `supporting_agents`
  (sin cambios), llama `prioritize()` y mapea a `RankedHypothesis`.

## Risks / Trade-offs

- [Artículos recientes todavía sin tipos de publicación indexados llegan como
  `Journal Article`] → un RCT nuevo topea en II, no en III (D3); `evidence_note` explica el
  tope y el nivel declarado queda visible.
- [Revisiones sistemáticas anteriores a 2019 indexadas solo como `Review`, antes de que
  existiera el tipo `Systematic Review`] → topean en III. Se documenta como limitación en la
  tesis; el demo con PMIDs reales tiene que mostrar al menos un caso para medir el impacto. El
  refinamiento por MeSH (D2) lo resolvería sin cambiar la interfaz.
- [La verificación confirma identidad del artículo, no pertinencia] → un meta-análisis
  verificado pero tangencial habilita tope I. Acotado por D1 (nunca sube lo declarado); la
  pertinencia la juzga el Árbitro (#52).
- [Cambio visible: `evidence_level` baja y el orden cambia en reportes nuevos] → contrato
  aditivo, `declared_evidence_level` visible, nota en backlog y en `architecture.md`.
- [El texto de los banners suma `respaldadas + especulativas` como total] → con `pendiente`
  deja de cuadrar; se actualiza el texto del frontend y del PDF en este mismo cambio.
- [Conflictos de merge con cambios paralelos] → `verification.py` (lo usa #52) recibe un diff
  chico y aditivo (un campo en `SourceVerification`, una línea en `_verify_one`);
  `report_builder.py` (lo reemplaza #62) queda más delgado porque la lógica se muda a
  `evidence.py`. No se tocan `router.py` (#53), `orchestrator.py`/`debate.py` (#51) ni
  `base_agent.py`. Conviene mergear este cambio antes que #52 y #62.
- [Frontend en una versión de Next.js con cambios incompatibles (`frontend/AGENTS.md`)] → solo
  se toca render en TSX y tipos; leer la guía local antes de editar.

## Migration Plan

- Sin persistencia ni migración de datos: los reportes se generan por sesión.
- Reportes JSON generados antes del cambio siguen siendo válidos para `POST /api/report/pdf`
  (todos los campos nuevos tienen default).
- Rollback: revertir la rama; ningún otro módulo depende todavía de `evidence.py`.

## Open Questions

- ¿El saneamiento de campos de verificación en `BaseAgent.parse_hypotheses()` (descartar
  `verified`, `verification_status`, `actual_title`, `publication_types` venidos del LLM) lo
  hace #52 o un fix aparte? Este cambio ya se protege en `evidence.py` y `_annotate_source()`,
  así que puede decidirse después.
- Si más adelante se adopta MeSH (D2), ¿`Observational Study` sin MeSH de diseño debería seguir
  topeando en II? No afecta este cambio.
