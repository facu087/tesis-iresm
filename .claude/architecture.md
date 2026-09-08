# NEXUS — Arquitectura del Sistema

## Flujo completo del pipeline

```
Documentos clínicos (PDF / imágenes)
            │
            ▼
    ┌───────────────────┐
    │  Módulo de Ingesta │
    │  extractor.py      │  PDF nativo → pdfplumber
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
              │ ClinicalCase estructurado
              │
     ┌────────┴────────┐
     │   Motor RAG      │  rag/retriever.py
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

> Todos los modelos son **Pydantic `BaseModel`** (no `dataclass`) y están nombrados
> en inglés, siguiendo la convención del código. Viven en `backend/models/`.

### ClinicalCase — `backend/models/case.py`
```python
class ClinicalCase(BaseModel):
    raw_text: str                               # texto clínico original (ya anonimizado)
    pico: PICOSynthesis | None = None           # se completa tras el análisis PICO
    biomarkers: BiomarkerProfile | None = None  # se completa tras la extracción
```

### PICOSynthesis — `backend/models/case.py`
Población / Intervención / Comparación / Outcome. Es un modelo completo,
no un string: lo construye `backend/pipeline/pico.py`.

```python
class PICOSynthesis(BaseModel):
    # P — Población
    patient_profile: str          # descripción demográfica y clínica
    chief_complaint: str          # motivo de consulta principal
    condition_en: str = ""        # condición en inglés médico, para APIs externas
    relevant_history: list[str]   # antecedentes familiares y personales
    negative_findings: list[str]  # estudios negativos (clave para el diferencial)
    disease_duration: str         # tiempo de evolución

    # I — Intervención / Exposición
    current_treatments: list[str]
    procedures_done: list[str]    # EMG, LCR, biopsias, etc.

    # C — Comparación
    comparison: str               # contexto de comparación o "No aplica"

    # O — Outcome
    primary_outcome: str
    secondary_outcomes: list[str]

    # Extras extraídos del texto
    biomarkers: list[str]
    genetic_findings: list[str]

    clinical_narrative: str       # narrativa final que se pasa a los agentes
```

### BiomarkerProfile — `backend/models/biomarkers.py`
Reemplaza a los campos planos `biomarcadores` / `historial_terapeutico`
del diseño original. Lo construye `backend/ingestion/biomarker_extractor.py`.

```python
class BiomarkerProfile(BaseModel):
    genes: list[str] = []              # ej: TTR, PMP22
    genetic_variants: list[str] = []   # ej: p.Val30Met, c.148G>A
    antibodies: list[str] = []         # ej: anti-Hu, anti-gangliósido GM1
    lab_biomarkers: list[str] = []     # marcadores séricos/LCR
    pathways: list[str] = []           # diagnósticos/síndromes mencionados o descartados
    drugs: list[str] = []              # fármacos (nombre INN) — historial terapéutico
    procedures: list[str] = []
    surgeries: list[str] = []

    def is_empty(self) -> bool: ...
    def summary(self) -> str: ...      # resumen compacto para logs y debugging
```

### Hypothesis — `backend/models/hypothesis.py`
```python
class Priority(str, Enum):
    HIGH = "HIGH"; MEDIUM = "MEDIUM"; LOW = "LOW"


class EvidenceLevel(str, Enum):
    I = "I"      # revisiones sistemáticas / meta-análisis / RCTs
    II = "II"    # estudios de cohorte / caso-control
    III = "III"  # series de casos / opinión de expertos / especulativo


class Source(BaseModel):
    pmid: str | None = None
    title: str
    journal: str | None = None
    year: int | None = None
    url: str | None = None


class Hypothesis(BaseModel):
    text: str
    priority: Priority
    evidence_level: EvidenceLevel
    rationale: str                # razonamiento explícito, por hipótesis
    sources: list[Source] = []    # varias referencias, no una sola
```

### AgentOutput, Critique, DebateRound, Report — `backend/models/report.py`
```python
class AgentOutput(BaseModel):
    agent_id: str                 # "01", "03", … (string, no int)
    agent_name: str
    hypotheses: list[Hypothesis]
    raw_response: str | None = None


class Critique(BaseModel):
    """Crítica de un agente sobre la hipótesis de otro (Ronda 2)."""
    from_agent_id: str
    from_agent_name: str
    target_agent_id: str
    target_hypothesis: str        # texto de la hipótesis criticada
    critique_text: str
    severity: str                 # "HIGH" | "MEDIUM" | "LOW"
    alternative: str | None = None


class DebateRound(BaseModel):
    round_number: int
    agent_outputs: list[AgentOutput] = []  # hipótesis revisadas (Rondas 3–4)
    critiques: list[Critique] = []         # críticas emitidas (Ronda 2)


class Report(BaseModel):
    """Salida interna del motor de debate (Rondas 1–4)."""
    case_summary: str
    hypotheses: list[Hypothesis] = []
    agent_outputs: list[AgentOutput] = []  # outputs de Ronda 1
    debate_rounds: list[DebateRound] = []  # Rondas 2–4
    divergences: list[str] = []
    sources_summary: dict[str, int] = {}
```

### ClinicalTrial — `backend/models/trial.py`
```python
class ClinicalTrial(BaseModel):
    nct_id: str                   # ej: "NCT04123456"
    title: str
    status: str                   # RECRUITING, ACTIVE_NOT_RECRUITING, …
    brief_summary: str
    conditions: list[str] = []
    phase: str | None = None      # PHASE1…PHASE4, NA
    sponsor: str | None = None
    start_date: str | None = None
    completion_date: str | None = None
    eligibility_criteria: str | None = None
    min_age: str | None = None
    max_age: str | None = None
    sex: str | None = None        # ALL | MALE | FEMALE
    locations: list[str] = []
    url: str = ""

    def summary_line(self) -> str: ...
```

### StructuredReport — `backend/api/schemas.py`
Contrato de **exportación**: lo consume el frontend y el generador de PDF.
Lo ensambla `backend/pipeline/report_builder.build_export()`, que es
el módulo que el Agente 06 (Sintetizador) va a reemplazar sin cambiar
este contrato JSON.

```python
class StructuredReport(BaseModel):
    metadata: ReportMetadata            # incluye el disclaimer obligatorio
    case_summary: CaseSummarySection
    hypotheses: list[RankedHypothesis]  # ordenadas por priority, luego evidence_level
    debate_summary: DebateSummary       # rondas, críticas, divergencias, consenso
    clinical_trials: list[ClinicalTrial]
    bibliography: list[Source]          # fuentes únicas, ordenadas por PMID
```

`RankedHypothesis` agrega `rank` y `supporting_agents` sobre `Hypothesis`.
La atribución por agente **no** se guarda en `Hypothesis`: se reconstruye en
`report_builder._rank_hypotheses()` cruzando el texto de la hipótesis contra
los `AgentOutput` de Ronda 1 y de la última ronda del debate.

---

## Diferencias con el diseño original (y qué falta)

El diseño inicial de esta arquitectura describía cuatro dataclasses en español
(`CasoClinico`, `Hipotesis`, `OutputAgente`, `ReporteFinal`). La implementación
divergió en estos puntos:

| Diseño original | Implementación actual | Motivo |
|-----------------|----------------------|--------|
| `dataclass`, nombres en español | Pydantic `BaseModel`, nombres en inglés | Validación automática y serialización JSON para la API |
| `Hipotesis.referencia_pubmed: str` | `Hypothesis.sources: list[Source]` | Una hipótesis puede tener varias referencias |
| `Hipotesis.agente_origen` | `AgentOutput.agent_name` | La atribución es del output, no de la hipótesis |
| `OutputAgente.razonamiento` (por agente) | `Hypothesis.rationale` (por hipótesis) | Razonamiento más granular |
| (no existía) | `Hypothesis.priority` | Permite ordenar el reporte sin depender solo del nivel EBM |
| `OutputAgente.ronda: int` | `DebateRound.round_number` | La ronda modela el conjunto, no cada output |
| `CasoClinico.sintesis_pico: str` | `ClinicalCase.pico: PICOSynthesis` | PICO es un modelo estructurado, no texto libre |
| `CasoClinico.biomarcadores: list[str]` | `ClinicalCase.biomarkers: BiomarkerProfile` | Los biomarcadores se clasifican por tipo |
| `ReporteFinal.ensayos_clinicos` | `build_export(trials=...)` | Los ensayos entran en la exportación, no en el `Report` interno |
| `ReporteFinal.resumen_ejecutivo` | `Report.case_summary` | Renombrado |

### Pendiente — depende del Agente 04 (Árbitro Verificador)

Dos elementos del diseño original **todavía no existen en el código**, y son
justamente los que introduce el árbitro:

1. **`Hypothesis.estado`** (`"pendiente"` | `"verificada"` | `"descartada"` |
   `"especulativa"`). Hoy no hay campo de estado: toda hipótesis generada llega
   al reporte. El árbitro necesita este campo para registrar el resultado de la
   verificación contra PubMed.

2. **La separación `hipotesis_verificadas` / `hipotesis_especulativas`** en el
   reporte. Hoy `Report.hypotheses` y `StructuredReport.hypotheses` son una
   lista única, ordenada por prioridad y nivel de evidencia, sin distinguir
   qué se verificó bibliográficamente.

> Definir estos dos puntos es prerrequisito de las tareas 9 y 11 del Sprint 4
> (ver `.claude/backlog.md`). Cambiar `Hypothesis` impacta a `report_builder.py`,
> `pdf_exporter.py`, `api/schemas.py` y a los tipos del frontend
> (`frontend/src/lib/types.ts`).

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
