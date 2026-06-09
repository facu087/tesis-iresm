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
- Agente 01 (Analista Literatura): prompt + Groq/LLaMA + parseo JSON
- Script de prueba con caso clínico anonimizado (neuropatía axonal, 42 años)

**Sprint 2 — Pipeline básico (Etapa 3)**
- Módulo de ingesta: OCR básico para PDFs escaneados (Tesseract)
- Normalización terminológica: nombres INN y unidades de medida
- Agente Orquestador: construcción de síntesis PICO (Groq/LLaMA)
- Extracción de biomarcadores y mapeo del historial terapéutico
- Clase base de agentes (BaseAgent ABC — interfaz común)
- Agente 03 (Consultor Clínico): prompt + Groq/LLaMA + parseo JSON
- Orquestador: distribución paralela con asyncio (Ronda 1)
- Motor de debate: Rondas 2–4 (crítica cruzada entre agentes)
- Cliente ClinicalTrials.gov API v2: búsqueda de ensayos activos

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

## Sprint 3 — Frontend conectado (Etapa 4) 🔜 EN CURSO

Épicas cubiertas: EP-07, EP-08

| # | Tarea | Estado |
|---|-------|--------|
| 1 | Modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial | ✅ Hecho (Sprint 2) |
| 2 | Endpoint FastAPI: POST /api/analyze | Por hacer |
| 3 | Generación de JSON estructurado con todas las secciones del reporte | Por hacer |
| 4 | Exportación del reporte a PDF (ReportLab) | Por hacer |
| 5 | Setup Next.js + conexión al backend FastAPI | Por hacer |
| 6 | Vista de carga de documentos | Por hacer |
| 7 | Vista de pipeline con animación de progreso en tiempo real | Por hacer |
| 8 | Vista de reporte: hipótesis, ensayos clínicos, divergencias y fuentes | Por hacer |

---

## Sprint 4 — Árbitro y verificación (Etapa 5)

Épicas cubiertas: EP-04, EP-05, EP-06

| # | Tarea |
|---|-------|
| 1 | Setup ChromaDB: colección y embeddings biomédicos |
| 2 | Indexación de artículos PubMed en ChromaDB |
| 3 | Motor RAG: búsqueda semántica y formateo para prompts |
| 4 | Cliente PubMed E-utilities: búsqueda y parseo de resultados |
| 5 | Cliente Orphanet API: búsqueda de enfermedades raras |
| 6 | Cliente PharmGKB: relaciones fármaco-genómicas |
| 7 | Gestión de rate limits y fallbacks en APIs externas |
| 8 | Agente 02 (Especialista Genómica): prompt + llamada GPT-4o + parseo JSON |
| 9 | Agente 04 (Árbitro Verificador): síntesis y verificación bibliográfica externa |
| 10 | Agente 05 (Navegador de Ensayos): búsqueda en ClinicalTrials + Orphanet |
| 11 | Priorización de hipótesis por nivel de evidencia EBM (I, II, III) |

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

## Notas importantes

- El caso de prueba base del proyecto es **neuropatía axonal, paciente de 42 años**
- En producción cada agente usa un modelo distinto; en el prototipo todos usan Groq/LLaMA 3.3 70B
- El frontend definitivo será Next.js, no React (decisión del equipo)
- El tablero tiene una columna **QA** (vacía) para tareas en revisión antes de pasar a Finalizado
