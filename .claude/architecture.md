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
     │   PubMedBERT +   │  Indexa literatura en ChromaDB
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
              └────────┬────────┘  Sin respaldo → especulativa (III)
                       │
                       ▼
              ┌─────────────────┐
              │   Agente 05     │  ClinicalTrials.gov API v2
              │   Navegador de  │  (RECRUITING + NOT_YET_RECRUITING)
              │   Ensayos       │  Orphanet API (coincidencia exacta)
              └────────┬────────┘  Compatibilidad orientativa, nunca excluye
                       │
                       ▼
              ┌─────────────────┐
              │   Agente 06     │
              │   Sintetizador  │  Genera reporte final
              │   Claude Opus   │  PDF / DOCX para el médico
              └─────────────────┘
```

> **Estado real del flujo (Sprint 4).** El Agente 04 todavía no existe como agente:
> su mitad de verificación corre en `pipeline/verification.py`. Hasta que exista,
> el Agente 05 **no** va después del Árbitro sino **en paralelo con la verificación**
> (`asyncio.gather` en `api/router.py`): ambos dependen solo del reporte final del
> debate y usan APIs distintas (ClinicalTrials.gov/Orphanet vs. PubMed). Cuando el
> Árbitro exista, el orden pasa a ser `árbitro → navigate(consenso)` cambiando solo
> el adaptador de entrada (`pipeline/trial_matching.build_navigation_input`), no el
> agente. El Agente 06 sigue siendo `pipeline/report_builder.py` + `pdf_exporter.py`.

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
    genomic_context: GenomicContext | None = None  # se completa antes de la Ronda 1
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

### GenomicContext — `backend/models/genomics.py`
Perfil genómico determinístico que se construye antes de la Ronda 1 (sin LLM) y se
pasa como contexto al Agente 02. Lo construye `backend/pipeline/genomic_context.py`.

```python
class GenomicContext(BaseModel):
    variants: list[str] = []              # variantes confirmadas (ej: p.Val30Met)
    genetic_findings: list[str] = []      # hallazgos textuales del caso
    genes: list[str] = []                 # genes saneados (sin acrónimos clínicos)
    discarded_symbols: frozenset[str] = frozenset()  # acrónimos filtrados
    negative_genetic_studies: list[str] = []  # paneles negativos
    annotations: list[PharmGKBAnnotation] = []  # relaciones fármaco-gen (PharmGKB)
    sources: list[GenomicSource] = []     # estado de cada fuente consultada

    def to_prompt_block(self) -> str: ... # formatea el contexto para el prompt
    def is_orientation_mode(self) -> bool: ...  # True si no hay variantes confirmadas
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

    # Agente 05 — aditivos, con default: un JSON previo valida igual
    compatibility: str = "sin_evaluar"        # alta | media | baja | sin_evaluar
    compatibility_rationale: str | None = None
    criteria_to_verify: list[str] = []        # qué debe verificar el médico
    related_hypotheses: list[str] = []        # hipótesis cuyas consultas lo trajeron
    matched_terms: list[str] = []             # términos en inglés que lo encontraron

    def summary_line(self) -> str: ...
```

El mismo módulo define el contrato del Agente 05: `TrialCandidate`,
`PatientDemographics`, `TrialNavigationInput`, `TrialNavigationResult`,
`RareDiseaseMatch` y `TrialSearchSummary` (`estado_clinicaltrials`,
`estado_orphanet`, `planificacion`, `evaluacion`, `terminos_consultados`,
`encontrados`, `excluidos_por_edad`, `excluidos_por_sexo`,
`evaluaciones_descartadas`).

**Orden de los ensayos** (`pipeline/trial_matching.sort_trials`):
compatibilidad → sede en Argentina → ya reclutando → orden de descubrimiento.
La sede y el estado de reclutamiento ordenan, **nunca** excluyen; la ubicación
del paciente no se usa como criterio.

### StructuredReport — `backend/api/schemas.py`
Contrato de **exportación**: lo consume el frontend y el generador de PDF.
Lo ensambla `backend/pipeline/report_builder.build_export()`, que es
el módulo que el Agente 06 (Sintetizador) va a reemplazar sin cambiar
este contrato JSON.

```python
class StructuredReport(BaseModel):
    metadata: ReportMetadata            # incluye el disclaimer obligatorio
    case_summary: CaseSummarySection
    hypotheses: list[RankedHypothesis]  # estado → nivel efectivo → priority (pipeline/evidence.py)
    debate_summary: DebateSummary       # rondas, críticas, divergencias, consenso
    clinical_trials: list[ClinicalTrial]  # orden del Agente 05, con compatibilidad
    bibliography: list[Source]          # fuentes únicas, ordenadas por PMID
    verification: VerificationSummary   # recuento de la verificación (Agente 04)
    # Agente 05 — aditivos
    rare_diseases: list[RareDiseaseMatch] = []
    trial_search: TrialSearchSummary | None = None  # None = reporte previo al 05
```

`trial_search` es **nullable** a propósito, a diferencia de `verification`: nulo
significa "reporte anterior al Agente 05", y es la señal que usan el frontend y el
PDF para renderizar la sección de ensayos como antes. Un default con estados en
`sin_consulta` haría que un reporte viejo con ensayos afirme que no se consultó nada.

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

### Estado de la hipótesis y nivel de evidencia — resuelto (tarea 11, Sprint 4)

Los dos elementos del diseño original que figuraban como pendientes se resolvieron
en `backend/pipeline/evidence.py` (cambio OpenSpec `priorizacion-evidencia-ebm`,
archivado en `openspec/changes/archive/2026-09-15-priorizacion-evidencia-ebm/`,
spec vigente en `openspec/specs/clasificacion-evidencia-ebm/`):

1. **Estado de la hipótesis**: es **derivado**, no un campo persistido en
   `Hypothesis` (evita estado desactualizado cuando el Árbitro re-verifique).
   `classify_hypothesis()` lo calcula de los veredictos de `verification.py` y viaja
   en `RankedHypothesis.status`: `"respaldada"` (≥1 fuente verificada),
   `"pendiente"` (la verificación no pudo concluir, p. ej. PubMed caído) o
   `"especulativa"`. **No existe "descartada"**: por regla del proyecto una
   hipótesis sin referencia verificable queda en nivel III y se muestra.

2. **Separación verificadas / especulativas**: `StructuredReport.hypotheses` sigue
   siendo una lista única, pero ordenada con el estado como primer criterio, así que
   cada grupo queda contiguo; la vista de reporte y el PDF la agrupan por `status`.

**Nivel efectivo.** `evidence_level` exportado = nivel declarado por el agente,
topeado por la mejor fuente verificada según los tipos de publicación de PubMed
(misma consulta `esummary` de la verificación). Nunca sube; sin fuente verificada, III.
El declarado queda en `declared_evidence_level` y la explicación en `evidence_note`.

| Tope | Tipos de publicación (PubMed) |
|------|-------------------------------|
| I | Meta-Analysis, Network Meta-Analysis, Systematic Review, Randomized Controlled Trial |
| II | Observational Study, Clinical Trial (y fases), Controlled/Pragmatic Clinical Trial, Comparative Study, Multicenter Study, Practice Guideline, Guideline, **o ningún tipo reconocido** (p. ej. solo Journal Article) |
| III | Case Reports, Review, Scoping Review, Letter, Editorial, Comment, News, Consensus Development Conference; **publicación retractada** (anula cualquier otro tipo) |

**Orden:** estado → nivel efectivo → prioridad → fuentes verificadas → orden original.

> **Limitación documentada:** el tipo `Systematic Review` existe en PubMed desde 2019.
> Las revisiones sistemáticas anteriores indexadas solo como `Review` topean en III,
> como una revisión narrativa. No se corrige con heurísticas de título ni abstract.

---

## Especificación de los 6 agentes

| ID | Rol | Modelo (prod) | Modelo (proto) | Herramientas |
|----|-----|---------------|----------------|--------------|
| agente_01 | Analista de Literatura | Claude Opus | Groq `gpt-oss-120b` | PubMed API, RAG |
| agente_02 | Especialista Genómica ✅ | GPT-4o | Groq `gpt-oss-120b` | PharmGKB; ClinVar pendiente |
| agente_03 | Consultor Clínico | Gemini Pro | Groq `gpt-oss-120b` | NCCN Guidelines |
| agente_04 | Árbitro Verificador | Claude Opus | Groq `gpt-oss-120b` | PubMed, ESMO, EMA |
| agente_05 | Navegador de Ensayos ✅ | Dedicado | Groq `gpt-oss-120b` | ClinicalTrials.gov, Orphanet |
| agente_06 | Sintetizador | Claude Opus | Groq `gpt-oss-120b` | ReportLab, python-docx |

> En el prototipo todos los agentes corren sobre Groq (`openai/gpt-oss-120b`,
> constante `GROQ_MAIN`) mientras se gestionan créditos en las APIs de pago.
> La columna de producción es la arquitectura de destino, no lo que corre hoy.
>
> `MODEL` en la definición de cada agente elige qué modelo de Groq usar. El
> **proveedor** está fijo en `BaseAgent._call_llm()`, que instancia el cliente de
> Groq directamente: el swap a la columna de producción se hace ahí, agregando
> despacho por proveedor.
>
> El **Agente 05 no participa del debate**: hereda de `BaseAgent` por las utilidades
> de LLM (`_call_llm`, `extract_json`), expone `navigate(TrialNavigationInput)` y su
> `run()` levanta `NotImplementedError`. Separar `BaseAgent` en una base de LLM y un
> `DebateAgent` es el diseño correcto cuando existan 04, 05 y 06 —ninguno debate— y
> quedó diferido a un refactor propio que no altera este contrato.

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
          → Sin soporte = especulativa (nivel III, no se descarta)
          → Sin respuesta de PubMed = pendiente (nivel III)
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
- Filtro clave: `filter.overallStatus`, con los estados separados por `|`.
  Default de `clinical_trials.search()`: `RECRUITING`. El Agente 05 pide
  `RECRUITING|NOT_YET_RECRUITING`: un ensayo que abre en tres meses es accionable
  y se etiqueta "aún no recluta" en la vista y el PDF.
- Autenticación: ninguna (público)
- Retorno: JSON
- Presupuesto por análisis (Agente 05): ≤ 1 búsqueda base + 3 candidatas × 3 términos,
  con `clinical_trials_limiter` (10 req/s) y `clinical_trials_breaker`

### Orphanet API (ORPHAcodes — nomenclatura)
- Base URL: `https://api.orphacode.org/EN/ClinicalEntity`
- Endpoint usado: `/ApproximateName/{label}` (el término va en el path, escapado)
- Credencial **opcional**: responde 200 sin `apiKey` (medido el 2026-09-15, 10 de 10).
  El cliente manda `ORPHANET_API_KEY` si está definida y un valor por defecto si no.
  El Agente 05 la consulta siempre.
- 404 con cuerpo `"Query not found"` = sin coincidencias, **no** es error; cualquier
  otro 404, 401, 5xx o timeout → `ExternalApiError` y `estado_orphanet` degradado
- Usada por el Agente 05: marca una hipótesis como enfermedad rara solo ante
  **coincidencia exacta** normalizada con el nombre preferido (tomar el primer
  resultado etiquetaba una neuropatía axonal del adulto como enfermedad neonatal letal)
- **No expone genes**: `get_genes()` levanta `OrphanetGenesNoDisponibles`. Están en
  Orphadata (`api.orphadata.com/rd-associated-genes/orphacodes/{code}`), tarjeta aparte

### PharmGKB
- Gratuito para uso académico
- Usado por Agente 02 para relaciones fármaco-genómicas
