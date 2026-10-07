# NEXUS — Contexto para Claude Code

## ¿Qué es este proyecto?

NEXUS es un sistema de soporte investigativo clínico multi-agente, desarrollado como
Tesis Final de la carrera Analista en Sistemas (IRESM, Villa Carlos Paz, Córdoba, Argentina).

El sistema recibe documentos clínicos de un paciente (PDFs, imágenes), los procesa mediante
un pipeline de 6 agentes de IA especializados que debaten entre sí en rondas adversariales,
y genera un reporte estructurado con hipótesis de investigación priorizadas por nivel de
evidencia, respaldadas por referencias bibliográficas verificables de PubMed.

**NEXUS no emite diagnósticos. Genera hipótesis de investigación para el médico responsable.**

---

## Estado actual del proyecto

| Etapa | Descripción | Estado |
|-------|-------------|--------|
| 1 | Fundamentación teórica y diseño | ✅ Completada |
| 2 | Proof of concept (Sprint 1) | ✅ Completada |
| 3 | Pipeline multi-agente (Sprint 2) | ✅ Completada |
| 4 | Frontend conectado (Sprint 3) | ✅ Completada |
| 5 | Árbitro + verificación (Sprint 4) | 🔄 En curso |
| 6 | Validación clínica (Sprint 5) | 📋 Planificada |

### Sprint 1 — Completado ✅
- Setup del repositorio, estructura de carpetas y .env
- Módulo de ingesta: extracción de texto de PDF nativo (pdfplumber)
- Agente 01 (Analista Literatura): prompt + Groq + parseo JSON
- Script de prueba con caso clínico anonimizado (neuropatía axonal, 42 años)

### Sprint 2 — Completado ✅ (Pipeline básico — Etapa 3)
- [x] Módulo de ingesta: OCR básico para PDFs escaneados (Tesseract)
- [x] Normalización terminológica: nombres INN y unidades de medida
- [x] Síntesis PICO: construcción de narrativa clínica estructurada
- [x] Extracción de biomarcadores y mapeo del historial terapéutico
- [x] Clase base de agentes (interfaz común — BaseAgent ABC)
- [x] Agente 03 (Consultor Clínico): prompt + llamada Groq + parseo JSON
- [x] Orquestador: distribución paralela con asyncio (Ronda 1)
- [x] Motor de debate: Rondas 2–4 (crítica cruzada entre agentes)
- [x] Cliente ClinicalTrials.gov API v2: búsqueda de ensayos activos

### Sprint 3 — Completado ✅ (Frontend conectado — Etapa 4)
- [x] Modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial (hecho en Sprint 2)
- [x] Endpoint FastAPI: POST /api/analyze (backend/api/router.py + schemas.py)
- [x] Generación de JSON estructurado con todas las secciones del reporte (pipeline/report_builder.py)
- [x] Exportación del reporte a PDF (ReportLab — pipeline/pdf_exporter.py)
- [x] Setup Next.js + conexión al backend FastAPI (frontend/src/lib/api.ts, types.ts)
- [x] Vista de carga de documentos (frontend/src/app/analizar/page.tsx + components/UploadForm.tsx)
- [x] Vista de pipeline con animación de progreso en tiempo real (frontend/src/app/analyzing/page.tsx)
- [x] Vista de reporte: hipótesis, ensayos clínicos, divergencias y fuentes (frontend/src/app/report/page.tsx)

### Sprint 4 — En curso 🔄 (Árbitro + verificación — Etapa 5)
Backend mergeado a `develop` (capa de recuperación de evidencia / RAG). Autor: Facundo.
- [x] Setup ChromaDB con colección y embeddings biomédicos (backend/rag/chroma_store.py)
- [x] Cliente PubMed E-utilities + verificación de PMIDs (backend/external/pubmed.py)
- [x] Indexación de artículos PubMed en ChromaDB (backend/rag/indexer.py)
- [x] Motor RAG: búsqueda semántica + formateo para prompts (backend/rag/retriever.py)
- [x] Cliente Orphanet API: enfermedades raras (backend/external/orphanet.py)
- [x] Cliente PharmGKB: relaciones fármaco-genómicas (backend/external/pharmgkb.py)
- [x] Cliente ClinVar: significancia clínica de variantes, con coincidencia verificada
      (backend/external/clinvar.py; lo consume `pipeline/genomic_context.enrich()`)
- [x] Gestión de rate limits y fallbacks para APIs externas (backend/external/rate_limiter.py)
- [x] Scripts de demo EP05: pubmed, orphanet, pharmgkb, rate_limiter (scripts/demo_*.py)
- [x] Scripts de demo RAG: chromadb, indexacion_pubmed, motor_rag (scripts/demo_*.py)
- [x] Scripts de demo EP07: modelos_pydantic, reporte_json, endpoint_fastapi (scripts/demo_*.py)
- [x] Embeddings biomédicos configurables en el RAG (backend/rag/chroma_store.py)
- [x] Fix: el RAG consultaba PubMed en español — ahora usa `condition_en`
- [x] **Integrar** RAG + verificador de PMIDs en el flujo del pipeline (router/orchestrator)
- [x] Verificación bibliográfica de PMIDs: título real vs. citado (backend/pipeline/verification.py)
- [x] Vista de reporte: estado de verificación de hipótesis y fuentes (frontend/src/app/report/page.tsx)
- [x] PDF: estado de verificación en el reporte exportado (backend/pipeline/pdf_exporter.py)
- [x] Agente 02 (Especialista Genómica): prompt + llamada LLM + parseo JSON
      (backend/agents/agent_02_genomics.py — PR #12, 2026-09-16; cableado en
      pipeline/orchestrator.py, pipeline/debate.py y api/router.py)
- [x] Agente 04 (Árbitro Verificador): consenso, contradicciones y Ronda 5 de recitación
      (backend/agents/agent_04_arbiter.py + pipeline/consensus.py + pipeline/recitation.py)
- [x] Agente 05 (Navegador de Ensayos): ClinicalTrials.gov + Orphanet
      (backend/agents/agent_05_trials.py + backend/pipeline/trial_matching.py)
- [x] Agente 06 (Sintetizador): `executive_summary` en prosa con guarda anti-invención
      (backend/agents/agent_06_synthesizer.py — corre después de `build_export()`, no lo reemplaza)
- [x] Priorización de hipótesis por nivel de evidencia EBM (I, II, III) (backend/pipeline/evidence.py)
- [x] Control de costos: punto único de llamada al proveedor, telemetría de
      tokens por análisis, tarifas configurables, techo y modelo por tarea
      (`backend/agents/model_tasks.py`), modo mock del pipeline
      (`NEXUS_MOCK_LLM`). Ver "Modelo de IA actual" más abajo. Medido sobre
      una corrida real el 2026-10-06 (`scripts/medir_costos.py`): **80.458
      tokens por caso** (43.240 de entrada y 37.218 de salida), 28 llamadas,
      2 casos por día de cuota. Reemplaza a las cifras anteriores (77.516 del
      2026-10-04 y 78.158 de la primera corrida del 2026-10-06), que se
      midieron con el debate corriendo **sin críticas**: el destinatario que
      declaraba el modelo no coincidía con el ID del agente y ninguna crítica
      llegaba (arreglo en el PR #31). Los techos de agrupación y
      planificación de términos volvieron a 4096: con 512 y 1024 se cortaban,
      porque los `gpt-oss` cuentan el razonamiento dentro de la salida.
- [x] Registro de médicos con matrícula, revisión admin y protección de `POST
      /api/analyze`/`POST /api/report/pdf` (backend/models/{cuenta,auditoria,sesion}.py,
      backend/db.py, backend/auth/, backend/api/{cuentas_router,admin_router}.py,
      backend/cli.py, frontend/src/app/{registro,ingresar,cuenta,admin/pendientes}/) —
      OpenSpec `registro-medicos-matricula`, ver nota (22) en `.claude/backlog.md`

> El pipeline de `POST /api/analyze` quedó **serializado**:
> `debate → verificación → Árbitro (04) → navegación de ensayos (05)`. El RAG
> enriquece el contexto de la Ronda 1 y ahora **conserva** los artículos
> recuperados en el `Report`, que es lo que permite medir si los agentes citan
> la literatura que se les da. El Agente 06 corre al final y solo agrega el
> `executive_summary`; no reemplaza a `report_builder.py`.
>
> El Agente 04 es **híbrido**: el LLM solo propone qué hipótesis son
> equivalentes —devolviendo índices, nunca texto— y redacta los veredictos. La
> validación del agrupamiento, la elección del enunciado representativo, la
> detección de contradicciones y la clasificación EBM son deterministas
> (`pipeline/consensus.py`, `pipeline/evidence.py`). El LLM nunca descarta una
> hipótesis, nunca introduce referencias y nunca altera un nivel de evidencia.
>
> **Ronda 5 — recitación**: las hipótesis sin respaldo vuelven a su autor con el
> motivo por el que falló cada cita y los artículos que el RAG recuperó, para que
> vuelvan a citar sobre literatura real. Una sola iteración; lo que siga sin
> respaldo queda especulativo. Esto **reemplaza** el criterio de parada que
> figuraba en `architecture.md` ("toda hipótesis con referencia verificable"),
> que con 15 de 15 citas discordantes no se cumplía nunca.
>
> El Agente 05 es **híbrido**: el LLM solo traduce hipótesis a términos de
> condición en inglés y etiqueta compatibilidad (`alta`/`media`/`baja`); la
> búsqueda, los filtros duros por edad y sexo, la coincidencia exacta con
> Orphanet y el orden del resultado son deterministas y viven en
> `pipeline/trial_matching.py`. El LLM nunca excluye un ensayo.

#### Numeración de agentes (canónica)

| ID | Rol | Estado |
|----|-----|--------|
| 01 | Analista de Literatura | ✅ Implementado |
| 02 | Especialista Genómica | ✅ Implementado |
| 03 | Consultor Clínico | ✅ Implementado |
| 04 | Árbitro Verificador | ✅ Implementado |
| 05 | Navegador de Ensayos | ✅ Implementado |
| 06 | Sintetizador | ✅ Implementado |

> La **fuente de verdad** de la numeración y los roles es la tabla de
> `.claude/architecture.md`. Este archivo la replica solo para consulta rápida:
> ante cualquier discrepancia, manda `architecture.md`.
>
> El código ya usa esta numeración: `external/pubmed.py` y `rag/retriever.py`
> referencian al Agente 04 como Árbitro Verificador; `pipeline/report_builder.py`
> y `pipeline/pdf_exporter.py` referencian al Agente 06 como Sintetizador;
> `external/pharmgkb.py` referencia al Agente 02 como Especialista Genómica.

### Setup del RAG (Sprint 4)

El modelo de embeddings por defecto necesita `sentence-transformers`:

```bash
pip install -r backend/requirements.txt
```

Arrastra torch. Ojo: pip instala la build CUDA por defecto (~5,6 GB de
librerías NVIDIA que no se usan, porque el código corre en `device="cpu"`).
Para la build liviana:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Sin `sentence-transformers` el RAG **igual funciona**: cae a `all-MiniLM-L6-v2`
(el default de ChromaDB, dominio general) y avisa por stderr.

Si se cambia de modelo hay que **re-indexar**: `backend/rag/chroma_store.py`
levanta `EmbeddingModelMismatch` si la colección en disco fue construida con
otro modelo, porque los vectores no son comparables. La salida es
`reset_collection()`. `chroma_db/` es descartable (gitignoreada).

### Setup de cuentas y alta del primer admin (Sprint 4)

`SQLModel.metadata.create_all()` crea el esquema (`cuenta_medico`,
`decision_auditoria`, `sesion`) al levantar el backend — no hace falta correr
nada a mano. El archivo SQLite (`NEXUS_DB_PATH`, default `./data/nexus.db`)
es descartable y gitignoreado, igual que `chroma_db/`.

Ninguna instalación trae una cuenta admin por defecto
(`revision-admin-matriculas` — Requirement: Alta del primer administrador).
Darla de alta:

```bash
python -m backend.cli crear-admin --email admin@tu-dominio.example
# Pide la contraseña de forma interactiva (sin eco). También acepta
# --password para scripts, pero no la dejes en el historial de la shell.
```

Falla si ya existe una cuenta con ese email — se puede correr más de una vez
para dar de alta más de un admin. `SECRET_KEY` (firma la cookie de sesión) y
`ALLOWED_ORIGINS` (valida `Origin`/`Referer` en todo endpoint que cambia
estado) tienen que estar en `.env` antes de levantar el backend: sin
`SECRET_KEY`, `backend/auth/sesiones.py` levanta `SecretKeyNoConfigurada` en
el primer login.

### Verificación / evidencia (scripts de demo)
Para documentar cada tarea (capturas para Trello) hay scripts en `scripts/demo_*.py`
que muestran entrada → salida de cada módulo. Cada uno guarda artefactos en `output/`.
Correr con: `python3 scripts/demo_<nombre>.py`

La evidencia que se sube a cada tarjeta (PNG de entrada → salida + `.txt` con la
salida completa + `.json` resumen) se genera en `output/evidencia/<nro-tarjeta>/`,
que es local e ignorada por git. Lo que queda es el adjunto en Trello.

Scripts disponibles:
- `demo_pubmed.py` — cliente PubMed E-utilities (búsqueda + verificación PMIDs)
- `demo_orphanet.py` — cliente Orphanet (enfermedades raras)
- `demo_pharmgkb.py` — cliente PharmGKB (fármaco-genómica)
- `demo_clinvar.py` — cliente ClinVar: TTR `c.148G>A` (encontrada), `p.Val50Met`, `Val30Met`
  (ambigua) y una inexistente, más el bloque del Agente 02; `--sin-red` simula la caída de NCBI
- `demo_rate_limiter.py` — RateLimiter, CircuitBreaker, with_fallback
- `demo_chromadb.py` — setup ChromaDB + embeddings biomédicos
- `demo_indexacion_pubmed.py` — indexación de artículos PubMed en ChromaDB
- `demo_motor_rag.py` — búsqueda semántica RAG + formateo para prompts
- `demo_modelos_pydantic.py` — modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial
- `demo_reporte_json.py` — generación JSON estructurado via report_builder.build_export()
- `demo_endpoint_fastapi.py` — contrato y ejemplo de respuesta del endpoint POST /api/analyze
- `demo_embeddings_comparacion.py` — compara el modelo de embeddings biomédico vs el general
  sobre el caso de prueba (rankings, overlap y dispersión de scores)
- `demo_verificacion.py` — verificación bibliográfica: contrasta contra PubMed los PMIDs
  citados por los agentes y muestra el título real al lado del citado (Agente 04)
- `demo_priorizacion_evidencia.py` — priorización EBM: nivel declarado vs. efectivo, estado
  y orden del reporte; genera `priorizacion.txt`, `reporte.json` y `reporte.pdf`
  (`--pubmed` verifica PMIDs reales)
- `demo_agente02.py` — Agente 02: caso base (sin hallazgos, `CMT` descartado) y caso TTR
  `p.Val30Met`: perfil genómico, bloque enviado al LLM e hipótesis con la guarda anti-invención;
  guarda los JSON en `output/demo_agente02/`
- `demo_agente04.py` — Agente 04: entrada (hipótesis del debate con su autor y las
  críticas) → salida (partición del agrupamiento, contradicciones, veredictos, Ronda 5
  y solapamiento entre lo que el RAG recuperó y lo que los agentes citaron); genera
  `arbitraje.json` y `resumen.txt`. `--sin-red` simula cuatro caídas (LLM al agrupar,
  LLM devolviendo texto libre, LLM citando un PMID inventado, PubMed sin responder)
- `demo_agente05.py` — Agente 05: entrada (candidatas, términos saneados, demografía)
  → salida (ensayos con compatibilidad, sede, excluidos por edad/sexo, enfermedades
  raras, estado de cada API y latencia); genera `navegacion.json` y `resumen.txt`.
  `--sin-red` usa respuestas grabadas y simula la caída de ClinicalTrials.gov,
  Orphanet y el LLM para mostrar cada fallback (`fallbacks.txt`)
- `demo_agente06.py` — Agente 06: contexto enviado al LLM → `executive_summary`, y la guarda
  anti-invención sobre PMID/NCT/gen inventados; guarda `output/demo_agente06/resumen.json`
- `demo_costos.py` (control de costos, Sprint 4) — corre siempre en modo mock,
  sin red ni cuota: (1) `pico.build()` + `biomarker_extractor.extract()` con
  `NEXUS_MOCK_LLM=1` dentro de un registro de telemetría, para probar el
  mecanismo de punta a punta; (2) una muestra sintética de 18 llamadas
  (conteos inventados, no una corrida real) con el desglose de tokens por
  agente y la comparación de costo Groq vs. arquitectura de destino via
  `usage.recalculate()`. Genera `mecanismo_mock.json`, `muestra_sintetica.json`
  y `comparacion_costos.txt`
- `medir_costos.py` (no es un demo: gasta cuota real) — una pasada del pipeline
  más la comparación `GROQ_MAIN` vs. `GROQ_FAST`; guarda en
  `output/medicion_costos/`. `--mock` lo recorre sin cuota. `--grabar` abre el
  grabador de `backend/mock/recorder.py` durante la pasada base y escribe
  `grabacion.json` (no graba en modo mock). Cada ejecución real gasta unos
  20.000 tokens extra en la comparación
- `demo_registro_medicos.py` — registro de médicos, revisión admin y pipeline
  protegido: dos altas → intento de análisis rechazado (pendiente, 403) → alta
  del primer admin por CLI → aprobación con auditoría → análisis permitido
  (pipeline mockeado) → rechazo con motivo → reenvío corregido. Contra una base
  SQLite temporal en memoria, cero llamadas a un LLM. Genera `flujo.json` y
  `resumen.txt` en `output/demo_registro/`

También se corrigió un bug del Sprint 2: falsos positivos en el extractor de
biomarcadores (regex de anticuerpos y de marcadores de lab). Ver commit `e72e004`.

---

## Estructura de carpetas actual

```
tesis-iresm/
├── .claude/
│   ├── CLAUDE.md               ← este archivo
│   ├── architecture.md         ← arquitectura detallada del pipeline
│   ├── backlog.md              ← estado del backlog / Trello
│   ├── stack.md                ← decisiones tecnológicas
│   ├── commands/opsx/          ← slash commands de OpenSpec (/opsx:*)
│   └── skills/openspec-*/      ← skills de OpenSpec (generadas por `openspec init`)
├── openspec/
│   ├── config.yaml             ← contexto del proyecto + reglas para los artefactos
│   ├── specs/                  ← specs vigentes del sistema (por capacidad)
│   └── changes/                ← cambios en curso; archive/ guarda los cerrados
├── .vscode/
│   ├── extensions.json         ← extensiones recomendadas del equipo
│   └── settings.json           ← configuración compartida
├── backend/
│   ├── agents/
│   │   ├── base_agent.py           ← clase base ABC con interfaz común
│   │   ├── agent_01_literature.py  ← Analista de Literatura (Groq)
│   │   ├── agent_02_genomics.py    ← Especialista Genómica (S4) + guarda anti-invención
│   │   ├── agent_03_clinical.py    ← Consultor Clínico (Groq)
│   │   ├── agent_04_arbiter.py     ← Árbitro Verificador (S4) — arbitrate(), no debate
│   │   ├── agent_05_trials.py      ← Navegador de Ensayos (S4) — navigate(), no debate
│   │   ├── agent_06_synthesizer.py ← Sintetizador (S4) — synthesize(), executive_summary
│   │   └── __init__.py
│   ├── auth/                       ← autenticación, sesión y autorización (S4)
│   │   ├── security.py             ← hash/verify de contraseña (Argon2id)
│   │   ├── sesiones.py             ← crear/resolver/invalidar sesión + cookie
│   │   ├── login.py                ← autenticar() + límite de intentos fallidos
│   │   ├── deps.py                 ← Depends() de FastAPI: sesión, rol, estado
│   │   ├── origen.py               ← validación Origin/Referer (mitigación CSRF)
│   │   └── verificacion.py         ← LicenseVerificationProvider — punto de
│   │                                   extensión sin implementar (design.md D6)
│   ├── ingestion/
│   │   ├── extractor.py            ← PDF nativo (pdfplumber) + OCR (Tesseract)
│   │   ├── normalizer.py           ← normalización INN y unidades de medida
│   │   ├── biomarker_extractor.py  ← extracción genes, anticuerpos, fármacos
│   │   └── __init__.py
│   ├── models/
│   │   ├── hypothesis.py       ← Hypothesis, Priority, EvidenceLevel, Source
│   │   ├── report.py           ← AgentOutput, Report
│   │   ├── case.py             ← ClinicalCase, PICOSynthesis
│   │   ├── biomarkers.py       ← BiomarkerProfile
│   │   ├── genomics.py         ← GenomicContext, ClinVar y PharmGKB del Agente 02 (S4)
│   │   ├── arbitration.py      ← consenso, contradicciones y resumen del Agente 04 (S4)
│   │   ├── trial.py            ← ClinicalTrial + contrato del Agente 05 (S4)
│   │   ├── cuenta.py           ← CuentaMedico, RolCuenta, EstadoCuenta (S4)
│   │   ├── auditoria.py        ← DecisionAuditoria, DecisionTipo (S4)
│   │   ├── sesion.py           ← Sesion — fila server-side de la cookie (S4)
│   │   └── __init__.py
│   ├── mock/                   ← modo mock del pipeline (S4)
│   │   ├── mode.py             ← activación de `NEXUS_MOCK_LLM`
│   │   ├── responses.py        ← respuestas por tarea, carga diferida de grabadas.json
│   │   ├── grabadas.json       ← respuestas textuales de la corrida real del 2026-10-07
│   │   ├── recorder.py         ← grabador de respuestas crudas (solo lo abre un script)
│   │   └── __init__.py
│   ├── telemetry/              ← control de costos (S4)
│   │   ├── usage.py            ← registro de consumo por análisis (contextvars)
│   │   ├── pricing.py          ← tabla de tarifas por modelo
│   │   ├── medicion.py         ← lógica de la medición de costos
│   │   └── __init__.py
│   ├── db.py                   ← engine SQLite + create_db_and_tables() (S4)
│   ├── cli.py                  ← `python -m backend.cli crear-admin` (S4)
│   ├── pipeline/
│   │   ├── pico.py             ← build() síntesis PICO + format_for_agents()
│   │   ├── genomic_context.py  ← build() determinista + enrich() PharmGKB/ClinVar (S4)
│   │   ├── orchestrator.py     ← distribución paralela asyncio (Ronda 1)
│   │   ├── debate.py           ← motor de debate adversarial (Rondas 2–4)
│   │   ├── verification.py     ← verificación de PMIDs citados contra PubMed (S4)
│   │   ├── evidence.py         ← clasificación EBM: tope de nivel, estado y orden (S4)
│   │   ├── consensus.py        ← lógica determinista del Agente 04: partición,
│   │   │                          representante, contradicciones, solapamiento RAG (S4)
│   │   ├── recitation.py       ← Ronda 5: qué se recita y qué se acepta (S4)
│   │   ├── trial_matching.py   ← lógica determinista del Agente 05: términos,
│   │   │                          filtros edad/sexo, Orphanet, orden (S4)
│   │   ├── report_builder.py   ← generación de JSON estructurado del reporte
│   │   ├── pdf_exporter.py     ← exportación a PDF con ReportLab
│   │   └── __init__.py
│   ├── external/
│   │   ├── clinical_trials.py  ← cliente ClinicalTrials.gov API v2
│   │   ├── pubmed.py           ← cliente PubMed E-utilities + verificación PMIDs (S4)
│   │   ├── orphanet.py         ← cliente Orphanet: enfermedades raras (S4)
│   │   ├── pharmgkb.py         ← cliente PharmGKB: fármaco-genómica (S4)
│   │   ├── clinvar.py          ← cliente ClinVar: significancia de variantes (S4)
│   │   └── rate_limiter.py     ← rate limits y fallbacks para APIs externas (S4)
│   ├── rag/                    ← capa RAG de evidencia (Sprint 4)
│   │   ├── chroma_store.py     ← ChromaDB + embeddings biomédicos
│   │   ├── indexer.py          ← indexación de artículos PubMed en ChromaDB
│   │   ├── retriever.py        ← motor RAG: búsqueda semántica
│   │   └── __init__.py
│   ├── api/
│   │   ├── router.py            ← POST /api/analyze, POST /api/report/pdf (protegidos, S4)
│   │   ├── schemas.py           ← schemas Pydantic del reporte
│   │   ├── cuentas_router.py    ← POST/PUT /api/registro, /login, /logout, GET /cuenta (S4)
│   │   ├── admin_router.py      ← GET /api/admin/pendientes, aprobar/rechazar (S4)
│   │   ├── schemas_cuentas.py   ← Pydantic: registro, login, estado de cuenta (S4)
│   │   └── schemas_admin.py     ← Pydantic: pendiente, aprobar, rechazar (S4)
│   ├── main.py                  ← FastAPI app + rutas + CORS + lifespan (create_db_and_tables, S4)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            ← landing demostrativa (S4) — Server Component
│   │   │   ├── globals.css         ← tokens: azul marino + ocre, tema claro/oscuro por atributo (S4)
│   │   │   ├── analizar/
│   │   │   │   ├── page.tsx        ← vista de carga (S4, movida desde `/`; guard de
│   │   │   │   │                      sesión — capa de UX, no de seguridad)
│   │   │   │   └── layout.tsx      ← metadata propia de la ruta (S4)
│   │   │   ├── analyzing/page.tsx  ← vista de pipeline con progreso en tiempo real
│   │   │   ├── report/page.tsx     ← vista de reporte (5 tabs)
│   │   │   ├── registro/page.tsx   ← alta de médico + consentimiento Ley 25.326 (S4)
│   │   │   ├── ingresar/page.tsx   ← login (S4)
│   │   │   ├── cuenta/page.tsx     ← estado de cuenta + reenvío tras rechazo (S4)
│   │   │   └── admin/pendientes/page.tsx ← revisión admin de cuentas pendientes (S4)
│   │   ├── components/
│   │   │   ├── UploadForm.tsx      ← formulario de carga PDF/texto
│   │   │   ├── ScrollReveal.tsx    ← animación de aparición al hacer scroll (S4)
│   │   │   ├── ReportDemo.tsx      ← vista del reporte de ejemplo (ilustrativa) de la landing (S4)
│   │   │   ├── BeforeAfter.tsx     ← cita declarada vs. título real de PubMed (dato real, S4)
│   │   │   ├── DebateDiagram.tsx   ← diagrama SVG del flujo del pipeline (S4)
│   │   │   ├── ThemeToggle.tsx     ← selector claro/oscuro de la barra (S4)
│   │   │   ├── ThemeScope.tsx      ← mantiene /report y /analyzing en claro (S4)
│   │   │   └── icons.tsx           ← iconos SVG inline (agentes, cuentas y tema, S4)
│   │   └── lib/
│   │       ├── api.ts              ← cliente HTTP al backend FastAPI (credentials: "include", S4)
│   │       ├── types.ts            ← tipos TypeScript del reporte y de cuentas (S4)
│   │       ├── inputStore.ts       ← estado compartido entre vistas
│   │       └── pipelineSteps.ts    ← pasos del pipeline (S4, fuente única landing + /analizar)
│   ├── next.config.ts
│   └── package.json
├── scripts/
│   ├── poc_test.py             ← script de prueba end-to-end Sprint 1
│   ├── demo_registro_medicos.py ← flujo completo de registro/revisión admin (S4)
│   └── demo_*.py               ← scripts de verificación por tarea (evidencia Trello):
│       │                          extraccion, ocr, normalizacion, biomarcadores, pico,
│       │                          base_agent, agente01, agente03, orquestador,
│       └─                         clinical_trials, debate, pdf, agente05
├── tests/
│   ├── test_ingesta.py
│   ├── test_normalizer.py
│   ├── test_pico.py
│   ├── test_biomarkers.py
│   ├── conftest.py             ← fixtures de cuentas: base SQLite en memoria
│   │                              autouse (aísla toda la suite de ./data/nexus.db),
│   │                              client/client_medico_verificado/client_admin (S4)
│   └── test_{cuentas_modelo,auditoria_y_sesion_modelo,db,security,origen,
│       sesiones,deps,login,registro,admin,proteccion_analisis}.py ← Sprint 4
├── output/                     ← JSONs generados (ignorado por git)
├── .env.example
├── .gitignore
└── README.md
```

---

### Identidad visual del frontend (S4)

Azul marino institucional con acento ocre, títulos en Newsreader y cuerpo en
Atkinson Hyperlegible, para las pantallas que usan los tokens (`/`, `/analizar`,
`/registro`, `/ingresar`, `/cuenta`, `/admin/pendientes`). El tema claro es el
predeterminado; el oscuro se elige con el selector de la barra (atributo
`data-theme` en `<html>`, clave `nexus-theme` en `localStorage`). `/report` y
`/analyzing` siguen con colores fijos claros y Geist: se migran en otra etapa.

---

## Workflow de Git (IMPORTANTE)

- **Rama principal de desarrollo:** `develop`
- **Nunca commitear directo a `master` ni `develop`**
- **Cada tarea = una rama** con naming: `feature/s{sprint}-{descripcion-corta}`
- **Flujo:** `feature/...` → PR → merge a `develop` → al cerrar etapa → `develop` a `master`

```bash
# Antes de arrancar una tarea
git checkout develop && git pull origin develop
git checkout -b feature/s2-nombre-tarea

# Al terminar
git add <archivos>
git commit -m "feat: descripción"
git push -u origin feature/s2-nombre-tarea
# Luego: PR en GitHub base:develop ← compare:feature/...
```

---

## Spec-driven con OpenSpec

Los agentes que faltan (02, 04, 05, 06) y las reglas de clasificación EBM se planifican
con [OpenSpec](https://github.com/Fission-AI/OpenSpec) antes de tocar código. No se
backfillean los Sprints 1–3. Requiere el CLI: `npm install -g @fission-ai/openspec@latest`.

| Comando | Qué hace |
|---------|----------|
| `/opsx:explore` | Pensar un problema o investigar antes de comprometerse a un cambio |
| `/opsx:propose <idea>` | Crea `openspec/changes/<nombre>/` con proposal, specs, design y tasks. Solo planifica |
| `/opsx:apply` | Implementa las tareas de un cambio ya propuesto |
| `/opsx:update` | Ajusta los artefactos de un cambio en curso |
| `/opsx:sync` | Vuelca las specs delta del cambio a `openspec/specs/` |
| `/opsx:archive` | Cierra el cambio y lo mueve a `changes/archive/` |

- El contexto del proyecto y las reglas de las tareas (test en `tests/`,
  `scripts/demo_*.py` como evidencia para Trello) viven en `openspec/config.yaml`.
  Si cambia una regla de este archivo que afecte cómo se planifica, actualizarla ahí también.
- Los artefactos se escriben en español; los encabezados estructurales y las
  palabras SHALL/MUST quedan en inglés (así lo configura `openspec init --language es`).
- Un cambio de OpenSpec vive en la misma rama de git que su implementación.
- `openspec validate --all` valida specs y cambios; `openspec list` muestra los cambios abiertos.

---

## Modelo de IA actual

> **Groq — `openai/gpt-oss-120b`** — reemplaza temporalmente a Claude/Gemini/GPT-4o
> mientras se gestionan créditos en las APIs de pago.
> La arquitectura final usará Claude Opus (agentes 01, 04, 06),
> GPT-4o (agente 02) y Gemini Pro (agente 03).

Constantes disponibles en `backend/agents/model_tasks.py` (re-exportadas desde
`base_agent.py` por compatibilidad):
- `GROQ_MAIN = "openai/gpt-oss-120b"` — razonamiento clínico
- `GROQ_FAST = "openai/gpt-oss-20b"` — tareas de salida acotada y validada por código

> ⚠ Groq dio de baja los LLaMA 3.x (`llama-3.3-70b-versatile` y
> `llama-3.1-8b-instant`): la API devuelve 404 `model_not_found`. Se reemplazaron
> por los `gpt-oss` en el commit `5174330`. Las constantes anteriores
> —`GROQ_LLAMA` y `GROQ_LLAMA_FAST`— **ya no existen**.

### Punto único de llamada al proveedor (Sprint 4 — control de costos)

**Ningún módulo instancia el cliente de Groq por su cuenta.** El único lugar
del sistema que lo hace es `call_provider()` en `backend/agents/base_agent.py`
(`grep -rn "Groq(api_key" backend/` tiene que devolver una sola línea, la de
adentro de esa función). Todo lo demás pasa por ahí:

- `BaseAgent._call_llm(self, user_message, *, task)` — usado por los agentes
  y por `critique()`/`revise()`/`recite()` del debate.
- `pipeline/pico.py` e `ingestion/biomarker_extractor.py` — no son agentes,
  llaman a `call_provider()` directamente.

`task` es obligatorio y nombra la tarea (p. ej. `"agente01_hipotesis"`,
`"arbitro_agrupacion"`, `"pico_sintesis"`): con eso se resuelve el **modelo y
el techo de tokens** desde el mapa `backend/agents/model_tasks.py`
(`TASK_BUDGETS`), no desde `self.MODEL` de la clase del agente. Revisar qué
modelo y qué techo usa cada llamada es leer ese único mapa, sin recorrer los
agentes. Solo tres tareas usan `GROQ_FAST` (agrupación del Árbitro,
planificación de términos y evaluación de compatibilidad del Agente 05): su
salida ya se valida deterministicamente por código
(`pipeline/consensus.py`/`pipeline/trial_matching.py`). Todo lo que produce
hipótesis, críticas, revisiones, veredictos o la síntesis PICO usa
`GROQ_MAIN` y no se degrada.

`call_provider()` también es donde vive el reintento ante 429, la telemetría
de consumo (`backend/telemetry/usage.py`) y el modo mock (ver abajo). El swap
de proveedor (Claude/GPT-4o/Gemini) se agrega en ese único método.

Vale tenerlo en cuenta al escribir el Agente 06: si asume la firma de Groq en
lugar de delegar en `_call_llm()`/`call_provider()`, rompe la regla y deja su
consumo fuera de la telemetría.

### Telemetría de costos

Cada llamada al proveedor queda registrada (paso, modelo, tokens de entrada y
salida, latencia, si falló) en un registro por análisis
(`backend/telemetry/usage.py`, basado en `contextvars`: no mezcla análisis
concurrentes). El router (`api/router.py`) abre el registro al empezar
`POST /api/analyze` y lo cierra al terminar, escribiendo una línea JSON en
`output/costos.jsonl` (gitignoreado, descartable) y un resumen legible por
stderr. El identificador de análisis es aleatorio, nunca un hash del caso: no
se puede usar para vincular dos análisis del mismo paciente. La telemetría
nunca contiene texto clínico, prompts ni respuestas del modelo — solo
conteos —, y un fallo al escribirla nunca rompe el análisis.

`backend/telemetry/pricing.py` tiene la tabla de tarifas por modelo (Groq en
cero; los modelos de la arquitectura de destino, comentados). Un registro ya
guardado se puede recalcular con otra tabla vía `usage.recalculate()`, sin
correr nada — es como se responde "¿cuánto costaría esto con Claude Opus?".

`scripts/demo_costos.py` muestra el mecanismo (en modo mock, sin gastar
cuota) y una comparación de costo Groq vs. arquitectura de destino sobre una
muestra sintética. Los números de una corrida real **ya están medidos**
(`scripts/medir_costos.py`, 2026-10-06): 80.458 tokens por caso en 28 llamadas
(7 fallidas por límite de velocidad y reintentadas), 505 s en la pasada base,
0 respuestas cortadas por el techo, 2 casos por día de la cuota de 200.000
tokens. Cada ejecución del script gasta además unos 20.000 tokens en la
comparación de modelos. Las cifras anteriores (77.516 y 78.158) quedan
superadas: se midieron sin que las críticas del debate llegaran a los agentes.
El costo equivalente con Claude, GPT-4o o Gemini sigue estimado sobre la
muestra sintética; con el `costos.jsonl` real se puede recalcular con
`usage.recalculate()`.

### Modo mock del pipeline

`NEXUS_MOCK_LLM=1` (variable de entorno, **apagada por defecto**) hace que
`call_provider()` devuelva respuestas grabadas (`backend/mock/responses.py`)
en vez de llamar a Groq, sin tocar la red. Las respuestas grabadas atraviesan
el mismo parseo y las mismas validaciones que una respuesta real — es la
condición para que sirva para desarrollar sobre el pipeline. Sin
`GROQ_API_KEY` y sin este modo activo, el análisis falla con un error claro
(nunca cae en silencio a datos grabados). El reporte de modo mock queda
marcado (`StructuredReport.metadata.mock`) y la marca se muestra en el PDF y
en el frontend con la misma visibilidad que la advertencia del consenso de
IA.

Las trece tareas de `TASK_BUDGETS` usan respuestas **textuales de la corrida
real del 2026-10-07** (22 respuestas: una por llamada, con el agente que la
pidió), guardadas en `backend/mock/grabadas.json` (versionado) y
cargadas de forma diferida por `backend/mock/responses.py` en el primer uso en
modo mock: el modo real nunca lee ese archivo, y si falta o está malformado se
levanta `RespuestasGrabadasInvalidas`. Salieron de `backend/mock/recorder.py`,
un grabador de respuestas crudas basado en `contextvars` que **solo abre un
script** (nunca una variable de entorno ni `POST /api/analyze`) y guarda
únicamente la respuesta del modelo, nunca el prompt. Se usa con
`scripts/medir_costos.py --grabar`, que lo abre durante la pasada base y escribe
`output/medicion_costos/grabacion.json` (gitignoreado);
`scripts/regenerar_mock.py` la convierte en `grabadas.json`. Como cada agente
recibe su propia grabación en el orden en que la pidió, el modo mock reproduce
la corrida: 9 hipótesis de consenso sin repetidas, 10 ensayos y el
`executive_summary` del Agente 06. Salvedad: los PMIDs y NCT que citan las
grabadas pertenecen a esa corrida y dependen de que PubMed y
ClinicalTrials.gov sigan devolviendo lo mismo.

---

## Reglas de desarrollo

### Estilo de código
- Python 3.11+
- Tipado estático en todas las funciones (`def foo(x: str) -> list[str]:`)
- Pydantic para todos los modelos de datos
- Async/await para llamadas paralelas a agentes (Sprint 2 en adelante)
- Docstrings en español en todos los módulos y funciones públicas

### Convenciones de nombres
- Archivos: `snake_case.py`
- Clases: `PascalCase`
- Funciones y variables: `snake_case`
- Constantes: `UPPER_SNAKE_CASE`
- IDs de agentes: `"01"`, `"02"`, etc. (string, no int)

### Manejo de errores
- Nunca silenciar excepciones con `except: pass`
- Las llamadas a APIs externas siempre en try/except con fallback explícito
- Si una hipótesis no tiene referencia verificable → `evidence_level: "III"`, no descartar

### Seguridad y privacidad
- Los datos clínicos NUNCA se loggean en texto plano
- Anonimizar antes de enviar a APIs externas
- No persistir datos clínicos más allá de la sesión
- API keys SIEMPRE desde `.env`, nunca hardcodeadas

### Testing
- Cada módulo nuevo requiere su test en `tests/`
- Caso de prueba base: neuropatía axonal sensitivomotora, paciente masculino 42 años

---

## Variables de entorno requeridas

```bash
# Modelo de IA activo
GROQ_API_KEY=           # Groq (gpt-oss) — obligatorio hoy

# Modelos futuros (cuando se tengan créditos)
ANTHROPIC_API_KEY=      # Claude — Agentes 01, 04, 06
OPENAI_API_KEY=         # GPT-4o — Agente 02
GOOGLE_API_KEY=         # Gemini Pro — Agente 03

# APIs científicas
PUBMED_API_KEY=         # Opcional, aumenta rate limit
ORPHANET_API_KEY=       # Opcional: la API responde sin credencial (medido el
                        # 2026-09-15, 10 de 10 llamadas). Si está definida se
                        # manda en el header apiKey; si no, el cliente manda un
                        # valor por defecto que el servicio acepta.

# RAG — embeddings (opcional)
NEXUS_EMBEDDING_MODEL=  # Sobreescribe el modelo de embeddings del RAG.
                        # Default: NeuML/pubmedbert-base-embeddings (768 dims).
                        # Requiere sentence-transformers (arrastra torch).
                        # Sin esa dependencia el RAG cae a all-MiniLM-L6-v2
                        # y avisa por stderr — funciona, con dominio general.

# Control de costos (Sprint 4, opcional)
NEXUS_MOCK_LLM=          # Apagada por defecto. 1/true la activa: el pipeline
                        # usa respuestas grabadas en vez de llamar a Groq, sin
                        # tocar la red. Sin GROQ_API_KEY y sin esto activo, el
                        # análisis falla con un error claro (nunca cae en
                        # silencio a datos grabados).

# Servidor
ENVIRONMENT=development
MAX_FILE_SIZE_MB=50
SESSION_TTL_MINUTES=60  # TTL de la sesión de cuenta — en uso desde Sprint 4

# Seguridad (Sprint 4 — registro de médicos)
SECRET_KEY=              # Firma la cookie de sesión (HMAC). Obligatoria: sin
                         # ella, backend/auth/sesiones.py levanta
                         # SecretKeyNoConfigurada en el primer login.
ALLOWED_ORIGINS=http://localhost:3000  # Lista blanca para CORS y para la
                         # validación de Origin/Referer (mitigación CSRF) en
                         # todo endpoint que cambia estado.

# Persistencia de cuentas (Sprint 4)
NEXUS_DB_PATH=./data/nexus.db  # Cuentas, sesiones y auditoría (SQLite).
                         # Gitignoreado, se regenera con create_all().
PROVINCIAL_LICENSE_SEARCH_URL=  # Enlace al buscador de matrícula de la
                         # jurisdicción provincial, mostrado al admin en
                         # /admin/pendientes. Puede quedar sin definir (el de
                         # Córdoba está roto al momento de este cambio). El
                         # Buscador Nacional REFEPS no es configurable.
```

---

## Documentación de referencia

- **Ver `.claude/traspaso.md` para retomar el trabajo**: modo orquestador con OpenSpec,
  decisiones tomadas el 2026-09-15, pendientes en orden y cómo levantar la demo
- Ver `.claude/architecture.md` para el flujo detallado del pipeline
- Ver `.claude/backlog.md` para el estado actual del Trello y próximas tareas
- Ver `.claude/stack.md` para las decisiones tecnológicas y sus justificaciones
- Trello del equipo: https://trello.com/b/kdXM36sU
- Repositorio: https://github.com/facu087/tesis-iresm
