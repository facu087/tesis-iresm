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
- Agente 01 (Analista Literatura): prompt + llamada Claude API + parseo JSON
- Script de prueba con caso clínico anonimizado (neuropatía axonal, 42 años)

### Sprint 2 — En curso 🔜 (Pipeline básico — Etapa 3)
- [ ] Módulo de ingesta: OCR básico para PDFs escaneados (Tesseract)
- [ ] Normalización terminológica: nombres INN y unidades de medida
- [ ] Agente Orquestador: construcción de síntesis PICO con Claude API
- [ ] Extracción de biomarcadores y mapeo del historial terapéutico
- [ ] Clase base de agentes (interfaz común)
- [ ] Agente 03 (Consultor Clínico): prompt + llamada Gemini API + parseo JSON
- [ ] Orquestador: distribución paralela con asyncio (Ronda 1)
- [ ] Motor de debate: Rondas 2–4 (crítica cruzada entre agentes)
- [ ] Cliente ClinicalTrials.gov API v2: búsqueda de ensayos activos

---

## Estructura de carpetas

```
nexus/
├── .claude/
│   ├── CLAUDE.md           ← este archivo
│   ├── architecture.md     ← arquitectura detallada
│   ├── backlog.md          ← estado del backlog / Trello
│   └── stack.md            ← decisiones tecnológicas
├── agents/
│   ├── __init__.py
│   ├── agentes.py          ← los 6 agentes especializados
│   └── orchestrator.py     ← orquestador del pipeline
├── core/
│   ├── __init__.py
│   ├── models.py            ← modelos de datos (dataclasses)
│   ├── ingesta.py           ← extracción y normalización de PDFs
│   └── rag.py               ← motor RAG (embeddings + ChromaDB)
├── tools/
│   ├── __init__.py
│   ├── pubmed.py            ← integración PubMed E-utilities
│   └── clinical_trials.py   ← integración ClinicalTrials.gov API v2
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── anonymizer.py
├── docs/
│   └── caso_ejemplo.pdf
├── tests/
│   ├── test_ingesta.py
│   ├── test_pubmed.py
│   ├── test_rag.py
│   └── test_pipeline.py
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Reglas de desarrollo

### Estilo de código
- Python 3.11+
- Tipado estático en todas las funciones (`def foo(x: str) -> list[str]:`)
- Dataclasses para modelos de datos (ver `core/models.py`)
- Async/await para todas las llamadas a APIs externas
- Docstrings en español en todos los módulos y funciones públicas

### Convenciones de nombres
- Archivos: `snake_case.py`
- Clases: `PascalCase`
- Funciones y variables: `snake_case`
- Constantes: `UPPER_SNAKE_CASE`
- IDs de agentes: `agente_01`, `agente_02`, etc.

### Manejo de errores
- Nunca silenciar excepciones con `except: pass`
- Loggear todos los errores con contexto suficiente para debuggear
- Las llamadas a APIs externas (Claude, PubMed, ClinicalTrials) siempre
  en try/except con fallback explícito
- Si una hipótesis no tiene referencia bibliográfica verificable → estado "especulativa",
  no descartar silenciosamente

### Seguridad y privacidad
- Los datos clínicos NUNCA se loggean en texto plano
- Anonimizar antes de enviar a APIs externas (ver `utils/anonymizer.py`)
- No persistir datos clínicos identificables más allá de la sesión
- La API key de Anthropic y otras claves SIEMPRE desde `.env`, nunca hardcodeadas

### Testing
- Cada módulo nuevo requiere su test en `tests/`
- Los tests de integración con APIs externas usan mocks (no llaman APIs reales)
- El caso de prueba base es: neuropatía axonal, paciente 42 años

---

## Variables de entorno requeridas

```bash
ANTHROPIC_API_KEY=      # Claude API — obligatorio
OPENAI_API_KEY=         # GPT-4o para Agente 02 — opcional en prototipo
GOOGLE_API_KEY=         # Gemini para Agente 03 — opcional en prototipo
NEXUS_MAX_DEBATE_ROUNDS=5
NEXUS_MAX_PUBMED_RESULTS=10
NEXUS_LOG_LEVEL=INFO
```

---

## Documentación de referencia

- Ver `.claude/architecture.md` para el flujo detallado del pipeline
- Ver `.claude/backlog.md` para el estado actual del Trello y próximas tareas
- Ver `.claude/stack.md` para las decisiones tecnológicas y sus justificaciones
- Documentación de la Etapa 1: `docs/NEXUS-Etapa1-v1.pdf`
