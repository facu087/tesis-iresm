# NEXUS — Stack Tecnológico y Decisiones de Diseño

## Criterios de selección

Las decisiones tecnológicas se guiaron por tres criterios:
1. **Agnosticismo de modelo** — poder cambiar el LLM de cada agente sin rediseñar el sistema
2. **Apertura de APIs** — no depender de plataformas cerradas o de pago
3. **Costo razonable** — viable para un prototipo académico (~$20-40/mes en producción)

---

## Modelos de IA

| Agente | Modelo (producción) | Modelo (prototipo) | Justificación |
|--------|--------------------|--------------------|---------------|
| 01, 04, 06 | Claude Opus | Claude Opus | Mayor razonamiento clínico, mejor manejo de textos largos |
| 02 | GPT-4o | Claude Opus | Fortaleza en análisis genómico y biológico molecular |
| 03 | Gemini Pro | Claude Opus | Capacidad multimodal para imágenes médicas (futuro) |
| Literatura | Perplexity Sonar Pro | — | Acceso en tiempo real a literatura reciente |

**Decisión clave:** En el prototipo todos usan Claude Opus para simplificar.
Cambiar el modelo de un agente = cambiar una sola variable en su clase.

---

## Backend

| Componente | Tecnología | Versión | Decisión |
|-----------|-----------|---------|---------|
| Lenguaje | Python | 3.11+ | Ecosistema dominante para IA/ML |
| Framework API | FastAPI | 0.111+ | Async nativo, ideal para orquestación paralela |
| Orquestación | asyncio | stdlib | Paralelo sin overhead — Ronda 1 corre los 3 agentes simultáneo |
| LLM Client | anthropic-sdk | 0.25+ | Cliente oficial Anthropic |
| Extracción PDF | pdfplumber | 0.10+ | PDFs nativos con preservación de estructura |
| OCR | Tesseract | 5.x | OCR gratuito para PDFs escaneados |
| Validación datos | Pydantic v2 | 2.x | Modelos tipados para el reporte final |
| Deploy prototipo | Railway.app | — | Tier gratuito, suficiente para tesis |

---

## RAG (Búsqueda Semántica)

| Componente | Tecnología | Decisión |
|-----------|-----------|---------|
| Embeddings | sentence-transformers | Gratuito, sin API key requerida |
| Modelo base | SciBERT (allenai/scibert_scivocab_uncased) | Pre-entrenado en literatura biomédica |
| Base vectorial (proto) | ChromaDB | Local, simple, ideal para prototipo |
| Base vectorial (prod) | Pinecone / Weaviate | Para entorno de producción escalable |
| Similitud | Coseno (HNSW) | Estándar para búsqueda semántica en texto |

**Por qué RAG y no solo búsqueda por keywords:**
La búsqueda keyword de PubMed puede perder artículos que usan terminología diferente.
RAG encuentra similitud de significado, no solo de palabras exactas.

---

## APIs de Bases de Datos Externas

| API | Costo | Uso en NEXUS | Rate limit |
|-----|-------|--------------|------------|
| PubMed E-utilities (NCBI) | Gratuito | Verificación bibliográfica — Agente 04 y 01 | 3/s sin key, 10/s con key |
| ClinicalTrials.gov API v2 | Gratuito | Búsqueda ensayos activos — Agente 05 | Sin límite publicado |
| Orphanet API | Gratuito (registro) | Enfermedades raras — Agente 05 | Con registro |
| PharmGKB | Gratuito (académico) | Farmacogenómica — Agente 02 | Con registro |
| ClinVar (NCBI) | Gratuito | Variantes genéticas — Agente 02 | Igual que PubMed |

---

## Frontend

| Fase | Tecnología | Decisión |
|------|-----------|---------|
| Prototipo | HTML / CSS / JS nativo | Sin dependencias, deploy inmediato |
| Producción | Next.js | SSR, mejor para integración con FastAPI, decisión del equipo |
| Exportación | ReportLab / WeasyPrint | Generación del reporte final en PDF |
| Exportación Word | python-docx | Reporte en DOCX si el médico lo requiere |

**Nota:** El documento de Etapa 1 menciona React, pero el equipo decidió usar Next.js
para la versión de producción por sus ventajas en SSR y routing.

---

## Decisiones de diseño del sistema

### Agentes stateless
Cada agente no recuerda conversaciones anteriores. El contexto entre rondas
lo gestiona el orquestador, que lo inyecta en cada prompt. Esto simplifica
el sistema y lo hace más predecible.

### Diversidad de modelos por agente
Diferentes modelos tienen sesgos de entrenamiento distintos. Un Agente 02
usando GPT-4o ve el caso desde una perspectiva diferente a Claude, reduciendo
puntos ciegos sistemáticos. En el prototipo se usa Claude para todos, pero la
arquitectura está diseñada para soportar múltiples modelos.

### Árbitro externo al debate
El Agente 04 no vota en el debate. Solo verifica hipótesis contra fuentes
externas. Esto previene el riesgo identificado en la literatura: dos modelos
pueden coincidir en el error. La verificación bibliográfica es el único
criterio de verdad objetivo.

### Criterio de parada por bibliografía, no por consenso
El debate termina cuando todas las hipótesis tienen al menos una referencia
PubMed verificable — no cuando los agentes están de acuerdo. Las divergencias
irresolubles se documentan explícitamente como información valiosa.

---

## Costos estimados del prototipo

| Componente | Costo mensual estimado |
|-----------|----------------------|
| Claude API (llamadas de desarrollo) | ~$10-20 |
| Railway.app (deploy) | ~$5-10 |
| Otras APIs | $0 (todas gratuitas) |
| **Total** | **~$15-30/mes** |
