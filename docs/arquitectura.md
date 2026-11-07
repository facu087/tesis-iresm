# Arquitectura del sistema NEXUS

Este documento describe la arquitectura de NEXUS tal como está implementada en
el repositorio al cierre del proyecto (rama `develop`). Cada módulo, función y
orden de ejecución citado se contrastó contra el código. Cuando la
documentación anterior (`README.md`, `.claude/architecture.md`) difiere del
código, manda el código.

---

## 1. Propósito y regla central

NEXUS es un sistema de soporte a la investigación clínica basado en varios
agentes de IA. Recibe documentación clínica de un paciente (PDF nativo, PDF
escaneado o texto), la procesa mediante agentes especializados que debaten en
rondas adversariales y entrega un reporte estructurado con hipótesis de
investigación priorizadas por nivel de evidencia, respaldadas por referencias
de PubMed verificadas.

**Regla central: NEXUS no emite diagnósticos. Genera hipótesis de
investigación para el médico responsable.** La regla condiciona el diseño
completo: ninguna hipótesis se descarta por falta de respaldo (queda marcada
como especulativa), el nivel de evidencia nunca sube por encima de lo que
sostiene la literatura verificada, y el aviso se muestra en el reporte, en el
PDF y en las rutas con sesión del frontend.

---

## 2. Flujo de `POST /api/analyze`

El endpoint está en `backend/api/router.py` (función `analyze`). Exige una
sesión de médico en estado `verificado` (`requerir_medico_verificado`) y un
`Origin`/`Referer` permitido (`validar_origen`). Al empezar abre el registro de
telemetría de consumo y la sesión de reproducción del modo mock; ambos se
cierran en un bloque `finally`.

### 2.1 Orden real de ejecución

| Paso | Qué ocurre | Módulo / función |
|------|------------|------------------|
| 1 | Extracción de texto: PDF nativo con pdfplumber, PDF escaneado con Tesseract (OCR) o texto plano | `ingestion/extractor.py` — `extract()` |
| 2 | Normalización terminológica (nombres INN y unidades) | `ingestion/normalizer.py` — `normalize()` |
| 3 | Síntesis PICO y extracción de biomarcadores, **en paralelo** (`asyncio.gather`) | `pipeline/pico.py` — `build()`; `ingestion/biomarker_extractor.py` — `extract()` |
| 4a | Antes de la Ronda 1, **en paralelo**: recuperación RAG (hasta `MAX_ARTICULOS_RAG = 10` artículos) y enriquecimiento del perfil genómico (PharmGKB, ClinVar) | `pipeline/orchestrator.py` — `_enrich_context_with_rag()`; `pipeline/genomic_context.py` — `build()` + `enrich()` |
| 4b | Ronda 1: Agentes 01, 02 y 03 **en paralelo** sobre el contexto PICO + RAG | `pipeline/orchestrator.py` — `run_round_1()` |
| 5 | Debate adversarial: Ronda 2 (críticas cruzadas), Rondas 3 y 4 (revisiones con la lista corta de literatura ofrecida) | `pipeline/debate.py` — `run_debate()` |
| 5' | Filtro de citas fuera del RAG sobre las hipótesis finales | `pipeline/debate.py` — `_anclar_citas()` → `pipeline/recitation.py` — `filtrar_citas()` |
| 6 | Verificación de los PMIDs citados contra PubMed | `pipeline/verification.py` — `verify_report_sources()` |
| 7 | Árbitro (Agente 04): agrupamiento, consenso, Ronda 5 de recitación, veredictos | `agents/agent_04_arbiter.py` — `arbitrate()` |
| 8 | Navegación de ensayos (Agente 05) sobre las hipótesis de consenso | `pipeline/trial_matching.py` — `build_navigation_input()`; `agents/agent_05_trials.py` — `navigate()` |
| 9 | Construcción del reporte estructurado y priorización EBM | `pipeline/report_builder.py` — `build_export()` |
| 10 | Resumen ejecutivo en prosa (Agente 06) | `agents/agent_06_synthesizer.py` — `synthesize()` |

Los pasos 6 y 7 corren dentro del contexto `registro_de_consultas()`, que anota
el resultado de cada consulta a PubMed (la verificación inicial y la
re-verificación de la Ronda 5) para calcular el estado global de la
verificación. A partir del paso 5 el pipeline es **serial**: la navegación de
ensayos no corre en paralelo con la verificación, sino después del arbitraje,
porque busca sobre el consenso. Si el consenso queda vacío, usa las hipótesis
finales del debate.

### 2.2 Diagrama

```
  PDF / imagen escaneada / texto
              │
              ▼
  ┌───────────────────────────┐
  │ 1. Extracción             │  pdfplumber · Tesseract
  │ 2. Normalización          │  INN · unidades
  └─────────────┬─────────────┘
                ▼
  ┌──────────────┐   ┌──────────────────┐
  │ 3. PICO      │ ∥ │ 3. Biomarcadores │      (asyncio.gather)
  └──────┬───────┘   └────────┬─────────┘
         └─────────┬──────────┘
                   ▼
  ┌──────────────────┐   ┌──────────────────────┐
  │ 4a. RAG          │ ∥ │ 4a. Perfil genómico  │ (asyncio.gather)
  │ ChromaDB +       │   │ PharmGKB · ClinVar   │
  │ PubMedBERT       │   │                      │
  └────────┬─────────┘   └──────────┬───────────┘
           └───────────┬────────────┘
                       ▼
  ┌──────────────────────────────────────────────┐
  │ 4b. Ronda 1   Agente 01 ∥ Agente 02 ∥ Agente 03│
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │ 5. Ronda 2 críticas → Ronda 3 → Ronda 4      │
  │    Filtro: se descartan PMIDs no ofrecidos   │
  │    por el RAG (fuera_del_rag)                │
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │ 6. Verificación de PMIDs contra PubMed       │
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │ 7. Agente 04 — Árbitro                       │
  │    agrupación → consenso → Ronda 5           │
  │    (recitación + re-verificación) → veredicto│
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │ 8. Agente 05 — Navegador de ensayos          │
  │    ClinicalTrials.gov · Orphanet             │
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │ 9. report_builder.build_export()             │
  │    priorización EBM · estado de verificación │
  └──────────────────────┬───────────────────────┘
                         ▼
  ┌──────────────────────────────────────────────┐
  │ 10. Agente 06 — executive_summary            │
  └──────────────────────┬───────────────────────┘
                         ▼
          StructuredReport (JSON) ──► POST /api/report/pdf (ReportLab)
```

El PDF no forma parte de `POST /api/analyze`: el frontend lo pide aparte con
`POST /api/report/pdf`, que recibe el `StructuredReport` y lo exporta con
`pipeline/pdf_exporter.py` (`generate_pdf()`). Ese endpoint exige la misma
sesión de médico verificado.

### 2.3 Tolerancia a fallos en el flujo

- Si un agente falla en la Ronda 1, se registra por stderr y el pipeline sigue
  con los restantes; solo se aborta si fallan los tres.
- El debate corre solo con los agentes que produjeron salida en la Ronda 1.
  Con menos de dos agentes no hay debate posible: se devuelven las hipótesis de
  la Ronda 1 (igualmente filtradas por el RAG).
- El Árbitro, el Navegador y el Sintetizador se invocan mediante envoltorios
  seguros en el router (`_arbitrate_safe`, `_navigate_trials_safe`,
  `_synthesize_safe`): una falla degrada esa sección del reporte, no el
  análisis completo.

---

## 3. Los seis agentes

Todos heredan de `BaseAgent` (`backend/agents/base_agent.py`). Los Agentes 01,
02 y 03 participan del debate; 04, 05 y 06 no debaten y exponen un método
propio (`arbitrate()`, `navigate()`, `synthesize()`).

| ID | Rol | Qué decide el LLM | Qué es código determinista | Archivo |
|----|-----|-------------------|----------------------------|---------|
| 01 | Analista de Literatura | Hipótesis, críticas y revisiones a partir del contexto y la literatura ofrecida | Parseo y validación del JSON; filtro de citas | `agents/agent_01_literature.py` |
| 02 | Especialista Genómica | Hipótesis genómicas sobre el perfil enriquecido | Perfil genómico (`pipeline/genomic_context.py`); **guarda anti-invención** (`_apply_invention_guard`): descarta hipótesis que mencionan variantes, alelos o hallazgos no reportados en el caso | `agents/agent_02_genomics.py` |
| 03 | Consultor Clínico | Hipótesis clínicas, críticas y revisiones | Parseo y validación del JSON; filtro de citas | `agents/agent_03_clinical.py` |
| 04 | Árbitro Verificador | Solo propone qué hipótesis son equivalentes (devuelve índices, nunca texto) y redacta los veredictos | Validación de la partición, elección del enunciado representativo, detección de contradicciones, clasificación EBM, selección de la Ronda 5 y aceptación de lo recitado (`pipeline/consensus.py`, `pipeline/recitation.py`, `pipeline/evidence.py`) | `agents/agent_04_arbiter.py` |
| 05 | Navegador de Ensayos | Traduce hipótesis a términos de condición en inglés y etiqueta compatibilidad (`alta`/`media`/`baja`) | Búsqueda en ClinicalTrials.gov, filtros duros por edad y sexo, coincidencia exacta con Orphanet y orden del resultado (`pipeline/trial_matching.py`) | `agents/agent_05_trials.py` |
| 06 | Sintetizador | Redacta el `executive_summary` en prosa | **Guarda anti-invención** (`check_invention`): descarta el resumen si cita un PMID, NCT o gen ausente o no confirmado en el reporte; también si la respuesta está vacía o no es texto | `agents/agent_06_synthesizer.py` |

Garantías del diseño híbrido de los Agentes 04 y 05: el LLM nunca descarta una
hipótesis, nunca introduce referencias, nunca altera un nivel de evidencia y
nunca excluye un ensayo. Si la agrupación del Árbitro no es utilizable, se
arma un consenso degradado (`consensus.degraded()`: cada hipótesis en su
propio grupo) y se deja constancia en el resumen.

El Agente 06 corre después de `build_export()` y solo agrega el resumen
ejecutivo; no reemplaza a `report_builder.py`. Si su guarda lo descarta, el
reporte queda sin resumen.

---

## 4. Evidencia y verificación

### 4.1 Citas ancladas al RAG

Una cita con PMID solo se acepta si ese PMID fue ofrecido por el RAG en la
Ronda 1. `run_debate()` aplica `recitation.filtrar_citas()` a las hipótesis
finales antes de la verificación: lo descartado no se consulta en PubMed ni
aparece en el reporte. El total descartado queda en
`verification.fuera_del_rag` del reporte (`None` en reportes anteriores al
cambio). Las fuentes sin PMID se conservan. Ninguna hipótesis se descarta: la
que queda sin fuentes pasa a especulativa y entra en la Ronda 5. Los prompts de
los Agentes 01, 02 y 03 incluyen la regla (`base_agent.REGLA_CITAS`) y las
Rondas 3 y 4 reciben la lista corta de artículos ofrecidos
(`recitation.lista_de_literatura()`).

### 4.2 Verificación de PMIDs

`pipeline/verification.py` consulta PubMed (`external/pubmed.py`) por cada PMID
citado y compara el título real con el citado. El estado global de la
verificación (`EstadoVerificacion`) se calcula con `estado_verificacion()` a
partir de las consultas registradas:

| Estado | Condición |
|--------|-----------|
| `completa` | Todas las consultas a PubMed respondieron |
| `parcial` | Alguna consulta falló, pero no todas |
| `no_disponible` | Fallaron todas las consultas |
| `sin_consulta` | No hubo consultas (por ejemplo, ninguna cita con PMID) |

Ante un fallo se informa una causa categorizada (`clasificar_fallo()`), nunca
el texto del error, la URL ni la clave. El estado y la causa se muestran en
`/report` y en el PDF.

### 4.3 Clasificación EBM

`pipeline/evidence.py` acota el `evidence_level` que autodeclara cada agente:

1. Cada fuente verificada habilita un nivel máximo según el tipo de
   publicación que indexa PubMed (`source_ceiling()`; por ejemplo,
   Meta-Analysis habilita I, Observational Study II y Case Reports III).
2. El nivel efectivo es el declarado, limitado por el mejor tope de sus fuentes
   verificadas. Nunca sube. Sin fuentes verificadas, el nivel es III.
3. Estado de la hipótesis: `respaldada` (al menos una fuente verificada),
   `pendiente` (la verificación no pudo concluir) o `especulativa`.
4. Orden del reporte (`prioritize()`): estado, nivel efectivo, prioridad,
   fuentes verificadas y orden original.

`classify_hypothesis()` lo usan el consenso del Árbitro y la Ronda 5;
`prioritize()` lo usa `report_builder.py`.

### 4.4 Ronda 5: recitación

Las hipótesis sin respaldo vuelven a su autor con el motivo por el que falló
cada cita y los artículos recuperados por el RAG, para que vuelvan a citar
sobre literatura real. Hay una sola iteración; lo que siga sin respaldo queda
especulativo. Las fuentes recitadas se re-verifican contra PubMed y los
veredictos del Árbitro se redactan después de la Ronda 5, de modo que
describan el estado final de la hipótesis.

### 4.5 Criterios de calidad (fuera del pipeline)

`pipeline/calidad.py` define `evaluar()`, una función pura que evalúa un
reporte guardado y devuelve un veredicto (`cumple`, `no_cumple`,
`no_evaluable`) con tres métricas contra umbral: cobertura de respaldo,
precisión de citas y sobredeclaración. **El pipeline no la invoca**: la usa
`scripts/evaluar_reporte.py` sobre un `reporte.json`. Los umbrales son
provisionales (versión `2026-11-provisional`). La corrida de verificación de
la tarjeta #92 (2026-11-03) cumplió los tres criterios: cobertura 0,91,
precisión 1,00 y sobredeclaración 0,45, con 0 citas fuera del RAG.

---

## 5. Aspectos transversales

### 5.1 Punto único de llamada al proveedor

Ningún módulo instancia el cliente de Groq por su cuenta: el único lugar es
`call_provider()` en `backend/agents/base_agent.py`. Los agentes llaman a
través de `BaseAgent._call_llm(user_message, *, task)`; `pipeline/pico.py` e
`ingestion/biomarker_extractor.py` llaman a `call_provider()` directamente.

El argumento `task` es obligatorio y resuelve modelo y techo de tokens desde
`TASK_BUDGETS` en `backend/agents/model_tasks.py` (trece tareas). Solo tres
usan `GROQ_FAST` (`openai/gpt-oss-20b`): `arbitro_agrupacion`,
`agente05_planificacion_terminos` y `agente05_evaluacion_compatibilidad`,
cuya salida se valida por código. El resto usa `GROQ_MAIN`
(`openai/gpt-oss-120b`). En `call_provider()` viven también el reintento ante
respuestas 429, la telemetría y el modo mock.

### 5.2 Telemetría de costos

`backend/telemetry/usage.py` registra por análisis (con `contextvars`) cada
llamada: paso, modelo, tokens de entrada y salida, latencia y si falló. Al
cerrar el análisis se agrega una línea a `output/costos.jsonl`. El
identificador de análisis es aleatorio y la telemetría nunca contiene texto
clínico, prompts ni respuestas. `backend/telemetry/pricing.py` contiene las
tarifas por modelo y `usage.recalculate()` recalcula un registro con otra
tabla. La última medición (`scripts/medir_costos.py`, 2026-11-03, tarjeta #92) arrojó
84.666 tokens por caso en 27 llamadas; la serie completa está en
`resultados-y-limitaciones.md`.

### 5.3 Modo mock

Con `NEXUS_MOCK_LLM=1` (apagado por defecto), `call_provider()` devuelve
respuestas grabadas de una corrida real (`backend/mock/grabadas.json`, cargado
por `backend/mock/responses.py`) sin tocar la red. Las respuestas atraviesan el
mismo parseo y las mismas validaciones que una real, y la grabación incluye
los artículos que ofreció el RAG. El reporte queda marcado
(`StructuredReport.metadata.mock`) y la marca se muestra en el frontend y el
PDF. Sin `GROQ_API_KEY` y sin modo mock, el análisis falla con un error
explícito. La verificación de PMIDs y la búsqueda de ensayos siguen
consultando las APIs en vivo.

### 5.4 APIs externas: límites y respaldos

`backend/external/rate_limiter.py` provee `RateLimiter` (ventana de
solicitudes por segundo por API), `ApiCircuitBreaker` (corta las llamadas a una
API que falla de forma repetida), el decorador `with_fallback()` (valor de
respaldo explícito) y la jerarquía `ExternalApiError` / `RateLimitError` /
`ApiUnavailableError`. Lo importan los clientes de Orphanet, Orphadata,
PharmGKB y ClinVar (este último con el limitador y el corte de NCBI). Los
clientes de PubMed (`external/pubmed.py`) y ClinicalTrials.gov
(`external/clinical_trials.py`) no lo importan: reintentan con espera
exponencial (`tenacity`) y el pipeline degrada su sección ante un fallo.

### 5.5 Cuentas y autenticación

| Componente | Archivo | Función |
|------------|---------|---------|
| Modelos | `models/cuenta.py`, `models/auditoria.py`, `models/sesion.py` | `CuentaMedico` (rol `medico`/`admin`; estado `pendiente`/`rechazado`/`verificado`), `DecisionAuditoria`, `Sesion` |
| Contraseñas | `auth/security.py` | Hash Argon2id (`argon2-cffi`) |
| Login | `auth/login.py` | Bloqueo temporal tras `MAX_INTENTOS_FALLIDOS = 5` durante `BLOQUEO_MINUTOS = 15` |
| Sesión | `auth/sesiones.py` | Token opaco en cookie firmada con HMAC-SHA256 (`SECRET_KEY`), fila server-side en `sesion` |
| Autorización | `auth/deps.py` | `requerir_sesion`, `requerir_admin`, `requerir_medico_verificado` |
| CSRF | `auth/origen.py` | `validar_origen` contrasta `Origin`/`Referer` con `ALLOWED_ORIGINS` en todo endpoint que cambia estado |
| Endpoints | `api/cuentas_router.py`, `api/admin_router.py` | `POST`/`PUT /api/registro`, `POST /api/login`, `POST /api/logout`, `GET /api/cuenta`; `GET /api/admin/pendientes`, `POST /api/admin/cuentas/{id}/aprobar` y `/rechazar` |
| Primer admin | `backend/cli.py` | `python -m backend.cli crear-admin`; ninguna instalación trae un admin por defecto |

El médico se registra con su matrícula; un administrador la revisa y aprueba o
rechaza con motivo, y cada decisión queda auditada. Solo una cuenta
`verificado` puede ejecutar el análisis o exportar el PDF. La verificación
automática de matrícula es un punto de extensión sin implementar
(`auth/verificacion.py`). La persistencia es SQLite (`backend/db.py`), creada
con `create_db_and_tables()` en el `lifespan` de `backend/main.py`.

### 5.6 Seguridad HTTP

`backend/seguridad.py` concentra tres decisiones:

- `origenes_permitidos()` es la única lectura de `ALLOWED_ORIGINS` (la usan
  CORS y la validación CSRF). Una configuración insegura (por ejemplo `*`)
  levanta `ConfiguracionInsegura` e impide arrancar.
- `es_produccion()` decide HSTS, cookie `Secure` y el apagado de `/docs`.
- `EncabezadosDeSeguridad` (middleware ASGI) agrega `nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP, una
  CSP de API y `Cache-Control: no-store` en `/api/*`; HSTS solo en producción.

El backend no termina TLS: se despliega detrás de un proxy inverso.

### 5.7 Limpieza de sesiones

`backend/mantenimiento/limpieza.py` borra en segundo plano las filas vencidas
de la tabla `sesion` (`bucle_de_limpieza()`, iniciada por `iniciar_tarea()` en
el `lifespan`). El intervalo lo fija `SESSION_CLEANUP_INTERVAL_MINUTES` (0 la
apaga). El backend no escribe archivos temporales: el documento se procesa en
memoria.

---

## 6. Frontend

Aplicación Next.js en `frontend/`. El cliente HTTP es `frontend/src/lib/api.ts`,
que llama al backend con `credentials: "include"` para enviar la cookie de
sesión.

| Ruta | Función | Llamadas al backend |
|------|---------|---------------------|
| `/` | Landing | `GET /api/cuenta` (acción según la sesión) |
| `/registro` | Alta de médico con consentimiento (Ley 25.326) | `POST /api/registro` |
| `/ingresar` | Login | `POST /api/login` |
| `/cuenta` | Estado de la cuenta y reenvío corregido tras un rechazo | `GET /api/cuenta`, `PUT /api/registro`, `POST /api/logout` |
| `/admin/pendientes` | Revisión de cuentas pendientes | `GET /api/admin/pendientes`, aprobar/rechazar, `POST /api/logout` |
| `/analizar` | Carga del PDF o del texto | `GET /api/cuenta` (guarda de sesión); la entrada se guarda en `lib/inputStore.ts` |
| `/analyzing` | Progreso del pipeline | `POST /api/analyze` (`analyzeFile`/`analyzeText`) |
| `/report` | Reporte en cinco pestañas: hipótesis, caso clínico, debate, ensayos clínicos y bibliografía | `POST /api/report/pdf` (`downloadPdf`) |

Los pasos que muestra la vista de progreso salen de una fuente única,
`lib/pipelineSteps.ts`. Todas las rutas comparten un solo sistema visual
(clase envoltorio `.landing` en `globals.css`, tipografía Geist, iconos
Phosphor, tema claro y oscuro) y el aviso "NEXUS no emite diagnósticos". Las
guardas de sesión del frontend son una capa de experiencia de usuario; la
autorización real la aplica el backend.

---

## 7. Modelos de datos

Modelos Pydantic en `backend/models/` (las tablas de cuentas usan SQLModel) y
el contrato de salida en `backend/api/schemas.py`.

| Archivo | Modelos principales |
|---------|---------------------|
| `hypothesis.py` | `Hypothesis`, `Source`, `EvidenceLevel`, `Priority` |
| `report.py` | `Report`, `AgentOutput`, `Critique`, `DebateRound`, `RetrievedArticleRef` |
| `case.py` | `ClinicalCase`, `PICOSynthesis` |
| `biomarkers.py` | `BiomarkerProfile` |
| `genomics.py` | `GenomicContext`, `PharmacogenomicAnnotation`, `VariantClassification` |
| `arbitration.py` | `ArbitrationInput`, `ArbitrationResult`, `ConsensusHypothesis`, `Contradiction`, `RecitationSummary` |
| `trial.py` | `ClinicalTrial`, `RareDiseaseMatch`, `TrialNavigationInput`, `TrialNavigationResult` |
| `cuenta.py`, `auditoria.py`, `sesion.py` | `CuentaMedico`, `DecisionAuditoria`, `Sesion` (tablas SQLModel) |
| `api/schemas.py` | `StructuredReport`, `ReportMetadata`, `RankedHypothesis`, `VerificationSummary`, `ArbitrationOut` |

---

## 8. Decisiones de diseño

| Decisión | Motivo |
|----------|--------|
| Pipeline serializado después del debate (verificación → Árbitro → ensayos → reporte → resumen) | Cada etapa necesita el resultado de la anterior: el Árbitro decide qué recitar según qué citas resistieron, y los ensayos se buscan sobre el consenso, con menos hipótesis y sin duplicados. El paralelismo se conserva donde no hay dependencia (PICO y biomarcadores, RAG y perfil genómico, Ronda 1, críticas y revisiones del debate). |
| Agentes 04 y 05 híbridos | El LLM queda limitado a tareas de lenguaje (agrupar por índices, redactar, traducir términos, etiquetar compatibilidad); toda decisión que afecta el resultado es código determinista y testeable. |
| Ronda 5 de recitación | Reemplaza el criterio de parada original ("toda hipótesis con referencia verificable"), que no se cumplía nunca: en la corrida que lo motivó, 15 de 15 citas eran discordantes. Una sola iteración acota el costo. |
| Citas ancladas al RAG | Los agentes citaban PMIDs de memoria que no correspondían al título citado. Aceptar solo lo ofrecido por el RAG garantiza que toda cita provenga de literatura recuperada. |
| Guardas anti-invención en 02 y 06 | Un hallazgo genético o una referencia inventados son el error más grave para el médico; se descartan por código antes de llegar al reporte. |
| Groq `gpt-oss` como proveedor temporal | Reemplaza a los modelos de destino mientras se gestionan créditos de las APIs pagas. La arquitectura de destino usa Claude Opus (Agentes 01, 04, 06), GPT-4o (Agente 02) y Gemini Pro (Agente 03); el cambio se concentra en `call_provider()`. |

---

## 9. Trabajo pendiente relacionado con la privacidad

La anonimización del texto clínico antes de enviarlo a APIs externas
(`backend/ingestion/anonimizador.py`) está en revisión en el PR #82 de GitHub y todavía
no forma parte de la rama `develop`.
