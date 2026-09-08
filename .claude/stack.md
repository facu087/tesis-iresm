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
| 01, 04, 06 | Claude Opus | Groq `gpt-oss-120b` | Mayor razonamiento clínico, mejor manejo de textos largos |
| 02 | GPT-4o | Groq `gpt-oss-120b` | Fortaleza en análisis genómico y biológico molecular |
| 03 | Gemini Pro | Groq `gpt-oss-120b` | Capacidad multimodal para imágenes médicas (futuro) |
| Literatura | Perplexity Sonar Pro | — | Acceso en tiempo real a literatura reciente |

**Decisión clave:** en el prototipo todos los agentes corren sobre Groq
(`openai/gpt-oss-120b`) para no depender de APIs pagas durante el desarrollo.
La columna de producción es la arquitectura de destino.

Cambiar el **modelo** de un agente = cambiar `MODEL` en su clase. Cambiar el
**proveedor** = agregar despacho por proveedor en `BaseAgent._call_llm()`, que
hoy instancia el cliente de Groq directamente.

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
| Embeddings | sentence-transformers | Gratuito, sin API key requerida; corre local sin GPU |
| Modelo base | `NeuML/pubmedbert-base-embeddings` (768 dims) | PubMedBERT afinado para embeddings de oraciones. Elegido midiendo, no por reputación |
| Modelo de fallback | `all-MiniLM-L6-v2` (384 dims) | Default de ChromaDB. No necesita torch: el RAG sigue andando sin la dependencia |
| Base vectorial (proto) | ChromaDB | Local, simple, ideal para prototipo |

**Por qué no SciBERT.** `allenai/scibert_scivocab_uncased` fue la elección
original —y es el modelo con el dominio correcto—, pero es un modelo de lenguaje
enmascarado, **no** un modelo de embeddings de oraciones. Obtener vectores por
mean-pooling sin fine-tuning contrastivo rinde peor en similitud semántica que
un modelo entrenado para la tarea; es el resultado que motivó Sentence-BERT
(Reimers & Gurevych, 2019). `S-PubMedBert-MS-MARCO` conserva el dominio
biomédico (PubMedBERT) y agrega el entrenamiento de recuperación que falta,
que es la combinación que necesita el RAG.

**Por qué no `S-PubMedBert-MS-MARCO`.** Fue el primer candidato —PubMedBERT
afinado sobre MS MARCO, pensado para recuperación— y se descartó al medirlo: sus
scores quedan comprimidos entre 0.951 y 0.980, una amplitud de 0.029 sobre el
corpus de prueba. Ordena de forma razonable, pero el `relevance_score` que el
retriever expone a los agentes deja de distinguir un artículo central de uno
tangencial, y el umbral de relevancia se vuelve imposible de calibrar. Es el
comportamiento esperable de los modelos entrenados sobre MS MARCO: optimizan el
orden, no la calibración del score.

**Resultado de la comparación** (`scripts/demo_embeddings_comparacion.py`, 8
artículos, 3 queries clínicas, un artículo fuera de dominio como control):

| | `pubmedbert-base-embeddings` | `all-MiniLM-L6-v2` | `S-PubMedBert-MS-MARCO` |
|---|---|---|---|
| Amplitud de scores | 0.218 | 0.235 | **0.029** ❌ |
| Control fuera de dominio en top-5 | no | no | no |
| 2º puesto para la query de herencia | Charcot-Marie-Tooth ✅ | déficit de B12 ❌ | Charcot-Marie-Tooth ✅ |

El desempate fue el segundo criterio: para la query de amiloidosis TTR "con
antecedentes familiares", PubMedBERT ubica segundo a Charcot-Marie-Tooth —la
neuropatía hereditaria por antonomasia— mientras MiniLM ubica déficit de B12,
que no es hereditario. PubMedBERT también trae amiloidosis TTR al top-5 de la
query del caso, donde MiniLM no la trae.

**Limitación medida.** Ningún modelo de embeddings maneja la negación: con la
query del caso, que incluye "negative CMT panel", los tres traen
Charcot-Marie-Tooth entre los primeros puestos. El hallazgo negativo llega al
agente por `negative_findings` de la síntesis PICO, así que el razonamiento
puede corregirlo, pero el recuperador no lo usa para filtrar.

El modelo se cambia con la variable de entorno `NEXUS_EMBEDDING_MODEL` o por
argumento del script de comparación, sin tocar código.
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
