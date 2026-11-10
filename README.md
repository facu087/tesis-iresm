# NEXUS — Sistema de Soporte Investigativo Clínico Multi-Agente

> Tesis Final — Carrera Analista en Sistemas · IRESM, Villa Carlos Paz, Córdoba · 2026

NEXUS recibe los documentos clínicos de un paciente (PDF o texto), los procesa con seis
agentes de inteligencia artificial que debaten entre sí en rondas adversariales y genera un
reporte con **hipótesis de investigación priorizadas por nivel de evidencia**, respaldadas por
referencias de PubMed verificadas contra la fuente.

**NEXUS no emite diagnósticos.** Genera hipótesis de investigación para el médico responsable,
que conserva el criterio clínico y la decisión.

---

## Problema que aborda

Los pacientes con enfermedades raras atraviesan una *odisea diagnóstica* de entre 5 y 7 años,
derivados entre especialistas sin que ninguno disponga del tiempo necesario para sintetizar la
información del caso y contrastarla con la literatura científica. NEXUS funciona como un
comité de revisión adicional: propone líneas de investigación con su respaldo bibliográfico,
señala dónde los agentes no coinciden y busca ensayos clínicos activos compatibles.

---

## Cómo funciona

```
Documento clínico (PDF / texto)
        │
        ▼
Ingesta y normalización ── pdfplumber, OCR con Tesseract, nombres INN y unidades
        │
        ▼
Síntesis PICO + biomarcadores
        │
        ▼
RAG ── literatura de PubMed recuperada con embeddings biomédicos (ChromaDB)
        │
        ▼
Ronda 1 ── Agentes 01, 02 y 03 en paralelo
        │
        ▼
Rondas 2 a 4 ── debate adversarial: críticas cruzadas y revisiones
        │
        ▼
Filtro de citas ── solo valen los PMID que ofreció el RAG
        │
        ▼
Verificación ── cada PMID se contrasta contra PubMed (título real vs. citado)
        │
        ▼
Agente 04, Árbitro ── consenso, contradicciones y Ronda 5 de recitación
        │
        ▼
Agente 05, Navegador ── ensayos de ClinicalTrials.gov y enfermedades raras de Orphanet
        │
        ▼
Reporte estructurado + priorización EBM (niveles I, II y III)
        │
        ▼
Agente 06, Sintetizador ── resumen ejecutivo en prosa
```

Ninguna hipótesis se descarta: la que no tiene respaldo verificado queda como
**especulativa**, con nivel de evidencia III. El reporte se consulta en la web y se exporta a
PDF. El detalle de cada paso está en [`docs/arquitectura.md`](docs/arquitectura.md).

### Los seis agentes

| ID | Rol | Qué decide el modelo | Qué resuelve el código |
|----|-----|----------------------|------------------------|
| 01 | Analista de Literatura | Hipótesis a partir de la literatura | Anclaje de citas al RAG |
| 02 | Especialista Genómica | Hipótesis sobre biomarcadores | Contexto de PharmGKB y ClinVar; guarda anti-invención |
| 03 | Consultor Clínico | Hipótesis desde la medicina interna | Anclaje de citas al RAG |
| 04 | Árbitro Verificador | Qué hipótesis son equivalentes y los veredictos | Agrupamiento, contradicciones y nivel EBM |
| 05 | Navegador de Ensayos | Términos de búsqueda y compatibilidad | Búsqueda, filtros por edad y sexo, orden |
| 06 | Sintetizador | Resumen ejecutivo | Guarda anti-invención sobre PMID, NCT y genes |

Todos los agentes usan hoy **Groq `openai/gpt-oss-120b`** (y `gpt-oss-20b` en tres tareas de
salida validada por código), como proveedor temporal. La arquitectura de destino asigna Claude
Opus a los agentes 01, 04 y 06, GPT-4o al 02 y Gemini Pro al 03; el cambio se concentra en un
único punto de llamada al proveedor (`call_provider()`).

---

## Inicio rápido

Requisitos: Python 3.11 o superior, Node 22 y el binario `tesseract-ocr`.

```bash
# Backend (desde la raíz del repositorio)
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env          # completar GROQ_API_KEY y SECRET_KEY
python -m backend.cli crear-admin --email admin@ejemplo.example
uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

Para recorrer el sistema sin consumir cuota del modelo, `NEXUS_MOCK_LLM=1` usa respuestas
grabadas de una corrida real. La guía completa, con las variables de entorno y el despliegue
en producción, está en [`docs/instalacion-y-despliegue.md`](docs/instalacion-y-despliegue.md).

---

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [`docs/arquitectura.md`](docs/arquitectura.md) | Flujo del pipeline, agentes, verificación, aspectos transversales y decisiones de diseño |
| [`docs/instalacion-y-despliegue.md`](docs/instalacion-y-despliegue.md) | Instalación local, variables de entorno, alta del administrador, producción, pruebas y CI |
| [`docs/manual-de-uso.md`](docs/manual-de-uso.md) | Uso por parte del médico y del administrador, y lectura del reporte |
| [`docs/resultados-y-limitaciones.md`](docs/resultados-y-limitaciones.md) | Método de evaluación, cifras medidas, problemas corregidos, limitaciones y trabajo futuro |
| [`docs/revision-medica.md`](docs/revision-medica.md) | Protocolo de la revisión del reporte con un médico |
| [`openspec/specs/`](openspec/specs/) | Especificaciones vigentes del sistema, por capacidad |

---

## Estado del proyecto

| Etapa | Descripción | Estado |
|-------|-------------|--------|
| 1 | Fundamentación teórica y diseño | Completada |
| 2 | Prueba de concepto | Completada |
| 3 | Pipeline multi-agente y debate | Completada |
| 4 | Frontend conectado al backend | Completada |
| 5 | Árbitro, verificación bibliográfica y evidencia | Completada |
| 6 | Validación y cierre | En curso: falta la revisión con un médico y la anonimización automática está en revisión |

En la corrida de verificación del 2026-11-03, el reporte del caso base cumplió los tres
criterios de calidad definidos (cobertura de respaldo 0,91, precisión de citas 1,00 y
sobredeclaración 0,45), con un consumo de 84.666 tokens y 502 segundos por caso. Las
mediciones y sus limitaciones están en
[`docs/resultados-y-limitaciones.md`](docs/resultados-y-limitaciones.md).

---

## Principios éticos y de seguridad

- **El médico es el usuario.** El acceso requiere una cuenta con matrícula revisada por un
  administrador; NEXUS no está pensado para pacientes.
- **Hipótesis, no diagnósticos.** El aviso es visible en todas las pantallas y en el PDF.
- **Trazabilidad.** Cada cita se verifica contra PubMed y el reporte informa el estado de la
  verificación; las divergencias entre agentes se documentan.
- **Privacidad.** Los datos clínicos no se registran en texto plano ni se conservan más allá
  de la sesión, y la telemetría guarda solo conteos.

---

## Referencias bibliográficas clave

- Han, Y. et al. (2025). *Enhancing diagnostic capability with multi-agents conversational
  large language models*. NPJ Digital Medicine, 8(159).
- Schmeder, A. et al. (2025). *DeepRare: An agentic system for rare disease diagnosis with
  traceable reasoning*. Nature.
- Silveira, A. L. et al. (2026). *Multi-agent systems for clinical decision support: A
  systematic review*. Applied Soft Computing, 188.

---

## Licencia

Documento y código de uso académico. Todos los derechos reservados.
Tesis Final — Carrera Analista en Sistemas · 2026
