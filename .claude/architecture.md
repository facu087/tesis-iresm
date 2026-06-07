# NEXUS — Arquitectura del Sistema

## Flujo completo del pipeline

```
Documentos clínicos (PDF / imágenes)
            │
            ▼
    ┌───────────────────┐
    │  Módulo de Ingesta │
    │  ingesta.py        │  PDF nativo → pdfplumber
    │                    │  PDF escaneado → Tesseract OCR
    └─────────┬──────────┘
              │ texto normalizado
              ▼
    ┌───────────────────┐
    │  Agente Orquestador│
    │  orchestrator.py   │  Construye síntesis PICO
    │                    │  Extrae biomarcadores
    │                    │  Mapea historial terapéutico
    └─────────┬──────────┘
              │ CasoClinico estructurado
              │
     ┌────────┴────────┐
     │   Motor RAG      │  rag.py
     │   SciBERT +      │  Indexa literatura en ChromaDB
     │   ChromaDB       │  Busca por similitud semántica
     └────────┬─────────┘
              │ literatura relevante
              ▼
    ┌──────────────────────────────────────────┐
    │            PIPELINE MULTI-AGENTE         │
    │                                          │
    │  RONDA 1 — Análisis independiente        │
    │  (asyncio.gather — paralelo)             │
    │                                          │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
    │  │ Agente 01│ │ Agente 02│ │ Agente 03│ │
    │  │Literatura│ │ Genómica │ │ Clínico  │ │
    │  │  Claude  │ │  GPT-4o  │ │  Gemini  │ │
    │  └──────────┘ └──────────┘ └──────────┘ │
    │                                          │
    │  RONDAS 2-4 — Debate adversarial         │
    │  Cada agente recibe outputs de los demás │
    │  y genera críticas específicas           │
    │                                          │
    │  RONDA 5 — Síntesis del árbitro          │
    └──────────────────┬───────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Agente 04     │
              │   Árbitro       │  Verifica cada hipótesis
              │   Verificador   │  contra PubMed
              │   Claude Opus   │  Clasifica nivel evidencia
              └────────┬────────┘  Descarta sin respaldo
                       │
                       ▼
              ┌─────────────────┐
              │   Agente 05     │
              │   Navegador de  │  ClinicalTrials.gov API v2
              │   Ensayos       │  Orphanet API
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Agente 06     │
              │   Sintetizador  │  Genera reporte final
              │   Claude Opus   │  PDF / DOCX para el médico
              └─────────────────┘
```

---

## Modelos de datos principales

### CasoClinico
```python
@dataclass
class CasoClinico:
    texto_raw: str                        # texto extraído del PDF
    sintesis_pico: Optional[str] = None   # construida por el orquestador
    biomarcadores: list[str]              # extraídos del texto
    historial_terapeutico: list[str]      # extraído del texto
```

### Hipotesis
```python
@dataclass
class Hipotesis:
    descripcion: str
    nivel_evidencia: str          # "I", "II" o "III" (jerarquía EBM)
    agente_origen: str            # qué agente la generó
    referencia_pubmed: str | None # PubMed ID — obligatorio para reporte final
    titulo_paper: str | None
    url_paper: str | None
    estado: str                   # "pendiente" | "verificada" | "descartada" | "especulativa"
```

### OutputAgente
```python
@dataclass
class OutputAgente:
    agente_id: str        # "agente_01", "agente_02", etc.
    rol: str
    hipotesis: list[Hipotesis]
    razonamiento: str     # cadena de razonamiento explícita
    ronda: int            # en qué ronda del debate se generó
```

### ReporteFinal
```python
@dataclass
class ReporteFinal:
    hipotesis_verificadas: list[Hipotesis]
    hipotesis_especulativas: list[Hipotesis]
    ensayos_clinicos: list[EnsayoClinico]
    divergencias: list[str]     # desacuerdos irresolubles documentados
    resumen_ejecutivo: str
```

---

## Especificación de los 6 agentes

| ID | Rol | Modelo (prod) | Modelo (proto) | Herramientas |
|----|-----|---------------|----------------|--------------|
| agente_01 | Analista de Literatura | Claude Opus | Claude Opus | PubMed API, RAG |
| agente_02 | Especialista Genómica | GPT-4o | Claude Opus | PharmGKB, ClinVar |
| agente_03 | Consultor Clínico | Gemini Pro | Claude Opus | NCCN Guidelines |
| agente_04 | Árbitro Verificador | Claude Opus | Claude Opus | PubMed, ESMO, EMA |
| agente_05 | Navegador de Ensayos | Dedicado | Claude Opus | ClinicalTrials.gov, Orphanet |
| agente_06 | Sintetizador | Claude Opus | Claude Opus | ReportLab, python-docx |

> En el prototipo todos los agentes usan Claude Opus para simplificar la implementación.
> El modelo de cada agente se cambia con una sola variable en su definición.

---

## Protocolo del debate adversarial

```
Ronda 1:  Cada agente analiza el caso de forma AISLADA
          → sin ver los outputs de los demás
          → resultado: 3 hipótesis por agente

Ronda 2:  Cada agente recibe los outputs de los otros
          → genera críticas específicas
          → identifica inconsistencias y sobre-estimaciones

Rondas 3-4: Los agentes responden a las críticas
          → ajustan o defienden sus hipótesis
          → con argumentación bibliográfica

Ronda 5:  El Árbitro recibe todos los outputs
          → resuelve divergencias con soporte bibliográfico
          → documenta las irresolubles
          → construye el consenso preliminar

Verificación final:
          → Árbitro cruza cada hipótesis contra PubMed
          → Sin soporte = descartada o especulativa
          → Con soporte = verificada (incluida en reporte)
```

### Criterio de parada
El debate finaliza cuando **todas las hipótesis del consenso tienen al menos
una referencia bibliográfica verificable**, independientemente de si los
agentes están de acuerdo entre sí. Las divergencias irresolubles se documentan.

---

## APIs externas

### PubMed E-utilities (NCBI)
- Base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- Endpoints usados: `esearch.fcgi`, `efetch.fcgi`
- Autenticación: ninguna (gratuito)
- Rate limit: 3 requests/segundo sin API key, 10/segundo con key
- Retorno: XML parseado con `xml.etree.ElementTree`

### ClinicalTrials.gov API v2
- Base URL: `https://clinicaltrials.gov/api/v2/studies`
- Filtro clave: `filter.overallStatus=RECRUITING`
- Autenticación: ninguna (público)
- Retorno: JSON

### Orphanet API
- Requiere registro gratuito
- Usado por Agente 05 para enfermedades raras

### PharmGKB
- Gratuito para uso académico
- Usado por Agente 02 para relaciones fármaco-genómicas
