## Context

Motivación en `proposal.md` (Why). Estado actual relevante para el cómo:

- `api/router.py` paso 6 llama a `clinical_trials.search_by_biomarkers(biomarcadores[:5],
  condition_en or chief_complaint)` en un `to_thread`, atrapa `Exception`, imprime el
  mensaje y devuelve `[]`. El paso 7 (`verify_report_sources`) corre después, en serie.
- `BaseAgent` mezcla dos cosas: utilidades de LLM (`_call_llm`, `extract_json`) y la interfaz
  del debate (`run(clinical_context) -> AgentOutput`, `critique`, `revise`). `run` es abstracto.
  `_call_llm` usa siempre `self.MODEL` y `self.SYSTEM_PROMPT`.
- `extract_json` lanza `ValueError` con los primeros 500 caracteres de la respuesta del LLM
  en el mensaje: loggear `str(exc)` puede volcar texto clínico a stderr.
- `PICOSynthesis` no tiene edad ni sexo estructurados: vienen dentro de `patient_profile`
  (texto libre en español, p. ej. "Paciente masculino de 42 años con DM2 de 10 años de evolución").
- `ClinicalTrial` ya trae `min_age`, `max_age` ("18 Years"), `sex` (ALL/MALE/FEMALE) y
  `eligibility_criteria` (texto libre, a veces de varios miles de caracteres).
- `external/clinical_trials.py` expone `search(condition, keywords, max_results,
  recruiting_only: bool)`: el booleano solo permite "todos los estados" o "solo
  `RECRUITING`". `ClinicalTrial` ya trae `status` y `locations` (lista de países).
- `external/rate_limiter.py` define `clinical_trials_limiter/breaker` y
  `orphanet_limiter/breaker`. El limiter de Orphanet **ya lo usa el cliente**
  internamente (`OrphanetClient._request`); los de ClinicalTrials.gov siguen sin uso.
- **Cliente Orphanet ya arreglado** en `fix/s4-cliente-orphanet` (commit `41828a8`, en
  `develop`), a partir de estas mediciones contra la API real del 2026-09-15:

  | Llamada | Resultado |
  |---|---|
  | `GET /EN/ClinicalEntity/approximatelymatching?name=…` (lo que usaba `search()`) | 404 genérico `{"title": "Not Found"}` |
  | `GET /EN/ClinicalEntity/ApproximateName/{name}` | 200, lista de `{"ORPHAcode": int, "Preferred term": str}` |
  | `ApproximateName` sin header `apiKey` | **200** (10 de 10 llamadas). Los 401 que medimos antes eran intermitentes, con una sola muestra cada uno |
  | `ApproximateName` sin coincidencias | 404 con cuerpo `"Query not found"` |
  | `GET /EN/ClinicalEntity/DisorderGene/{code}` (lo que usaba `_get_genes()`) | 404 genérico: la ORPHAcodes API es de nomenclatura y no expone genes |
  | `ApproximateName/axonal sensorimotor polyneuropathy` | 1.º resultado: *Autosomal recessive lethal neonatal axonal sensorimotor polyneuropathy* |
  | `ApproximateName/hereditary transthyretin amyloidosis` | 234 resultados; 1.º *Hereditary amyloidosis*, 2.º *Hereditary ATTR amyloidosis* (271861) |

  Lo que queda para este cambio: el orden del servicio no sirve para elegir "la"
  enfermedad (de ahí D8), y nadie llama al cliente desde el pipeline.

## Goals / Non-Goals

**Goals:**
- Que el Agente 05 funcione hoy sobre el reporte del debate y mañana sobre el consenso del
  Árbitro cambiando solo el adaptador de entrada y el orden en el router.
- Que ninguna falla externa (ClinicalTrials.gov, Orphanet, Groq) rompa `POST /api/analyze` y
  que el reporte diga qué falló.
- Que la búsqueda nunca sea peor que la actual: la consulta base se mantiene.
- Que todo lo que excluye ensayos sea determinista y testeable sin red.

**Non-Goals:**
- Determinar elegibilidad real ni recomendar inscripción.
- Estado de hipótesis y reglas EBM (#54), síntesis del Árbitro (#52), Sintetizador (#62).
- Arreglar el cliente de Orphanet: ya se hizo en `fix/s4-cliente-orphanet` (commit `41828a8`).
- Traer genes desde Orphanet: la ORPHAcodes API no los expone y `get_genes()` levanta
  `OrphanetGenesNoDisponibles`. Están en Orphadata, otro host y otro producto; va en
  tarjeta aparte y el Agente 05 no depende de ellos.
- Filtrar ensayos por país: la sede en Argentina ordena, nunca excluye.
- Agregar edad/sexo estructurados a `PICOSynthesis`.

## Decisions

### D1. Agente híbrido: el LLM traduce y evalúa, lo determinista busca, filtra y valida

```
TrialNavigationInput
   │
   ├─(1) LLM: hipótesis (es) → términos en inglés + sinónimos ──── fallback: sin términos
   │         └─ saneamiento determinista de cada término
   ├─(2) ClinicalTrials.gov: búsqueda base (igual a hoy) + 1 consulta por hipótesis
   │         (sinónimos si el principal da 0) ──────────────────── fallback por consulta
   │         RECRUITING + NOT_YET_RECRUITING, etiquetados (D14)
   ├─(3) Orphanet: ApproximateName por término → coincidencia EXACTA ── fallback: sin marcas
   ├─(4) Filtros duros edad/sexo (locales) + dedupe por NCT + tope 10
   ├─(5) LLM: compatibilidad alta/media/baja + criterios a verificar ─ fallback: sin_evaluar
   │         └─ validación: solo NCT IDs enviados, etiquetas del enum
   └─(6) Orden: compatibilidad → Argentina → ya reclutando → descubrimiento (D15)
   ▼
TrialNavigationResult(trials, rare_diseases, summary)
```

- **Por qué LLM en (1)**: las hipótesis llegan en español y como oraciones; ClinicalTrials.gov
  indexa en inglés (el fix `fix/s4-ensayos-idioma` midió 0 resultados en español). Sin este
  paso las hipótesis no se pueden usar para buscar y el agente sería el paso 6 actual.
- **Por qué LLM en (5)**: los criterios de inclusión/exclusión son texto libre; ningún parser
  determinista razonable los contrasta contra el perfil.
- **Por qué determinista en (2)–(4)**: lo que quita un ensayo de la vista del médico tiene que
  ser auditable y reproducible. El backlog (nota 16) midió 9 de cada 10 PMIDs alucinados por
  los agentes: el LLM etiqueta, nunca excluye, y su salida se valida contra lo que se le envió.
- **Alternativa descartada — 100 % determinista**: no traduce hipótesis ni lee criterios; la
  "compatibilidad" quedaría reducida a edad/sexo, que ya cubre (4).
- **Alternativa descartada — el LLM decide todo (incluso exclusiones)**: inauditable, no
  testeable sin red y expuesto a alucinar NCT IDs.
- **Alternativa descartada — una sola llamada al LLM**: la evaluación necesita los ensayos que
  resultan de la búsqueda, y la búsqueda necesita los términos: son dos momentos distintos.

### D2. El Agente 05 hereda de `BaseAgent` pero no participa del debate

`TrialNavigatorAgent(BaseAgent)` con `AGENT_ID = "05"`, `AGENT_NAME = "Navegador de Ensayos"`,
`MODEL = GROQ_MAIN`. Entrada pública: `async def navigate(input) -> TrialNavigationResult`.
Las dos llamadas usan `self._call_llm()` vía `asyncio.to_thread`; `SYSTEM_PROMPT` fija rol y
reglas (no diagnosticar, no afirmar elegibilidad, solo JSON) y cada mensaje de usuario define
el formato de su tarea, igual que hacen `critique()`/`revise()` en la base. `run()` se
implementa lanzando `NotImplementedError("El Agente 05 no participa del debate: usar navigate()")`.

- **Alternativa descartada — `run()` devolviendo un `AgentOutput` sin hipótesis**: el contrato
  de `AgentOutput` es "hipótesis de un agente"; `parse_hypotheses` exige al menos una.
- **Alternativa descartada — separar `BaseAgent` en base LLM + `DebateAgent`**: es el diseño
  correcto cuando existan 04, 05 y 06 (ninguno debate), pero toca `base_agent.py` mientras
  #51/#52/#62 se planifican en paralelo. **Decidido con el equipo**: se difiere hasta que
  04 y 06 existan, y será un refactor propio que no altera este contrato.

Las 2 llamadas extra a Groq por análisis están **aceptadas por el equipo**, con el
presupuesto de tokens de D11 y el fallback de cada paso.

### D3. Contrato de entrada neutral y adaptador único

Modelos nuevos en `backend/models/trial.py`:

- `TrialCandidate(text, priority, evidence_level, status: str | None = None)`
- `PatientDemographics(age_years: float | None, sex: "MALE" | "FEMALE" | None)`
- `TrialNavigationInput(condition_en, biomarker_terms, demographics, eligibility_profile, candidates)`
  — `eligibility_profile` se arma con campos PICO (`patient_profile`, `chief_complaint`,
  `relevant_history`, `negative_findings`, `current_treatments`, `genetic_findings`), nunca con
  `raw_text` ni `clinical_narrative`.

`pipeline/trial_matching.build_navigation_input(case, hypotheses, statuses=None)` es el único
lugar que sabe de dónde vienen las hipótesis. `statuses` es un mapa texto → estado (mismo
criterio de clave por texto que ya usa `report_builder._rank_hypotheses`). Hoy el router lo
llama con `final_report.hypotheses`; con el Árbitro, con su consenso y el mapa de estados.

- **Alternativa descartada — que el agente reciba `Report`**: lo acopla al debate; el día que
  el 04 devuelva otro tipo hay que tocar el agente.
- **Alternativa descartada — que reciba `RankedHypothesis`**: obliga a correr después de
  `build_export`, invirtiendo el pipeline y atándolo al contrato que va a reemplazar el 06.

### D4. Posición en el pipeline: hoy en paralelo con la verificación

```python
nav_input = build_navigation_input(case_with_pico, final_report.hypotheses)
navigation, verifications = await asyncio.gather(
    _navigate_trials_safe(nav_input),        # nunca lanza
    verify_report_sources(final_report),
)
```

Ambos dependen solo del reporte final del debate y ninguno usa Groq a la vez que el otro
(la verificación usa PubMed), así que se ahorra latencia sin competir por el cupo de tokens.
`_navigate_trials_safe` es la red de seguridad del router: ante una excepción no prevista
devuelve un `TrialNavigationResult` vacío con `estado_clinicaltrials="no_disponible"` y loggea
solo el tipo. Cuando exista el Árbitro, el orden pasa a ser `árbitro → navigate(consenso)`.

Se elimina el reemplazo `condition_en or chief_complaint`: el motivo de consulta en español
da 0 resultados y es texto del caso viajando a una API externa.

### D5. Contrato de exportación aditivo, siguiendo el precedente de `Source.verified`

- `ClinicalTrial` suma `compatibility="sin_evaluar"`, `compatibility_rationale=None`,
  `criteria_to_verify=[]`, `related_hypotheses=[]`, `matched_terms=[]`.
- `StructuredReport` suma al final `rare_diseases: list[RareDiseaseMatch] = []` y
  `trial_search: TrialSearchSummary | None = None`.
- `build_export(...)` suma al final `navigation: TrialNavigationResult | None = None`; `trials`
  sigue siendo el parámetro de los ensayos, así los tests y demos actuales no cambian.

`trial_search` es **nullable** a propósito, a diferencia de `verification`: `None` significa
"reporte anterior al Agente 05", y es la señal que usan frontend y PDF para renderizar como
hoy. Un default con estados en `sin_consulta` haría que un reporte viejo con ensayos afirme que
no se consultó nada. Los campos del resumen van en español como `VerificationSummary`
(`estado_clinicaltrials`, `excluidos_por_edad`, …); los de `ClinicalTrial`, en inglés como el
resto del modelo, con valores en español como `RankedHypothesis.status`.

- **Alternativa descartada — lista paralela `trial_matches: list[TrialMatch]`**: duplica los
  ensayos, obliga al frontend a cruzar dos listas y crea dos fuentes de verdad.

### D6. Edad y sexo por reglas sobre `patient_profile`, conservadoras

`parse_patient_demographics(profile)`:
- Edad: patrones anclados al paciente, en orden (`(\d{1,3}) años de edad`, `edad:? (\d{1,3})`,
  `(paciente|hombre|mujer|varón|masculino|femenino)` seguido a ≤ 25 caracteres de `(\d{1,3}) años`),
  descartando menciones seguidas de "de evolución". Valores > 120 o ninguna coincidencia → `None`.
- Sexo: `masculino|varón|hombre` → MALE; `femenino|mujer` → FEMALE; ambos o ninguno → `None`.
- Edades de ensayo: `"N Years|Months|Weeks|Days"` → años; cualquier otra forma → `None`.

Dato faltante o ambiguo nunca excluye: el error esperable es mostrar un ensayo de más, no
esconder uno compatible. Edad y sexo no salen del proceso: se filtra localmente.

- **Alternativa descartada — agregar `age_years`/`sex` a `PICOSynthesis`**: más limpio a futuro,
  pero cambia el prompt PICO, sus demos y un modelo compartido por todo el pipeline.
- **Alternativa descartada — que el LLM extraiga edad/sexo**: el filtro dejaría de ser
  determinista y reproducible.
- **Alternativa descartada — mandar edad/sexo como filtros a ClinicalTrials.gov**: expone datos
  demográficos del paciente a una API externa sin necesidad.

### D7. Saneamiento de términos antes de cualquier API científica

`sanitize_term(term) -> str | None` aplica la regla de la spec: regex
`^[A-Za-z0-9][A-Za-z0-9 ,'()/+\-]{1,79}$`, ≤ 8 palabras y ningún token en
`{patient, patients, year, years, yo, old, aged, male, female, man, woman, men, women}`.
Se aplica a condición, sinónimos y biomarcadores. Descarta, no corrige: un término "arreglado"
por código podría conservar justo la parte sensible. Como efecto colateral, los anticuerpos
extraídos en español (`anti-gangliósido GM1`) dejan de enviarse; hoy suman ruido a una búsqueda
que la API combina con AND.

### D8. Orphanet: coincidencia exacta normalizada, precisión antes que cobertura

`normalize_disease_name`: minúsculas, puntuación y guiones → espacio, espacios colapsados,
conjunto de palabras (orden indiferente). Una hipótesis se marca si el nombre preferido de
alguna candidata devuelta es igual a su término principal o a un sinónimo. Se consulta el
término principal y, si no hay coincidencia, cada sinónimo; se compara contra todas las
candidatas (la respuesta puede traer cientos, comparar es barato). El prompt de planificación
pide incluir el nombre preferido de Orphanet como sinónimo cuando la condición sea una
enfermedad rara, lo que sube la cobertura sin aflojar el criterio.

- **Alternativa descartada — tomar el primer resultado**: medido, marca una neuropatía axonal
  del adulto como *enfermedad neonatal letal*. Etiquetar mal una hipótesis es peor que no marcarla.
- **Alternativa descartada — similitud por inclusión/Jaccard**: el mismo falso positivo pasa
  cualquier umbral de inclusión (todas las palabras del término están en el nombre).
- **Alternativa descartada — que el LLM elija entre candidatas**: tercera llamada al LLM con el
  cupo ya castigado por el debate. Es la mejora natural si la cobertura medida resulta baja.

Qué aporta Orphanet al reporte: código ORPHA y enlace a la ficha de orpha.net (centros
expertos, asociaciones, medicamentos huérfanos) para las hipótesis que corresponden a una
enfermedad rara catalogada. No agrega términos nuevos de búsqueda (con coincidencia exacta el
nombre preferido ya es uno de los términos) ni cambia la compatibilidad.

### D9. Cliente Orphanet: contrato que consume el agente (ya implementado)

El arreglo del cliente salió de este cambio y se hizo en `fix/s4-cliente-orphanet`. Lo que
el Agente 05 puede dar por dado:

- `search(name)` pega a `GET {BASE}/ApproximateName/{quote(name, safe="")}` y devuelve
  `RareDisease` con `orpha_code`, `preferred_term`, sinónimos, `definition` (`""` cuando la
  API responde "None available") y el enlace a orpha.net.
- 404 con cuerpo `"Query not found"` → `[]` (sin coincidencias, no es error). Otro 404 o 401
  → `ExternalApiError` sin reintento. Timeout, conexión y 5xx → reintento y luego
  `ApiUnavailableError` (subclase de `ExternalApiError`, `external/rate_limiter.py`).
- **El cliente ya aplica `orphanet_limiter` internamente**: el agente MUST NOT volver a
  aplicarlo, o duplica la espera. El agente sí envuelve las llamadas en `orphanet_breaker`,
  que el cliente no conoce.
- `get_genes()` levanta `OrphanetGenesNoDisponibles`: el agente no lo llama.

Lo único que decide este cambio es el fallback: el agente traduce cualquiera de esas
excepciones a `estado_orphanet` y sigue con los ensayos.

**Credencial**: la API responde 200 sin `apiKey` (10 de 10 llamadas medidas). El cliente
manda `ORPHANET_API_KEY` si está definida y, si no, un valor por defecto que la API acepta.
El agente **consulta Orphanet siempre**, haya o no credencial en el entorno. Un 401
intermitente cae en `no_disponible` como cualquier otra falla.

- **Alternativa descartada — exigir `ORPHANET_API_KEY` y saltear Orphanet sin ella**: era el
  diseño original, escrito cuando creíamos que la API devolvía 401 sin clave. Con la medición
  corregida, apagaría una función que anda en todos los entornos del equipo, ninguno de los
  cuales tiene la variable definida.

### D14. Ensayos que todavía no reclutan

`clinical_trials.search()` hoy recibe `recruiting_only: bool` y solo sabe filtrar por
`RECRUITING` o no filtrar nada. Pasa a recibir los estados a consultar
(`statuses: Sequence[str] = ("RECRUITING",)`), que se mandan a `filter.overallStatus`
separados por `|` como acepta la API v2. El Agente 05 consulta
`("RECRUITING", "NOT_YET_RECRUITING")`.

El default deja las llamadas actuales igual, así que `search_by_biomarkers` y los tests
vigentes no cambian. El estado ya viaja en `ClinicalTrial.status`, así que no hace falta un
campo nuevo: la vista y el PDF etiquetan "aún no recluta" cuando vale `NOT_YET_RECRUITING`.

- **Por qué incluirlos**: un ensayo que abre en tres meses es accionable para el médico, que
  puede contactar al equipo investigador. Excluirlo esconde información útil; la etiqueta
  evita que se lea como "está reclutando hoy".
- **Alternativa descartada — consultar todos los estados y filtrar localmente**: trae ensayos
  terminados y suspendidos que gastan lugar en el tope de 10 y tokens en la evaluación.

### D15. Orden del resultado: compatibilidad, después Argentina

`compatibilidad (alta, media, baja, sin_evaluar) → sede en Argentina → ya reclutando →
orden de descubrimiento`. La sede sale de `ClinicalTrial.locations`, que ya trae la lista de
países; "Argentina" se compara normalizado.

- **Por qué la compatibilidad va primero**: es lo que el médico necesita arriba. Un ensayo
  local poco compatible por encima de uno muy compatible del exterior invierte el criterio
  clínico por uno logístico.
- **Argentina ordena, nunca filtra**: es una preferencia de despliegue del equipo, no un dato
  del paciente. Ningún ensayo se pierde por su sede, y nada del paciente viaja a la API.
- **Alternativa descartada — Argentina primero de todo**: la evaluó el equipo y se descartó
  por lo anterior.
- **Alternativa descartada — país como variable de entorno**: configurable es más general,
  pero hoy hay un solo despliegue y una constante es más simple de testear. Si aparece otro
  país, el cambio es acotado.

### D10. Consultas externas: reuso de `rate_limiter`, paralelismo acotado

Cada consulta a ClinicalTrials.gov corre como `asyncio.to_thread(clinical_trials.search, …)`
dentro de `clinical_trials_limiter` y `clinical_trials_breaker`. La búsqueda base y las
consultas de cada candidata corren con `asyncio.gather(..., return_exceptions=True)`; los
sinónimos de una misma candidata, en serie. Presupuesto: ≤ 1 + 3 × 3 consultas a
ClinicalTrials.gov (5 resultados por candidata, 10 en la base) y ≤ 3 × 3 a Orphanet.
`estado_*` = `ok` si todas respondieron, `parcial` si alguna, `no_disponible` si ninguna.

### D11. Presupuesto del LLM y validación de su salida

- Planificación: solo textos de hasta 3 hipótesis y `condition_en`. Salida
  `{"terms": [{"candidate": 1, "condition_en": "...", "synonyms_en": ["..."]}]}`.
- Evaluación: `eligibility_profile` + hasta 10 ensayos con título, condiciones, rango etario,
  sexo y `eligibility_criteria` truncado a 1500 caracteres (~6k tokens de entrada, bajo el
  límite de 12k TPM de Groq). Salida `{"evaluations": [{"nct_id", "compatibility",
  "rationale", "criteria_to_verify"}]}`; `rationale` se trunca a 600 caracteres y
  `criteria_to_verify` a 5 ítems de 200 caracteres.
- Validación de la salida según la spec (NCT IDs desconocidos descartados y contados,
  etiquetas fuera del enum → `sin_evaluar`, duplicados: gana el primero).

### D12. Logs sin texto clínico

Un helper `_log_fallback(paso, exc)` imprime a stderr
`[NEXUS] Agente 05 — <paso>: fallback (<TipoDeExcepción>)` y, como mucho, conteos. Nunca
`str(exc)`: `extract_json` mete la respuesta del LLM en el mensaje y los errores HTTP pueden
repetir el término consultado. El print actual del router (`{exc}`) se reemplaza por el mismo
criterio.

### D13. Frontend y PDF

- `types.ts`: campos nuevos opcionales en `ClinicalTrial`; `RareDiseaseMatch`,
  `TrialSearchSummary`; `rare_diseases?` y `trial_search?: TrialSearchSummary | null` en
  `StructuredReport`.
- `EnsayosTab` recibe el reporte completo. Si `trial_search` es nulo, render idéntico al actual.
  Si no: aviso de estado (ClinicalTrials.gov u Orphanet no disponible o parcial), aclaración
  orientativa, bloque "Enfermedades raras relacionadas (Orphanet)", y por ensayo badge de
  compatibilidad (alta verde, media ámbar, baja gris, sin evaluar neutro), fundamento,
  criterios a verificar e hipótesis relacionadas. `EmptyState` distingue "no se encontraron"
  de "no se pudo consultar". Se mantienen las 5 tabs.
- Etiquetas nuevas por ensayo (D14/D15): "Aún no recluta" cuando `status` es
  `NOT_YET_RECRUITING`, y "Sede en Argentina" cuando `locations` la incluye. La de
  reclutamiento es una advertencia, no un badge de calidad: el médico tiene que ver de un
  vistazo que ese ensayo todavía no abrió.
- `analyzing/page.tsx`: el paso "Generación del reporte" pasa a nombrar al Agente 05
  (solo texto; la vista no recibe eventos reales del backend).
- `pdf_exporter._clinical_trials`: mismas piezas; la línea de la portada sigue contando ensayos.

## Risks / Trade-offs

- [Cupo de Groq agotado por el debate → los reintentos de `_call_llm` (8/20/40 s) suman
  latencia] → Solo 2 llamadas, entradas truncadas, fallback a `sin_evaluar`; el demo mide la
  latencia real sobre el caso base.
- [Coincidencia exacta con baja cobertura en Orphanet] → Prompt que pide el nombre preferido
  de Orphanet como sinónimo; el demo registra cuántas hipótesis se marcaron; si es baja, la
  selección por LLM entre candidatas validadas es un cambio posterior acotado.
- [El LLM etiqueta mal la compatibilidad] → Nunca excluye; criterios a verificar explícitos;
  aclaración fija en vista y PDF; los filtros que excluyen son deterministas.
- [Reglas de edad/sexo que no reconocen una redacción] → Fallan hacia "no filtrar"; tests con
  redacciones reales de la síntesis PICO del caso base.
- [El cuerpo `"Query not found"` de Orphanet cambia] → Test con fixture de ambos 404; el demo
  contra la API real lo detecta; en el peor caso Orphanet reporta `no_disponible`, no rompe nada.
- [Breakers globales de `rate_limiter` con estado compartido entre tests] → Fixture que llama
  `reset()` antes de cada test del agente.
- [Conflictos de merge] → #54 toca `schemas.py` y `report_builder.py`: acá solo se agregan
  campos y un parámetro al final, sin tocar `RankedHypothesis` ni `_rank_hypotheses`. #52
  (Árbitro) va a tocar el tramo del router posterior al debate: conflicto textual chico y
  esperado, que resuelve el orden `árbitro → navigate`. #51 no se cruza.
- [Más consultas a ClinicalTrials.gov por análisis (hasta 10)] → Limiter de 10 req/s y
  circuit breaker existentes.

## Migration Plan

1. Sin migración de datos: no hay persistencia.
2. Backend y frontend se pueden desplegar en cualquier orden: el frontend viejo ignora los
   campos nuevos y el nuevo renderiza como antes cuando `trial_search` es nulo.
3. `ORPHANET_API_KEY` es opcional: la API responde sin credencial y el reporte informa el
   estado real de la consulta (`ok`, `parcial` o `no_disponible`).
4. Rollback: revertir el paso 6 del router a `search_by_biomarkers` (la función se conserva);
   los campos nuevos quedan con sus defaults.

## Open Questions

- ¿El Agente 06 va a consumir `trial_search` para redactar la sección de ensayos? Se define en #62.
- ¿Integrar Orphadata (`api.orphadata.com/rd-associated-genes/orphacodes/{code}`) para cruzar
  los genes del caso con la enfermedad rara marcada? Tarjeta aparte; no afecta este contrato.

Resueltas por el equipo el 2026-09-15, ahora en Decisions: incluir `NOT_YET_RECRUITING` (D14),
ordenar por sede en Argentina (D15), aceptar las 2 llamadas extra a Groq y diferir la
separación de `BaseAgent` hasta que existan los agentes 04 y 06 (D2).
