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
- [x] Vista de carga de documentos (frontend/src/app/page.tsx + components/UploadForm.tsx)
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
- [ ] Agente 02 (Especialista Genómica): prompt + llamada LLM + parseo JSON
- [ ] Agente 04 (Árbitro Verificador): verificación bibliográfica de cada hipótesis
- [ ] Agente 05 (Navegador de Ensayos): ClinicalTrials.gov + Orphanet
- [ ] Agente 06 (Sintetizador): reporte final — reemplaza a `pipeline/report_builder.py`
- [ ] Priorización de hipótesis por nivel de evidencia EBM (I, II, III)

> El RAG y el verificador de PMIDs ya corren en el flujo de `POST /api/analyze`:
> el RAG enriquece el contexto de la Ronda 1 (`pipeline/orchestrator.py`,
> `_enrich_context_with_rag`) y la verificación es el paso 7 de `api/router.py`.
> Falta la parte de **síntesis** del Agente 04 y los agentes 02, 05 y 06.

#### Numeración de agentes (canónica)

| ID | Rol | Estado |
|----|-----|--------|
| 01 | Analista de Literatura | ✅ Implementado |
| 02 | Especialista Genómica | 📋 Pendiente |
| 03 | Consultor Clínico | ✅ Implementado |
| 04 | Árbitro Verificador | 📋 Pendiente |
| 05 | Navegador de Ensayos | 📋 Pendiente |
| 06 | Sintetizador | 📋 Pendiente |

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
│   │   ├── agent_03_clinical.py    ← Consultor Clínico (Groq)
│   │   └── __init__.py
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
│   │   ├── trial.py            ← ClinicalTrial
│   │   └── __init__.py
│   ├── pipeline/
│   │   ├── pico.py             ← build() síntesis PICO + format_for_agents()
│   │   ├── orchestrator.py     ← distribución paralela asyncio (Ronda 1)
│   │   ├── debate.py           ← motor de debate adversarial (Rondas 2–4)
│   │   ├── verification.py     ← verificación de PMIDs citados contra PubMed (S4)
│   │   ├── report_builder.py   ← generación de JSON estructurado del reporte
│   │   ├── pdf_exporter.py     ← exportación a PDF con ReportLab
│   │   └── __init__.py
│   ├── external/
│   │   ├── clinical_trials.py  ← cliente ClinicalTrials.gov API v2
│   │   ├── pubmed.py           ← cliente PubMed E-utilities + verificación PMIDs (S4)
│   │   ├── orphanet.py         ← cliente Orphanet: enfermedades raras (S4)
│   │   ├── pharmgkb.py         ← cliente PharmGKB: fármaco-genómica (S4)
│   │   └── rate_limiter.py     ← rate limits y fallbacks para APIs externas (S4)
│   ├── rag/                    ← capa RAG de evidencia (Sprint 4)
│   │   ├── chroma_store.py     ← ChromaDB + embeddings biomédicos
│   │   ├── indexer.py          ← indexación de artículos PubMed en ChromaDB
│   │   ├── retriever.py        ← motor RAG: búsqueda semántica
│   │   └── __init__.py
│   ├── api/
│   │   ├── router.py           ← POST /api/analyze, POST /api/report/pdf
│   │   └── schemas.py          ← schemas Pydantic para request/response
│   ├── main.py                 ← FastAPI app + rutas + CORS
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            ← vista de carga de documentos
│   │   │   ├── analyzing/page.tsx  ← vista de pipeline con progreso en tiempo real
│   │   │   └── report/page.tsx     ← vista de reporte (5 tabs)
│   │   ├── components/
│   │   │   └── UploadForm.tsx      ← formulario de carga PDF/texto
│   │   └── lib/
│   │       ├── api.ts              ← cliente HTTP al backend FastAPI
│   │       ├── types.ts            ← tipos TypeScript del reporte
│   │       └── inputStore.ts       ← estado compartido entre vistas
│   ├── next.config.ts
│   └── package.json
├── scripts/
│   ├── poc_test.py             ← script de prueba end-to-end Sprint 1
│   └── demo_*.py               ← scripts de verificación por tarea (evidencia Trello):
│       │                          extraccion, ocr, normalizacion, biomarcadores, pico,
│       │                          base_agent, agente01, agente03, orquestador,
│       └─                         clinical_trials, debate, pdf
├── tests/
│   ├── test_ingesta.py
│   ├── test_normalizer.py
│   ├── test_pico.py
│   └── test_biomarkers.py
├── output/                     ← JSONs generados (ignorado por git)
├── .env.example
├── .gitignore
└── README.md
```

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

Constantes disponibles en `base_agent.py`:
- `GROQ_MAIN = "openai/gpt-oss-120b"` — modelo principal (agentes 01, 03, 06)
- `GROQ_FAST = "openai/gpt-oss-20b"` — tareas simples/rápidas

> ⚠ Groq dio de baja los LLaMA 3.x (`llama-3.3-70b-versatile` y
> `llama-3.1-8b-instant`): la API devuelve 404 `model_not_found`. Se reemplazaron
> por los `gpt-oss` en el commit `5174330`. Las constantes anteriores
> —`GROQ_LLAMA` y `GROQ_LLAMA_FAST`— **ya no existen**.

### Swap de proveedor

`MODEL` en la definición de cada agente elige **qué modelo de Groq** usar, no el
proveedor: `BaseAgent._call_llm()` instancia el cliente de Groq directamente
(`backend/agents/base_agent.py`). El swap a Claude / GPT-4o / Gemini se hace en
ese único método, agregando despacho por proveedor.

Vale tenerlo en cuenta al escribir los agentes 02, 04, 05 y 06: si cada uno
asume la firma de Groq en lugar de delegar en `_call_llm()`, el swap se
multiplica por la cantidad de agentes.

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
ORPHANET_API_KEY=       # Requiere registro en orphanet.org

# RAG — embeddings (opcional)
NEXUS_EMBEDDING_MODEL=  # Sobreescribe el modelo de embeddings del RAG.
                        # Default: NeuML/pubmedbert-base-embeddings (768 dims).
                        # Requiere sentence-transformers (arrastra torch).
                        # Sin esa dependencia el RAG cae a all-MiniLM-L6-v2
                        # y avisa por stderr — funciona, con dominio general.

# Servidor
ENVIRONMENT=development
MAX_FILE_SIZE_MB=50
SESSION_TTL_MINUTES=60
```

---

## Documentación de referencia

- Ver `.claude/architecture.md` para el flujo detallado del pipeline
- Ver `.claude/backlog.md` para el estado actual del Trello y próximas tareas
- Ver `.claude/stack.md` para las decisiones tecnológicas y sus justificaciones
- Trello del equipo: https://trello.com/b/kdXM36sU
- Repositorio: https://github.com/facu087/tesis-iresm
