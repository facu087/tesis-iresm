## Context

Motivación: ver `proposal.md` — Why. Requisitos: `specs/agente-especialista-genomica/spec.md` y
`specs/contexto-genomico/spec.md`.

Estado actual que condiciona el diseño (verificado en el código de `develop`, commit `f26e3d9`):

- **Interfaz de agentes.** `BaseAgent.run(clinical_context: str)` recibe solo texto. El orquestador le pasa
  a todos el mismo contexto (PICO + RAG); el debate instancia los agentes sin argumentos
  (`debate.py:172`) y les pasa solo PICO. Ningún agente ve hoy `BiomarkerProfile`.
- **Qué extrae hoy `biomarker_extractor` del caso base.** Corriendo solo la capa regex sobre el texto del
  caso (`scripts/poc_test.py`): `genes=['CMT']`, `antibodies=['anti-Hu','anti-Yo','anti-Ri']`,
  `variants=[]`, `lab_markers=[]`. `CMT` no es un gen: es Charcot-Marie-Tooth, entra por `_KNOWN_GENES`
  (que también incluye `FAP` y `ATTR`) y en el texto aparece dentro de un estudio **negativo** ("CMT panel
  de 40 genes negativo"). La capa LLM no se midió (requiere Groq); los fixtures de PICO de
  `tests/test_orchestrator.py` y `tests/test_debate.py` usan `genetic_findings=[]`.
- **Cliente PharmGKB.** `backend/external/pharmgkb.py` atrapa todas las excepciones
  (`except (httpx.HTTPError, Exception): pass` / `return []`), así que un error de red es indistinguible de
  "sin anotaciones" y el `@retry` nunca se dispara. No usa `pharmgkb_limiter` ni `pharmgkb_breaker`.
  `scripts/demo_pharmgkb.py` usa **datos simulados**: el cliente nunca se ejercitó contra la API real.
- **Debate.** `_round_2` y `_round_revision` indexan `outputs_by_id[agent.AGENT_ID]` para cada agente de la
  lista fija: si un agente falló en la Ronda 1, la Ronda 2 lanza `KeyError` fuera del `gather` y tira abajo
  `POST /api/analyze`. Con dos agentes estables no se vio; con un tercero aumenta la probabilidad.
- **Atribución.** `report_builder._rank_hypotheses()` reconstruye `supporting_agents` por texto exacto de la
  hipótesis contra los outputs de Ronda 1 y de la última ronda, usando `agent_name`.
- **Groq.** `_call_llm` fija `max_tokens=4096` y reintenta 429 con esperas de 8/20/40 s. El demo del debate
  midió 25 s para 3 rondas × 2 agentes.
- **Fármacos.** `normalizer.py` lleva marcas a INN **en español** (`lyrica → pregabalina`).

## Goals / Non-Goals

**Goals:**
- Que la decisión "¿el caso trae hallazgos genéticos?" sea determinista, testeable sin red y visible en el
  prompt, no una inferencia del LLM.
- Sumar el Agente 02 sin tocar `BaseAgent`, `Hypothesis`, `Report`, `report_builder` ni `api/schemas`, que
  son los archivos que editan en paralelo #52, #54 y #62.
- Que el caso base de la tesis produzca evidencia útil para Trello aunque no tenga variantes.

**Non-Goals:**
- Cliente ClinVar (D6).
- Consultas farmacogenómicas por fármaco (D7).
- Corregir `_KNOWN_GENES` en `biomarker_extractor` (D5).
- Swap real a GPT-4o: queda en `BaseAgent._call_llm()`, fuera de este cambio.
- Clasificación EBM y estado de la hipótesis (#54): el agente no recalcula `evidence_level`.
- Agregar el contexto RAG al debate (hoy el debate usa solo PICO para todos los agentes; es preexistente).

## Decisions

### D1. El perfil genómico se arma fuera del LLM y fuera del agente

`backend/models/genomics.py` define los modelos Pydantic (`GenomicContext`, `GenomicSource`,
`GenomicSourceStatus`, `PharmacogenomicAnnotation`) y el método `to_prompt_block()`.
`backend/pipeline/genomic_context.py` expone `build(case) -> GenomicContext` (determinista, sin red) y
`async enrich(ctx) -> GenomicContext` (PharmGKB, nunca lanza).

```
case.biomarkers ─┐                     ┌─ variants, genetic_findings  (reportado)
case.pico ───────┼─► build() ──────────┼─ genes (saneados), discarded_symbols (mencionado)
                 │                     └─ negative_genetic_studies
                 └─► enrich() ──► annotations + sources[{name, status, detail}]
```

`to_prompt_block()` vive en el modelo para que el agente importe solo `models/` y no `pipeline/` (evita el
ciclo `pipeline → agents → pipeline`).

- *Alternativa descartada — el agente consulta PharmGKB dentro de `run()`.* `run()` corre en
  `asyncio.to_thread`; el cliente es async, así que habría que abrir otro event loop en el thread, y los
  `asyncio.Lock` globales de `rate_limiter.py` quedarían usados desde loops distintos. Además el agente
  volvería a consultar en cada ronda del debate y los tests de agente necesitarían mockear red.
- *Alternativa descartada — que el LLM decida si hay datos genómicos.* Es exactamente la falla que hay que
  evitar: no es reproducible ni verificable.

### D2. El agente recibe el perfil por constructor; `BaseAgent` no cambia

`GenomicsSpecialistAgent(genomic_context: GenomicContext | None = None)`. Sobrescribe `run`, `critique` y
`revise`: agrega `to_prompt_block()` al contexto recibido, delega en la implementación de `BaseAgent` (que
llama a `_call_llm`) y aplica la guarda de D4 al resultado. Con `None` usa un `GenomicContext` vacío, que se
comporta como modo sin hallazgos (fail-safe: la falta de datos nunca habilita a inventar).

Para reutilizar el perfil en el debate sin reconsultar, se agrega `genomic_context: GenomicContext | None =
None` a `ClinicalCase` (`models/case.py`). El orquestador lo completa, igual que el router ya completa
`case.biomarkers`. El debate usa `case.genomic_context` y, si falta (por ejemplo `demo_debate.py`, que
precarga la Ronda 1), cae a `genomic_context.build(case)` sin red.

- *Alternativa descartada — `BaseAgent.run(case: ClinicalCase)`.* Rompe 01 y 03, sus tests y demos, y choca
  con los agentes 04, 05 y 06 que se están planificando en paralelo sobre la misma clase base.
- *Alternativa descartada — guardar el perfil en `Report`.* `models/report.py` es zona de #52 y #62.

### D3. Sin hallazgos genómicos el agente corre igual, en modo orientación

El modo lo fija `GenomicContext.has_genomic_findings` (variantes o hallazgos genéticos positivos). En modo
orientación el bloque del prompt afirma que el caso no reporta variantes, lista los estudios genéticos
negativos y pide razonar sobre patrón de herencia y cobertura de esos estudios. El caso base cae en este
modo con **0 consultas externas y 1 llamada al LLM** en la Ronda 1.

El `SYSTEM_PROMPT` describe criterios generales (herencia, cobertura de paneles, tipos de alteración que un
panel NGS no detecta, farmacogenómica solo si hay anotaciones) y **no nombra enfermedades ni genes
concretos**: si el prompt dijera "pensá en TTR", el demo del caso base mostraría el prompt, no el
razonamiento del agente.

Se piden 1 a 4 hipótesis (01 y 03 piden 3 a 6) para acotar el crecimiento de los prompts del debate.

- *Alternativa descartada — omitir el agente si no hay genes ni variantes.* Ahorra 4 llamadas por análisis,
  pero en el caso base (antecedente paterno, panel CMT negativo, compromiso autonómico) la etiología
  hereditaria fuera del panel es la lectura que más aporta el Agente 02.
- *Alternativa descartada — permitir 0 hipótesis ("sin aporte genómico").* `parse_hypotheses` trata la lista
  vacía como falla y `AgentOutput` no tiene cómo expresar una abstención; agregarlo toca `models/report.py`.
  Queda como mejora posible después de #52/#62.

### D4. Guarda anti-invención: degradar y advertir, no descartar

El JSON del Agente 02 agrega por hipótesis `case_genetic_findings: list[str]`. `parse_hypotheses` lo ignora,
así que el agente lo lee del JSON crudo antes de construir el `AgentOutput`. Dos chequeos deterministas
(detalle en la spec): hallazgo declarado que no está en el perfil, y notación de variante
(`c.`/`p.`/`g.`/`rs`) en `text` en modo orientación. La hipótesis sospechosa queda con `priority=LOW` y el
`rationale` prefijado con `⚠ Hallazgo genético no reportado en el caso: <x>.`

Se degrada `priority` y no `evidence_level` porque el nivel EBM es dominio de #54. El log registra solo la
cantidad de hipótesis marcadas.

- *Alternativa descartada — descartar la hipótesis.* Contradice la regla del proyecto de no descartar, y un
  falso positivo por notación (`Val30Met` vs `p.Val30Met`) borraría una hipótesis válida.
- *Alternativa descartada — confiar solo en el prompt.* No deja nada verificable para el evaluador.
- *Alternativa descartada — un LLM juez.* Una llamada más por ronda y no determinista.
- *Límite conocido:* no detecta afirmaciones en texto libre sin notación ("portador de una mutación en TTR").

### D5. Saneamiento de símbolos en el perfil genómico, no en `biomarker_extractor`

`build()` aplica el formato de símbolo y una lista de siglas que no son genes (`CMT`, `FAP`, `ATTR`, `HMSN`,
`CIDP`, `EMG`, `LCR`, …) y registra los descartes en `discarded_symbols`.

- *Alternativa descartada (para este cambio) — corregir `_KNOWN_GENES` en el extractor.* Los genes
  alimentan también la query del RAG (`orchestrator.py:69`) y la búsqueda de ensayos (`router.py:91`),
  ambas medidas sobre el caso base; cambiar su entrada obliga a remedirlas. Conviene hacerlo en una rama
  `fix/` propia. Costo aceptado: la lista de siglas queda duplicada hasta ese fix.
- *Límite:* el formato exige mayúsculas, así que descarta símbolos HGNC con minúsculas (`C9orf72`).

### D6. ClinVar queda fuera de este cambio

- No hay cliente, y ClinVar responde "¿qué significancia clínica tiene esta variante?": solo aporta cuando el
  caso trae variantes. En el caso base no se llamaría nunca, así que la evidencia para Trello necesitaría un
  caso sintético igual.
- Las otras APIs externas del Sprint 4 (PubMed, Orphanet, PharmGKB) tuvieron cada una su tarjeta y su demo;
  un cliente ClinVar es una unidad de trabajo del mismo tamaño.
- ClinVar va por E-utilities y compartiría el rate limit de PubMed (3 req/s sin key) con la verificación
  bibliográfica, que ya lo usa en el paso 7 del router.
- El PharmGKB existente todavía no se verificó contra la API real: sumar un segundo cliente sin verificar
  duplica el riesgo en la misma tarjeta.

`GenomicContext.sources` es una lista de fuentes con estado: ClinVar se agrega después como otra fuente sin
tocar el agente ni su prompt.

- *Alternativa descartada — cliente ClinVar mínimo (esearch + esummary por variante) en este cambio.* Es
  viable, pero agranda la tarjeta #51 con una integración que el caso de referencia no ejercita.

### D7. PharmGKB se consulta solo por gen

Los símbolos HGNC no dependen del idioma; los fármacos llegan en INN español (`pregabalina`) y PharmGKB
indexa en inglés, así que consultarlos devolvería vacío en silencio. Máximo 3 genes, igual que el RAG.

- *Alternativa descartada — traducir INN español → inglés.* No hay diccionario confiable en el proyecto y
  una heurística de sufijos (`-ina → -in`) falla en casos comunes.

### D8. `pharmgkb.py` deja de tragar errores; el fallback vive en `enrich()`

El cliente propaga `ApiUnavailableError` / `RateLimitError` (de `rate_limiter.py`), envuelve cada request
con `pharmgkb_limiter` y `pharmgkb_breaker`, y devuelve `[]` solo cuando la API respondió sin datos.
`enrich()` hace el `try/except` explícito y traduce a `no_disponible` / `sin_resultados` / `consultada`.
Antes de cerrar la tarjeta se verifican contra la API real las rutas (`/v1/gene`, `/v1/clinicalAnnotation`)
y la forma de la respuesta que asume el cliente.

- *Alternativa descartada — usar el cliente tal cual.* Una caída de PharmGKB llegaría al agente como "sin
  anotaciones" y nadie lo notaría; además viola la regla "nunca `except: pass`".

### D9. Integración en Ronda 1 y debate

- Orquestador: `asyncio.gather(_enrich_context_with_rag(...), _build_genomic_context(case))`, así el paso
  genómico no agrega latencia secuencial. Agentes: `[01, 02(ctx), 03]`.
- Debate: se filtran los agentes a los que tienen output de Ronda 1 (corrige el `KeyError`). El Agente 02
  se instancia con `case.genomic_context`.
- Costo: llamadas por análisis 10 → 14; por ronda 2 → 3 (cada agente critica a los otros dos en una sola
  llamada, así que las llamadas crecen lineal y no por pares). Los pares dirigidos de crítica pasan de 2 a
  6 y cada prompt de revisión recibe críticas de dos agentes.

- *Alternativa descartada — que el Agente 02 solo critique y no revise.* Sus hipótesis llegarían al reporte
  sin pasar por las Rondas 3–4, rompiendo el protocolo del debate.
- *Alternativa descartada (queda como palanca) — `GROQ_FAST` para el Agente 02.* En Groq cada modelo tiene su
  propio cupo, así que evitaría competir con 01 y 03, pero baja la calidad justo en el razonamiento genómico.
  Se usa si la medición de la tarea 6.3 muestra 429 inmanejables.

### D10. Atribución sin tocar `report_builder`

Con `AGENT_NAME = "Especialista Genómica"`, `_rank_hypotheses()` ya atribuye bien. El test va en un archivo
nuevo y no en `tests/test_report_builder.py`, que #54 va a modificar.

## Risks / Trade-offs

- [Más 429 en Groq con 3 llamadas simultáneas por ronda; cada backoff suma 8–40 s] → 1–4 hipótesis en el
  Agente 02; medición end-to-end del caso base (llamadas, tiempo, reintentos) registrada en el backlog;
  palanca `GROQ_FAST` (D9).
- [Las rutas o la forma de respuesta de la API de PharmGKB no coinciden con el cliente: nunca se probó
  contra la API real] → tarea de verificación con una llamada real por `TTR` antes de cerrar; si falla,
  corregir el cliente en el mismo cambio. Mientras tanto el estado `no_disponible` lo hace visible.
- [La guarda de D4 no ve afirmaciones sin notación] → límite documentado en la spec y en el demo; la
  hipótesis igual pasa por el debate y por la verificación bibliográfica.
- [La lista de siglas no-gen queda duplicada respecto de `biomarker_extractor`] → recomendado un `fix/`
  posterior que la unifique.
- [`asyncio.Lock` globales de `rate_limiter.py` usados desde varios `asyncio.run()` en tests/demos, y estado
  del circuit breaker que se filtra entre tests] → los tests mockean el cliente y llaman `reset()` del
  breaker en un fixture.
- [Conflictos de merge con cambios paralelos] → `orchestrator.py`, `debate.py`, `tests/test_orchestrator.py`
  y `tests/test_debate.py` pueden cruzarse con #52 si el árbitro se engancha al debate; `.claude/*.md` se
  cruza con todos (conflictos triviales). No se tocan `hypothesis.py`, `report.py`, `report_builder.py`,
  `schemas.py`, `router.py` ni `base_agent.py`.
- [Si #54 recalcula `priority`, pisaría la degradación de la guarda] → coordinar al integrar: la guarda
  tiene que quedar después de cualquier recálculo de prioridad, o #54 debe respetar la marca.
- [El demo simulado de PharmGKB incluye una anotación pregabalina–CYP2D6 que no tiene sustento
  (la pregabalina se elimina por vía renal sin metabolismo hepático relevante)] → el demo nuevo muestra
  respuestas reales de la API, no datos simulados.

## Migration Plan

Cambio aditivo, sin migración de datos ni cambios en el contrato JSON. Rollback: revertir el merge. Si
hubiera que desactivar el agente sin revertir, alcanza con sacarlo de la lista de agentes del orquestador
(el debate ya lo filtraría por no tener output de Ronda 1).

## Open Questions

- Cupo real de tokens por minuto de `openai/gpt-oss-120b` en el tier de Groq del equipo (el comentario de
  `base_agent.py` dice 12k TPM): se mide en la tarea de medición end-to-end y no cambia el diseño.
- Rutas y forma exacta de la respuesta de la API de PharmGKB: se resuelve con la llamada real de la tarea
  de verificación.
