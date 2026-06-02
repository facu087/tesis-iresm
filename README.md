# NEXUS — Sistema de Soporte Investigativo Clínico Multi-Agente

> Tesis Final — Analista en Sistemas  

---

## ¿Qué es NEXUS?

NEXUS es un sistema de inteligencia artificial multi-agente diseñado para asistir a médicos en casos clínicos complejos, especialmente enfermedades raras. Recibe documentos clínicos de un paciente, los procesa mediante un pipeline de 6 agentes de IA especializados que debaten entre sí, y genera un reporte estructurado con **hipótesis de investigación priorizadas por nivel de evidencia**, respaldadas por referencias bibliográficas verificables de PubMed.

**NEXUS no emite diagnósticos.** Su función es ampliar el horizonte investigativo del médico responsable, no reemplazar su criterio clínico.

---

## Problema que resuelve

Los pacientes con enfermedades raras enfrentan una *odisea diagnóstica* de entre 5 y 7 años, durante la cual son derivados entre múltiples especialistas sin que ninguno cuente con el tiempo para sintetizar toda la información disponible y compararla con el estado del arte de la investigación.

PubMed indexa más de 50 millones de publicaciones. Ningún médico puede mantenerse actualizado en todos los subdominios relevantes para un caso multidisciplinar complejo. NEXUS actúa como un **segundo comité de expertos disponible las 24 horas**.

---

## Arquitectura del sistema

```
Documentos clínicos (PDF / imágenes)
            │
            ▼
    ┌───────────────┐
    │    Ingesta    │  OCR + extracción de texto + normalización
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Síntesis PICO │  Agente Orquestador → estructura el caso
    └───────┬───────┘
            │
     ┌──────┴──────┐
     │  RAG Engine │  Embeddings biomédicos (SciBERT) + ChromaDB
     └──────┬──────┘
            │ Literatura relevante
            ▼
    ┌───────────────────────────────┐
    │     Pipeline Multi-Agente     │
    │                               │
    │  Agente 01 │ Agente 02 │ Ag 03│  ← Ronda 1: análisis paralelo
    │  Literatura│ Genómica  │Clínic│
    │            ↓           ↓     │
    │       Rondas 2-4: debate      │
    │       adversarial             │
    └───────────────┬───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  Agente 04    │  Árbitro: verifica hipótesis vs PubMed
            │  Árbitro      │  Descarta sin respaldo bibliográfico
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Agente 05    │  Busca ensayos clínicos activos
            │  ClinicalTr.  │  (ClinicalTrials.gov API v2)
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Agente 06    │  Genera el reporte final estructurado
            │  Sintetizador │  (PDF / DOCX para el médico)
            └───────────────┘
```

---

## Agentes del sistema

| Agente | Rol | Modelo | Herramientas |
|--------|-----|--------|--------------|
| 01 — Analista de Literatura | Recupera y procesa literatura científica | Claude Opus | PubMed API, RAG |
| 02 — Especialista en Genómica | Analiza biomarcadores y mutaciones | GPT-4o* | PharmGKB, ClinVar |
| 03 — Consultor Clínico | Razona desde medicina interna | Gemini Pro* | NCCN Guidelines |
| 04 — Árbitro Verificador | Valida hipótesis, gestiona divergencias | Claude Opus | PubMed, ESMO, EMA |
| 05 — Navegador de Ensayos | Busca ensayos clínicos compatibles | Dedicado | ClinicalTrials.gov API v2 |
| 06 — Sintetizador | Genera el reporte final | Claude Opus | PDF/DOCX export |

> *En el proof of concept (Etapa 2), todos los agentes usan Claude Opus para simplificar la implementación inicial.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python 3.11+ |
| API Framework | FastAPI |
| LLM principal | Claude Opus (Anthropic API) |
| Embeddings | SciBERT (sentence-transformers) |
| Base vectorial | ChromaDB |
| Extracción PDF | pdfplumber |
| OCR | Tesseract |
| Literatura | PubMed E-utilities (NCBI) |
| Ensayos clínicos | ClinicalTrials.gov API v2 |
| Enfermedades raras | Orphanet API |
| Farmacogenómica | PharmGKB API |
| Deploy prototipo | Railway.app |
| Frontend (proto) | HTML / CSS / JS nativo |
| Frontend (prod) | React 18+ |

---

## Estructura del proyecto

```
nexus/
├── agents/
│   └── agentes.py          # Los 6 agentes especializados
├── core/
│   ├── models.py            # Modelos de datos (CasoClinico, Hipotesis, etc.)
│   ├── ingesta.py           # Extracción y normalización de PDFs
│   ├── rag.py               # Motor RAG (embeddings + ChromaDB)
│   └── orchestrator.py      # Orquestador del pipeline completo
├── tools/
│   ├── pubmed.py            # Integración PubMed E-utilities
│   └── clinical_trials.py   # Integración ClinicalTrials.gov API v2
├── utils/
├── requirements.txt
├── .env.example
└── main.py                  # Punto de entrada
```

---

## Instalación y uso

### Requisitos previos
- Python 3.11+
- API key de Anthropic ([obtener aquí](https://console.anthropic.com))

### Setup

```bash
# Clonar el repositorio
git clone https://github.com/facu087/tesis-iresm
cd tesis-iresm

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu ANTHROPIC_API_KEY
```

### Ejecutar el proof of concept

```bash
python main.py --caso docs/caso_ejemplo.pdf
```

---

## Hoja de ruta

| Etapa | Descripción | Estado |
|-------|-------------|--------|
| 1 | Fundamentación teórica y diseño del sistema | ✅ Completada |
| 2 | Proof of concept: 1 agente + Claude API + caso real | 🔜 En desarrollo |
| 3 | Pipeline completo: multi-agente + debate + ClinicalTrials | 📋 Planificada |
| 4 | Frontend conectado al backend real | 📋 Planificada |
| 5 | Agente Árbitro + verificación PubMed completa | 📋 Planificada |
| 6 | Validación con casos clínicos reales | 📋 Planificada |

---

## Principios éticos y de seguridad

- **El médico es el usuario primario.** NEXUS no es de acceso directo para pacientes.
- **Hipótesis, no diagnósticos.** El sistema genera rutas de investigación con respaldo bibliográfico, nunca conclusiones definitivas.
- **Privacidad desde el diseño.** Los datos clínicos se anonimizan antes de enviarse a APIs externas y no se almacenan más allá de la sesión activa.
- **Trazabilidad completa.** Cada hipótesis en el reporte final lleva asociada al menos una referencia con PubMed ID. Las hipótesis sin soporte son descartadas.
- **Transparencia del razonamiento.** Las divergencias entre agentes se documentan explícitamente.

---

## Referencias bibliográficas clave

- Han, Y. et al. (2025). *Enhancing diagnostic capability with multi-agents conversational large language models*. NPJ Digital Medicine, 8(159).
- Schmeder, A. et al. (2025). *DeepRare: An agentic system for rare disease diagnosis with traceable reasoning*. Nature.
- Silveira, A. L. et al. (2026). *Multi-agent systems for clinical decision support: A systematic review*. Applied Soft Computing, 188.

---

## Licencia

Documento y código de uso académico. Todos los derechos reservados.  
Tesis Final — Carrera Analista en Sistemas · 2026
