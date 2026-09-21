# NEXUS — Backlog y Estado del Proyecto

## Tablero Trello
URL: https://trello.com/b/kdXM36sU/sistema-soporte-de-investigacion-clinico-multiagente

---

## Épicas (columna "Épicas")

| ID | Nombre | Prioridad |
|----|--------|-----------|
| EP-01 | Ingesta y normalización de documentos | Alta |
| EP-02 | Síntesis clínica y Estructura PICO | Alta |
| EP-03 | Pipeline multi-agente y debate adversarial | Alta |
| EP-04 | Búsqueda semántica sobre literatura científica | Alta |
| EP-05 | Integración con bases de datos externas | Alta |
| EP-06 | Agente árbitro y verificación de hipótesis | Alta |
| EP-07 | Generación del reporte final | Media |
| EP-08 | Interfaz de usuario (Front) | Media |
| EP-09 | Seguridad, privacidad y anonimización | Alta |
| EP-10 | Validación con casos clínicos reales | Alta |

---

## Finalizado ✅

**Sprint 1 — PoC (Etapa 2)**
- Setup del repositorio, estructura de carpetas y .env
- Módulo de ingesta: extracción de texto de PDF nativo (pdfplumber)
- Agente 01 (Analista Literatura): prompt + Groq + parseo JSON
- Script de prueba con caso clínico anonimizado (neuropatía axonal, 42 años)

**Sprint 2 — Pipeline básico (Etapa 3)**
- Módulo de ingesta: OCR básico para PDFs escaneados (Tesseract)
- Normalización terminológica: nombres INN y unidades de medida
- Agente Orquestador: construcción de síntesis PICO (Groq)
- Extracción de biomarcadores y mapeo del historial terapéutico
- Clase base de agentes (BaseAgent ABC — interfaz común)
- Agente 03 (Consultor Clínico): prompt + Groq + parseo JSON
- Orquestador: distribución paralela con asyncio (Ronda 1)
- Motor de debate: Rondas 2–4 (crítica cruzada entre agentes)
- Cliente ClinicalTrials.gov API v2: búsqueda de ensayos activos

**Sprint 3 — Frontend conectado (Etapa 4)**
- Endpoint FastAPI: POST /api/analyze
- Generación de JSON estructurado con todas las secciones del reporte
- Exportación del reporte a PDF (ReportLab)
- Setup Next.js + conexión al backend FastAPI
- Vista de carga de documentos
- Vista de pipeline con animación de progreso en tiempo real
- Vista de reporte: hipótesis, ensayos clínicos, divergencias y fuentes

---

## Sprint 1 — PoC (Etapa 2) ✅ COMPLETO

Caso de prueba usado: **neuropatía axonal, paciente de 42 años**.

---

## Sprint 2 — Pipeline básico (Etapa 3) ✅ COMPLETO

Épicas cubiertas: EP-01, EP-02, EP-03, EP-05

| # | Tarea | Épica | Archivos clave |
|---|-------|-------|----------------|
| 1 | OCR para PDFs escaneados (Tesseract) | EP-01 | `backend/ingestion/extractor.py` |
| 2 | Normalización INN y unidades de medida | EP-01 | `backend/ingestion/normalizer.py` |
| 3 | Síntesis PICO con LLM | EP-02 | `backend/pipeline/pico.py` |
| 4 | Extracción de biomarcadores e historial terapéutico | EP-02 | `backend/ingestion/biomarker_extractor.py` |
| 5 | Clase base de agentes (BaseAgent ABC) | EP-03 | `backend/agents/base_agent.py` |
| 6 | Agente 03 — Consultor Clínico | EP-03 | `backend/agents/agent_03_clinical.py` |
| 7 | Orquestador asyncio — Ronda 1 | EP-03 | `backend/pipeline/orchestrator.py` |
| 8 | Motor de debate — Rondas 2–4 | EP-03 | `backend/pipeline/debate.py` |
| 9 | Cliente ClinicalTrials.gov API v2 | EP-05 | `backend/external/clinical_trials.py` |

Suite de tests: **82 tests, 100% passing** (`pytest tests/`)

---

## Sprint 3 — Frontend conectado (Etapa 4) ✅ COMPLETO

Épicas cubiertas: EP-07, EP-08

| # | Tarea | Estado |
|---|-------|--------|
| 1 | Modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial | ✅ Hecho (Sprint 2) |
| 2 | Endpoint FastAPI: POST /api/analyze | ✅ Hecho |
| 3 | Generación de JSON estructurado con todas las secciones del reporte | ✅ Hecho |
| 4 | Exportación del reporte a PDF (ReportLab) | ✅ Hecho |
| 5 | Setup Next.js + conexión al backend FastAPI | ✅ Hecho |
| 6 | Vista de carga de documentos | ✅ Hecho |
| 7 | Vista de pipeline con animación de progreso en tiempo real | ✅ Hecho |
| 8 | Vista de reporte: hipótesis, ensayos clínicos, divergencias y fuentes | ✅ Hecho |

---

## Sprint 4 — Árbitro y verificación (Etapa 5) 🔄 EN CURSO

Épicas cubiertas: EP-04, EP-05, EP-06

| # | Tarea | Estado |
|---|-------|--------|
| 1 | Setup ChromaDB: colección y embeddings biomédicos | ✅ Hecho |
| 2 | Indexación de artículos PubMed en ChromaDB | ✅ Hecho |
| 3 | Motor RAG: búsqueda semántica y formateo para prompts | ✅ Hecho |
| 4 | Cliente PubMed E-utilities: búsqueda y parseo de resultados | ✅ Hecho |
| 5 | Cliente Orphanet API: búsqueda de enfermedades raras | ✅ Hecho |
| 6 | Cliente PharmGKB: relaciones fármaco-genómicas | ✅ Hecho |
| 7 | Gestión de rate limits y fallbacks en APIs externas | ✅ Hecho |
| 8 | Agente 02 (Especialista Genómica): prompt + llamada GPT-4o + parseo JSON | 📋 Pendiente |
| 9 | Agente 04 (Árbitro Verificador): síntesis y verificación bibliográfica externa | ✅ Hecho (`agents/agent_04_arbiter.py`, `pipeline/consensus.py`, `pipeline/recitation.py`) |
| 10 | Agente 05 (Navegador de Ensayos): búsqueda en ClinicalTrials + Orphanet | ✅ Hecho (`agents/agent_05_trials.py`, `pipeline/trial_matching.py`) |
| 11 | Priorización de hipótesis por nivel de evidencia EBM (I, II, III) | ✅ Hecho (`pipeline/evidence.py`) |
| 12 | Integrar contexto RAG (búsqueda semántica PubMed) a la Ronda 1 del orquestador | ✅ Hecho |
| 13 | Agente 06 (Sintetizador): reporte final asistido por LLM | 📋 Pendiente |
| 14 | Embeddings biomédicos configurables en el RAG (elegidos midiendo) | ✅ Hecho |
| 15 | Fix: el RAG consultaba PubMed en español — ahora usa `condition_en` | ✅ Hecho |
| 16 | Verificación bibliográfica de PMIDs: título real vs. citado (`pipeline/verification.py`) | ✅ Hecho |
| 17 | Fix: comentarios en línea del `.env.example` se cargaban como valor de la clave | ✅ Hecho |
| 18 | Vista de reporte: mostrar el estado de verificación de hipótesis y fuentes (EP-08) | ✅ Hecho |
| 19 | PDF: incluir el estado de verificación en el reporte exportado (EP-07) | ✅ Hecho |

> Nota (12) — **RESUELTA**: se integró la búsqueda semántica RAG como contexto
> bibliográfico en `backend/pipeline/orchestrator.py` (Ronda 1), y desde la tarea 16
> el pipeline **sí** verifica los PMIDs citados (paso 7 de `api/router.py`).

> Nota (9) — **RESUELTA**. La mitad de verificación ya estaba
> (`pipeline/verification.py`). Se sumó la de **síntesis**: el Árbitro agrupa las
> hipótesis equivalentes de los tres agentes en un consenso, registra quién respalda
> y quién refuta cada una, documenta las objeciones HIGH que nadie retiró y emite un
> veredicto por hipótesis. El pipeline se serializó a
> `debate → verificación → Árbitro → navegación`, así que el Agente 05 busca ensayos
> sobre el consenso y no sobre la concatenación con duplicados.
>
> **Ronda 5 — recitación**: las hipótesis sin respaldo vuelven a su autor con el
> motivo por el que falló cada cita y los artículos que el RAG había recuperado. Los
> PMID nuevos se validan contra ese conjunto **antes** de gastar una consulta a
> PubMed, y después se re-verifican. Una sola iteración.
>
> Esto **corrige el criterio de parada** de `architecture.md`, que exigía que toda
> hipótesis tuviera referencia verificable: con 15 de 15 citas discordantes no se
> cumple nunca. Ahora el análisis termina después de recitar, mejore o no, y el
> resultado se mide y se reporta.
>
> **Hallazgo G — RESUELTO** en la misma tarea: `parse_hypotheses()` armaba
> `Source(**s)` y aceptaba `verified`, `verification_status`, `actual_title` y
> `publication_types` autodeclarados por el LLM. Ahora se descartan en el origen.
>
> Evidencia: `scripts/demo_agente04.py` (y `--sin-red`, que muestra los cuatro
> fallbacks sin conexión). Cambio OpenSpec: `agente-04-arbitro-verificador`.
>
> **Medido en la corrida real del 2026-09-21** sobre el caso base (450 s, sin ningún
> fallback): **14 hipótesis del debate → 8 de consenso**; **19 de 19 referencias
> citadas resultaron discordantes** contra PubMed (ninguna verificada); **0 de 19
> citas salieron de los 5 artículos que el RAG les puso en el prompt**; 3 objeciones
> quedaron sin resolver; 0 referencias inventadas por el Árbitro.
> **Ronda 5: 8 hipótesis recitaron, 5 consiguieron respaldo verificable y 0 PMIDs
> fueron rechazados** — puestos frente a la literatura real y con el motivo por el que
> falló cada cita, los agentes sí citan del conjunto ofrecido. No es incapacidad de
> citar: sin el material delante, inventan. Es el resultado que justifica la ronda.
>
> ⚠ **FALTA UNA CORRIDA LIMPIA** para adjuntar a la tarjeta #52. Los números de arriba
> salen de una corrida que tenía el bug de propagación de los veredictos de la Ronda 5
> (corregido en `e9bd486`): el arbitraje y la verificación son correctos, pero el
> reporte exportado mostraba 0 hipótesis respaldadas. La corrida siguiente, ya con el
> fix, confirmó que el reporte muestra las respaldadas, pero se agotó la **cuota diaria**
> de Groq (197.800/200.000 TPD) y el debate se cayó desde la Ronda 2. Hay que correr una
> vez más, con la cuota repuesta, y regenerar la evidencia.

> Nota (16) — **por qué hizo falta**: los agentes citaban PMIDs alucinados. No eran
> números inválidos: existían en PubMed pero apuntaban a otro artículo, así que
> `verify_pmid()` (chequeo de existencia) los aprobaba a todos. Medido sobre el caso
> de la tesis en tres corridas: **9 de cada 10 referencias eran discordantes**
> (ej.: el agente cita "Metformin-associated vitamin B12 deficiency, Diabetes Care"
> y el PMID 22439958 es "Breeding replacement gilts for organic pig herds").
> Las hipótesis sin respaldo verificable quedan etiquetadas "especulativa" y **no**
> se descartan. Evidencia: `scripts/demo_verificacion.py`.

> Nota (18/19) — **RESUELTA**: la verificación viaja en el JSON (`status`,
> `verified_sources`, `verification_status`, `actual_title`, sección `verification`)
> y ahora se muestra en la vista de reporte (`fd1485e`: franja de cabecera, badge
> respaldada/especulativa, fuentes discordantes tachadas con el título real) y en el
> PDF (`7c728a2`: resumen y advertencia en la portada, veredicto por fuente).

> Nota (numeración) — **RESUELTA**: la numeración vigente es **04 = Árbitro Verificador**
> y **06 = Sintetizador**, tal como figura en este backlog, en `.claude/architecture.md`,
> en `.claude/stack.md` y en el propio código (`external/pubmed.py:256`,
> `rag/retriever.py:189` → Agente 04; `pipeline/report_builder.py:7`,
> `pipeline/pdf_exporter.py:4` → Agente 06). `CLAUDE.md` era el único documento que los
> unificaba como "Agente 06 (Sintetizador/Árbitro)" y quedó corregido.
> Ninguno de los dos está implementado todavía (`backend/agents/` solo tiene
> `agent_01` y `agent_03`), y van como tarjetas separadas en Trello:
> tarea 9 = Agente 04 (Árbitro Verificador), tarea 13 = Agente 06 (Sintetizador).
> La tarea 13 no existía en este backlog: se agregó junto con esta corrección.

Evidencia/verificación de las tareas 1–7: scripts `scripts/demo_*.py` (PubMed, Orphanet,
PharmGKB, rate_limiter, ChromaDB, indexación, motor RAG).
Evidencia de la tarea 16: `scripts/demo_verificacion.py` (consulta PubMed de verdad y
muestra, por fuente, el título citado contra el real).
Evidencia de las tareas 12, 14, 15, 17, 18 y 19, y del fix de biomarcadores: adjunta en
sus tarjetas de Trello (#63, #66, #67, #65, #69, #70 y #68). Se genera en
`output/evidencia/<nro-tarjeta>/`, que es local e ignorada por git. Las tareas 12, 18 y 19
se probaron con una corrida real de `POST /api/analyze` sobre el caso de la tesis.

---

## Sprint 5 — Validación y cierre (Etapa 6)

Épicas cubiertas: EP-09, EP-10

| # | Tarea |
|---|-------|
| 1 | Módulo de anonimización: nombres, fechas e identificadores |
| 2 | Limpieza automática de archivos temporales (SESSION_TTL) |
| 3 | Configuración CORS, validación de origins y HTTPS/TLS |
| 4 | Validación end-to-end: caso neuropatía axonal (42 años) |
| 5 | Definición de criterios de calidad del reporte |
| 6 | Evaluación del output con médico o tutor académico |
| 7 | Documentación final para entrega de tesis |

---

> Nota (11) — **priorización EBM** (cambio OpenSpec `priorizacion-evidencia-ebm`):
> el nivel que autodeclara el LLM se **topea** con los tipos de publicación que PubMed
> indexa para sus fuentes verificadas (Meta-Analysis/Systematic Review/RCT → I;
> observacional, ensayo no aleatorizado, guía o solo "Journal Article" → II; Case Reports,
> Review, carta, editorial o retractada → III). Nunca sube. Sin fuente verificada → III.
> Estados: respaldada / **pendiente** (PubMed no respondió) / especulativa; ninguna se
> descarta. Orden: estado → nivel efectivo → prioridad → fuentes verificadas.
> Decisiones confirmadas: guías con tope II; nivel antes que prioridad. **Limitación
> documentada**: revisiones sistemáticas previas a 2019 indexadas solo como "Review"
> topean en III. Evidencia: `scripts/demo_priorizacion_evidencia.py`, incluido el modo
> `--pubmed` (corrido el 2026-09-15). Cambio OpenSpec archivado en
> `openspec/changes/archive/2026-09-15-priorizacion-evidencia-ebm/`, spec vigente en
> `openspec/specs/clasificacion-evidencia-ebm/`. Tarjeta #54 con evidencia adjunta
> (`priorizacion.txt`, `reporte.json`, `reporte.pdf`, captura de la vista) y en QA.

> Nota (10) — **Agente 05, Navegador de Ensayos** (cambio OpenSpec
> `agente-05-navegador-ensayos`, tarjeta #53): agente **híbrido**. El LLM solo hace
> dos cosas —traducir las hipótesis (hasta 3, sin las `descartada`) a términos de
> condición en inglés y etiquetar cada ensayo `alta`/`media`/`baja`— y **nunca**
> excluye un ensayo ni puede inventar NCT IDs: su salida se valida contra los que se
> le mandaron. Todo lo que quita un ensayo de la vista es determinista
> (`pipeline/trial_matching.py`): saneamiento de términos, filtros duros de edad y
> sexo leídos por reglas del perfil PICO, dedupe por NCT y tope de 10.
> Consulta `RECRUITING` **y** `NOT_YET_RECRUITING` (un ensayo que abre en tres meses
> es accionable, y se etiqueta "aún no recluta"). Orden del resultado:
> compatibilidad → sede en Argentina → ya reclutando → descubrimiento; la sede ordena,
> nunca filtra. Orphanet marca una hipótesis como enfermedad rara solo ante
> **coincidencia exacta** normalizada con el nombre preferido: tomar el primer
> resultado etiquetaba una neuropatía axonal del adulto como enfermedad neonatal letal.
> Corre en paralelo con la verificación bibliográfica (`asyncio.gather` en
> `api/router.py`) y ninguna falla externa rompe `POST /api/analyze`: el reporte trae
> `trial_search` con el estado de cada API. Contrato JSON **aditivo**: `ClinicalTrial`
> suma `compatibility`, `compatibility_rationale`, `criteria_to_verify`,
> `related_hypotheses` y `matched_terms`; `StructuredReport` suma `rare_diseases` y
> `trial_search` (nulo = reporte anterior al agente). Evidencia:
> `scripts/demo_agente05.py` (y `--sin-red`, que muestra los cuatro fallbacks sin
> conexión) + corrida real de `POST /api/analyze` sobre el caso base, artefactos en
> `output/corrida_agente05/` y `output/demo_agente05/` (locales, gitignoreados).
>
> **Medido en la corrida real del 2026-09-15** (294 s en total, sin `ORPHANET_API_KEY`):
> 21 ensayos únicos, 2 excluidos por edad, 0 por sexo, 10 en el reporte; ambas APIs
> `ok`, planificación y evaluación `ok`, **0 evaluaciones descartadas** (el LLM no
> inventó ningún NCT ID). Compatibilidad: 2 `media` y 8 `baja`, ninguna `alta` — el
> caso es una neuropatía sin diagnóstico y casi todos los ensayos de ATTR piden
> cardiomiopatía confirmada. Orphanet marcó 1 hipótesis: ORPHA 85443 *AL amyloidosis*.
> El ensayo con sede en Argentina (NCT07052903) quedó primero dentro de su nivel de
> compatibilidad, no arriba de todo: la sede desempata, no manda.
>
> **Limitación observada**: la búsqueda por relevancia de ClinicalTrials.gov trae
> ruido (con "Hereditary sensory and autonomic neuropathy" devolvió dos ensayos de
> tumores sólidos con mutación ATM). No se filtran —solo los filtros deterministas
> excluyen— pero el LLM los etiquetó `baja` con el motivo explícito, que es lo que
> hace legible la lista.

## Reparto de tareas (2026-09-15)

Se reparte **por área de archivos**, para que dos personas no toquen el mismo módulo.
Surge de un choque real: el mismo día, dos sesiones actualizaron en paralelo los
artefactos OpenSpec del Agente 05 (commits `20498d4` y `13d7f96`), con las mismas
decisiones de fondo y distinto texto. Se resolvió en el merge del PR #13.

| Responsable | Tarjetas | Área / archivos |
|---|---|---|
| **Facundo** | #51 Agente 02 (en curso), #73 fix del regex de genes, #71 cliente ClinVar | Genómica e ingesta: `orchestrator.py`, `debate.py`, `models/case.py`, `pharmgkb.py`, `biomarker_extractor.py`, `external/clinvar.py` |
| **Matías** | #52 Agente 04 (Árbitro) + hallazgo G | Verificación: `verification.py`, `evidence.py`, paso 7 del router, `base_agent.parse_hypotheses()` |
| **Fede** | #74 cliente Orphadata, hallazgos A, B y H, arreglos del PDF (portada y celdas del resumen), y los dos arreglos manuales de Trello (#65 adjunto duplicado, #63 PNG sin extensión) | RAG, frontend y calidad: `rag/retriever.py`, `tests/test_rag_integration.py`, `pdf_exporter.py`, `frontend/` |
| **Sin asignar** | #62 Agente 06 (Sintetizador) | Va **última**: depende de que exista el Agente 04 y pisa el `pdf_exporter.py` que toca Fede. La toma quien se libere primero. |

### Reglas para no pisarnos

1. **Asignarse la tarjeta en Trello antes de arrancar.** Si no tiene a nadie, está libre.
2. **Los artefactos de un cambio OpenSpec los edita solo quien tiene la tarjeta.**
3. **Pushear la rama con el primer commit**, aunque esté a medias: así se ve en GitHub
   que esa tarea está tomada.

## Hallazgos abiertos (pendientes de decisión)

Cosas detectadas y verificadas, que **no** se arreglaron todavía porque exceden
el alcance de la tarea en la que aparecieron. Con archivo y línea, para retomar:

| # | Hallazgo | Dónde |
|---|----------|-------|
| A | El filtro de relevancia del RAG **no filtra nada**. El score es `1 - distancia/2`, así que `_MIN_RELEVANCE_SCORE = 0.3` equivale a un coseno de −0.4. Medido: 0 de 15 resultados quedaron bajo el umbral. Para PubMedBERT un valor razonable estaría cerca de 0.65, pero hay que medirlo con `scripts/demo_embeddings_comparacion.py`. | `backend/rag/retriever.py:33` |
| B | ✅ **RESUELTO** (tarjeta #75, `fix/s4-tests-rag-hermeticos`). Medido con la red bloqueada (`scripts/pytest_sin_red.py`): los 6 tests hacían **89 intentos de conexión** (39 a PubMed, 50 a huggingface.co) y tardaban 165 s — y **pasaban igual sin red**, porque el fallback del orquestador también dice "LITERATURA CIENTÍFICA" y "evidence_level". No distinguían un RAG que funciona de uno caído: contra el orquestador roto a propósito, los 6 pasaban. Ahora mockean indexación y búsqueda (patrón de `TestIdiomaDeLaQueryRag`): 0 conexiones, 0,83 s, y 2 fallan ante esa misma rotura. Aclaración: `tests/test_rag.py` **ya era hermético** (0 conexiones); sus `ReadTimeout` del 15/09 fueron puntuales, durante la primera descarga de PubMedBERT. Evidencia: `scripts/demo_tests_rag_hermeticos.py`. | `tests/test_rag_integration.py::TestEnrichContextWithRag` |
| C | Ningún modelo de embeddings maneja la **negación**: con "negative CMT panel" en la query, los tres modelos evaluados traen Charcot-Marie-Tooth arriba. El hallazgo negativo llega al agente por `negative_findings`, así que el razonamiento puede corregirlo, pero el recuperador no filtra por él. Limitación conocida, vale documentarla en la tesis. | `backend/rag/chroma_store.py` (docstring) |
| D | `master` está **62 commits detrás** de `develop`: Sprints 2, 3 y 4 sin liberar. Decisión del equipo: se promueve cuando haya una versión del sistema, no por etapa. | — |
| E | **OpenSpec**: **adoptado** (v1.11.0, rama `chore/s4-openspec`). Alcance: los 4 agentes que faltan (02, 04, 05, 06) y las reglas de clasificación EBM — sin backfillear los Sprints 1–3. Uso en `.claude/CLAUDE.md` § "Spec-driven con OpenSpec". | `openspec/config.yaml` |
| F | El extractor de biomarcadores devuelve **`genes=['CMT']`** en el caso base: `CMT`, `FAP` y `ATTR` están en `_KNOWN_GENES`, pero son enfermedades o paneles, no genes. Además `tests/test_biomarkers.py` no es un test de pytest (es un script con `main()`, pytest recolecta 0 tests) y exige que `CMT` salga como gen. Por esto la tarjeta #68 no pasó a QA. | `backend/ingestion/biomarker_extractor.py:65-67`, `tests/test_biomarkers.py:63-66` |
| G | ✅ **RESUELTO** (Agente 04). `BaseAgent.parse_hypotheses()` armaba `Source(**s)` con lo que manda el LLM, así que acepta `verified`, `verification_status` o `publication_types` autodeclarados. La clasificación EBM y `_annotate_source()` ya los ignoran/limpian, pero conviene sanearlos en el parseo (lo toca el Agente 04). | `backend/agents/base_agent.py:92` |
| H | Lint del frontend con 1 error y 1 warning **previos** a la priorización EBM: `setState` síncrono en un effect (`report/page.tsx`, `useEffect` de carga del reporte) y un `eslint-disable` sin uso (`analyzing/page.tsx:120`). `next build` no corre lint, así que no bloquea el build. Sigue igual después del Agente 05: el error es del effect que lee `sessionStorage`, ajeno a la tab de ensayos. | `frontend/src/app/report/page.tsx`, `frontend/src/app/analyzing/page.tsx:120` |
| I | **Los genes de enfermedades raras no están en la ORPHAcodes API**: expone 32 rutas y ninguna de genes (es una API de nomenclatura). `get_genes()` levanta `OrphanetGenesNoDisponibles` en vez de mentir con `[]`. Están en Orphadata, otro host y otro producto: `GET https://api.orphadata.com/rd-associated-genes/orphacodes/{code}` (200, CC-BY-4.0, sin apiKey; 404 = esa enfermedad no tiene asociación génica). Integrarlo va en **tarjeta aparte**: el Agente 05 no depende de ellos. | `backend/external/orphanet.py:255` (`get_genes`), docstring del módulo |

---

## Notas importantes

- El caso de prueba base del proyecto es **neuropatía axonal, paciente de 42 años**
- En producción cada agente usa un modelo distinto; en el prototipo todos usan Groq `gpt-oss-120b`
- El frontend definitivo será Next.js, no React (decisión del equipo)
- El tablero tiene una columna **QA** para tareas en revisión antes de pasar a FINALIZADO.
  Al 2026-09-08 tenía **24 tarjetas** esperando revisión del profesor, y FINALIZADO tenía 1.
  El 2026-09-15 se sumaron a QA, con evidencia adjunta, las tarjetas del Sprint 4 cuyo código
  ya estaba en `develop`: #63 (tarea 12), #64 (16), #65 (17), #66 (14), #67 (15), #69 (18),
  #70 (19) y #54 (tarea 11, priorización EBM). La #68 (fix de biomarcadores) tiene evidencia
  pero no pasó (ver hallazgo F).
- **Juan Lencina es el profesor evaluador**, no del equipo. Su criterio: cada tarjeta necesita
  adjunto que compruebe que la tarea funciona (capturas de entrada → salida). Sin eso la
  manda a RECHAZADO. Para eso existen los `scripts/demo_*.py`.
- Las 3 tarjetas en **RECHAZADO** (los módulos de ingesta, EP-01) ya tienen la evidencia
  adjunta desde el 2026-06-15, cinco días después del rechazo, pero nadie las movió de
  vuelta a QA — así que el profesor nunca las re-revisó.
