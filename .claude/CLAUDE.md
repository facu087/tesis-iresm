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
| 3 | Pipeline multi-agente (Sprint 2) | 🔜 En curso |
| 4 | Frontend conectado (Sprint 3) | 📋 Planificada |
| 5 | Árbitro + verificación (Sprint 4) | 📋 Planificada |
| 6 | Validación clínica (Sprint 5) | 📋 Planificada |

### Sprint 1 — Completado ✅
- Setup del repositorio, estructura de carpetas y .env
- Módulo de ingesta: extracción de texto de PDF nativo (pdfplumber)
- Agente 01 (Analista Literatura): prompt + Groq/LLaMA + parseo JSON
- Script de prueba con caso clínico anonimizado (neuropatía axonal, 42 años)

### Sprint 2 — En curso 🔜 (Pipeline básico — Etapa 3)
- [x] Módulo de ingesta: OCR básico para PDFs escaneados (Tesseract)
- [x] Normalización terminológica: nombres INN y unidades de medida
- [x] Síntesis PICO: construcción de narrativa clínica estructurada
- [x] Extracción de biomarcadores y mapeo del historial terapéutico
- [x] Clase base de agentes (interfaz común — BaseAgent ABC)
- [ ] Agente 03 (Consultor Clínico): prompt + llamada Groq + parseo JSON
- [ ] Orquestador: distribución paralela con asyncio (Ronda 1)
- [ ] Motor de debate: Rondas 2–4 (crítica cruzada entre agentes)
- [ ] Cliente ClinicalTrials.gov API v2: búsqueda de ensayos activos

---

## Estructura de carpetas actual

```
tesis-iresm/
├── .claude/
│   ├── CLAUDE.md               ← este archivo
│   ├── architecture.md         ← arquitectura detallada del pipeline
│   ├── backlog.md              ← estado del backlog / Trello
│   └── stack.md                ← decisiones tecnológicas
├── .vscode/
│   ├── extensions.json         ← extensiones recomendadas del equipo
│   └── settings.json           ← configuración compartida
├── backend/
│   ├── agents/
│   │   ├── base_agent.py       ← clase base ABC con interfaz común
│   │   ├── agent_01_literature.py  ← Analista de Literatura (Groq/LLaMA)
│   │   └── __init__.py
│   ├── ingestion/
│   │   ├── extractor.py        ← PDF nativo (pdfplumber) + OCR (Tesseract)
│   │   ├── normalizer.py       ← normalización INN y unidades de medida
│   │   ├── biomarker_extractor.py  ← extracción genes, anticuerpos, fármacos
│   │   └── __init__.py
│   ├── models/
│   │   ├── hypothesis.py       ← Hypothesis, Priority, EvidenceLevel, Source
│   │   ├── report.py           ← AgentOutput, Report
│   │   ├── case.py             ← ClinicalCase, PICOSynthesis
│   │   ├── biomarkers.py       ← BiomarkerProfile
│   │   └── __init__.py
│   ├── pipeline/
│   │   ├── pico.py             ← build() síntesis PICO + format_for_agents()
│   │   └── __init__.py
│   ├── external/               ← clientes APIs científicas (Sprint 4)
│   ├── api/                    ← endpoints FastAPI (Sprint 3)
│   └── requirements.txt
├── scripts/
│   └── poc_test.py             ← script de prueba end-to-end Sprint 1
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

## Modelo de IA actual

> **Groq (LLaMA 3.3 70B)** — reemplaza temporalmente a Claude/Gemini/GPT-4o
> mientras se gestionan créditos en las APIs de pago.
> La arquitectura final usará Claude Opus (agentes 01, 04, 06),
> GPT-4o (agente 02) y Gemini Pro (agente 03).

Constantes disponibles en `base_agent.py`:
- `GROQ_LLAMA = "llama-3.3-70b-versatile"` — modelo principal
- `GROQ_LLAMA_FAST = "llama-3.1-8b-instant"` — tareas simples/rápidas

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
GROQ_API_KEY=           # LLaMA 3.3 via Groq — obligatorio hoy

# Modelos futuros (cuando se tengan créditos)
ANTHROPIC_API_KEY=      # Claude — Agentes 01, 04, 06
OPENAI_API_KEY=         # GPT-4o — Agente 02
GOOGLE_API_KEY=         # Gemini Pro — Agente 03

# APIs científicas
PUBMED_API_KEY=         # Opcional, aumenta rate limit
ORPHANET_API_KEY=       # Requiere registro en orphanet.org

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
