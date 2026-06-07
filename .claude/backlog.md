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

- Setup del repositorio, estructura de carpetas y .env
- Módulo de ingesta: extracción de texto de PDF nativo (pdfplumber)
- Agente 01 (Analista Literatura): prompt + llamada Claude API + parseo JSON
- Script de prueba con caso clínico anonimizado (neuropatía axonal, 42 años)

---

## Sprint 1 — PoC (Etapa 2) ✅ COMPLETO

Todas las tareas fueron movidas a **Finalizado**.
Caso de prueba usado: **neuropatía axonal, paciente de 42 años**.

---

## Sprint 2 — Pipeline básico (Etapa 3) 🔜 EN CURSO

Épicas cubiertas: EP-01, EP-02, EP-03, EP-05

| # | Tarea | Épica | Estado |
|---|-------|-------|--------|
| 1 | Módulo de ingesta: OCR básico para PDFs escaneados (Tesseract) | EP-01 | Por hacer |
| 2 | Normalización terminológica: nombres INN y unidades de medida | EP-01 | Por hacer |
| 3 | Agente Orquestador: construcción de síntesis PICO con Claude API | EP-02 | Por hacer |
| 4 | Extracción de biomarcadores y mapeo del historial terapéutico | EP-02 | Por hacer |
| 5 | Clase base de agentes (interfaz común) | EP-03 | Por hacer |
| 6 | Agente 03 (Consultor Clínico): prompt + llamada Gemini API + parseo JSON | EP-03 | Por hacer |
| 7 | Orquestador: distribución paralela con asyncio (Ronda 1) | EP-03 | Por hacer |
| 8 | Motor de debate: Rondas 2–4 (crítica cruzada entre agentes) | EP-03 | Por hacer |
| 9 | Cliente ClinicalTrials.gov API v2: búsqueda de ensayos activos | EP-05 | Por hacer |

---

## Sprint 3 — Frontend conectado (Etapa 4)

Épicas cubiertas: EP-07, EP-08

| # | Tarea |
|---|-------|
| 1 | Modelos Pydantic: Report, Hypothesis, ClinicalCase, ClinicalTrial |
| 2 | Endpoint FastAPI: POST /api/analyze |
| 3 | Generación de JSON estructurado con todas las secciones del reporte |
| 4 | Exportación del reporte a PDF (ReportLab o WeasyPrint) |
| 5 | Setup Next.js + conexión al backend FastAPI |
| 6 | Vista de carga de documentos |
| 7 | Vista de pipeline con animación de progreso en tiempo real |
| 8 | Vista de reporte: hipótesis, ensayos clínicos, divergencias y fuentes |

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
- En producción cada agente usa un modelo distinto; en el prototipo todos usan Claude Opus
- El frontend definitivo será Next.js, no React (decisión del equipo)
- El tablero tiene una columna **QA** (vacía) para tareas en revisión antes de pasar a Finalizado
