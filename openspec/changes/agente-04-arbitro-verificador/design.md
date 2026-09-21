## Context

Ver `proposal.md` — Why para la motivación. Lo que importa para el diseño es el estado
actual del código:

- `pipeline/debate.py:run_debate()` consolida a mano:
  `final_hypotheses = [h for o in outputs_r4.values() for h in o.hypotheses]`, y
  `_detect_divergences()` decide si una hipótesis criticada "se mantuvo" comparando
  conjuntos de palabras con un umbral de 0,6.
- `pipeline/verification.py` ya verifica en batch (un solo `esummary` con todos los
  PMIDs) y devuelve `dict[str, SourceVerification]` con clave `source_key(source)`.
- `pipeline/evidence.py` ya expone `classify_hypothesis()` y `prioritize()`, ambas
  deterministas y sin red. La spec `clasificacion-evidencia-ebm` está vigente.
- `report_builder._rank_hypotheses()` arma hoy `supporting_agents` con un índice
  `dict[texto exacto → agentes]`. Como cada agente redacta distinto, ese índice casi
  siempre devuelve un solo agente: el respaldo múltiple que el reporte muestra hoy es
  un artefacto de coincidencia literal de strings.
- `rag/retriever.py:PubMedRetriever.search()` devuelve `list[RetrievedArticle]` con
  PMID, título, revista y excerpt. `orchestrator._enrich_context_with_rag()` llama a
  `get_context_for_agent()`, que devuelve sólo el string ya formateado: los objetos se
  pierden.
- `api/router.py` corre hoy el Agente 05 y la verificación con un `asyncio.gather`.
- `base_agent.py:92` construye `Source(**s)` sin filtrar.

Restricción de plataforma: Groq tier gratuito, 12k TPM. Cada llamada extra compite con
las 11 que ya hace el pipeline (3 en Ronda 1, 3+3+3 en el debate, 2 del Agente 05).

## Goals / Non-Goals

**Goals:**

- Que el Árbitro sea un agente más (`BaseAgent`), con toda la decisión dura fuera del
  LLM y reutilizando `verification.py` y `evidence.py` sin duplicar lógica.
- Que la agrupación sea auditable: poder mostrar en la demo qué hipótesis se agruparon
  con cuáles y por qué.
- Que la recitación produzca un número comparable antes/después, que es el dato de
  tesis: ¿mejora la calidad de las citas cuando se les pone la literatura real delante?
- Que ninguna falla del Árbitro rompa `POST /api/analyze`.

**Non-Goals:**

- No se reescribe el motor de debate. Las Rondas 2–4 quedan como están; el Árbitro
  consume su salida.
- No se implementa el Agente 06. El Árbitro produce datos estructurados; la redacción
  del reporte final sigue en `report_builder.py` + `pdf_exporter.py`.
- No se cambia el criterio de verificación de una fuente (`_MIN_TITLE_MATCH`, el
  containment de tokens): se reutiliza tal cual.
- No se persiste nada entre sesiones. El consenso vive en la request.

## Decisions

### D1 — Agrupar con el LLM, verificar la agrupación con código

**Decisión.** El LLM recibe las N hipótesis numeradas y devuelve grupos como listas de
índices. El código valida esa partición antes de usarla: que todo índice exista, que
ninguno se repita y que la unión cubra las N. Los índices faltantes se agregan como
grupos propios; los repetidos se asignan al primer grupo que los reclamó.

**Por qué.** Decidir si "Amiloidosis ATTR hereditaria" y "Variante patogénica en TTR
con compromiso de fibra fina" son la misma hipótesis es exactamente lo que un LLM hace
bien y una heurística de strings hace mal — lo demuestra el `supporting_agents` actual,
que casi nunca agrupa nada. Pero devolver índices en vez de texto hace que el modelo no
pueda reescribir ni inventar hipótesis: el texto sale siempre del objeto original.

**Alternativas.** (a) Similitud de embeddings sobre los textos: no hay umbral
defendible sin medir, y el hallazgo C del backlog ya documenta que los embeddings del
proyecto no manejan la negación — "descartar ATTR" y "confirmar ATTR" quedarían
cerca. (b) Seguir con solapamiento de palabras: es lo que hay hoy y no funciona.

### D2 — Índices, no texto, en toda la interfaz con el modelo

**Decisión.** Las tres llamadas al LLM del Árbitro (agrupar, redactar veredictos,
recitar) reciben elementos numerados y devuelven referencias por número. Ninguna salida
del modelo se usa como identidad de nada.

**Por qué.** Es la misma guarda que el Agente 05 aplica con los NCT IDs, que en la
corrida real dio 0 evaluaciones descartadas. Reduce el problema de "el modelo inventó
algo" a una validación de rango de enteros.

### D3 — El texto representativo del grupo se elige por regla, no por el modelo

**Decisión.** Dentro de un grupo, el texto representativo es el de la hipótesis con
mejor estado bibliográfico; a igual estado, la de mejor nivel efectivo; a igual nivel,
la del agente de menor ID. El modelo redacta el *fundamento consolidado* y el
*veredicto*, no el enunciado de la hipótesis.

**Por qué.** El enunciado es lo que el médico va a leer como la hipótesis del sistema.
Si lo redacta el LLM, puede introducir matices que ningún agente sostuvo y que nadie
verificó. Eligiendo un enunciado existente, cada hipótesis del reporte es trazable a un
agente concreto.

**Trade-off.** El enunciado elegido puede ser menos elegante que una síntesis
redactada. Se acepta: la trazabilidad vale más que la prosa.

### D4 — Las contradicciones salen de las críticas, no de una llamada nueva

**Decisión.** `_detect_divergences()` se reemplaza por lógica sobre los objetos
`Critique` que la Ronda 2 ya produjo. Una crítica de severidad HIGH cuenta como
contradicción abierta contra el grupo que contiene la hipótesis criticada, salvo que el
agente criticado haya modificado esa hipótesis entre la Ronda 1 y la Ronda 4.

La hipótesis criticada se localiza por el mismo agrupamiento de D1: se le pide al
modelo que mapee cada crítica a un grupo, con la misma validación por índices.

**Por qué.** Las críticas ya están estructuradas (`target_agent_id`, `severity`,
`critique_text`), con autor y severidad. Volver a pedirle al LLM que "encuentre
contradicciones" sería tirar ese trabajo y sumar una llamada.

**Cómo se detecta que el agente cedió.** Comparación de conjuntos de tokens entre la
hipótesis del agente en Ronda 1 y en Ronda 4, con el mismo criterio de containment que
ya usa `verification._title_match_score()`. Es una heurística y se documenta como tal;
el costo de equivocarse es reportar una contradicción de más, que es el lado seguro.

### D5 — Conservar los `RetrievedArticle` en el `Report`

**Decisión.** `_enrich_context_with_rag()` pasa a devolver `(contexto, articulos)` y los
artículos viajan en `Report.retrieved_articles`. `get_context_for_agent()` queda como
está para no romper a sus otros usuarios.

**Por qué.** Sin esto no hay recitación posible (no hay conjunto contra el cual validar
PMIDs) ni métrica de solapamiento. Es el cambio que convierte el hallazgo "los agentes
ignoran el RAG" de anécdota en número reportado.

**Alternativa descartada.** Volver a correr la búsqueda semántica desde el Árbitro:
duplicaría trabajo y podría devolver otros artículos que los que los agentes vieron, con
lo cual la métrica de solapamiento mediría otra cosa.

### D6 — Recitación por agente, no por hipótesis

**Decisión.** Las hipótesis sin respaldo se agrupan por agente de origen y se hace una
llamada por agente con todas sus hipótesis a recitar. Máximo tres llamadas.

**Por qué.** Una llamada por hipótesis serían hasta nueve llamadas con el mismo bloque
de literatura repetido en cada prompt — inviable con 12k TPM.

**Qué recibe.** El agente recibe sus hipótesis a recitar con el motivo (qué pasó con
cada PMID que citó: inexistente, o discordante con el título real) más los artículos
recuperados. Decirle *por qué* falló su cita es lo que le da la chance de corregir.

**Dónde vive el método.** En `BaseAgent`, como `critique()` y `revise()`. Con una
salvedad: `GenomicsSpecialistAgent` sobreescribe hoy `run()`, `critique()` y `revise()`
(`agent_02_genomics.py:84,99,101`) para enriquecer el contexto con el perfil genómico y
aplicar su guarda anti-invención sobre la salida. La recitación necesita el mismo
override, o el Agente 02 recita sin contexto genómico y sin guarda — justo el agente
cuyas hipótesis son las más fáciles de inventar.

### D7 — Serializar el pipeline y absorber la latencia

**Decisión.** `router.py` pasa de `gather(navegación, verificación)` a
`verificación → arbitraje → navegación`. `build_navigation_input()` recibe las
hipótesis de consenso.

**Por qué.** Decisión del equipo (ver proposal). El Agente 05 buscando sobre 4 hipótesis
consolidadas en vez de 9 con duplicados reduce el ruido que documenta la limitación del
Agente 05 en el backlog.

**Costo.** ~5 min → ~7 min estimados. Para la demo del profesor hay respaldo grabado en
`output/`, así que la latencia no bloquea la presentación.

### D8 — `ConsensusHypothesis` envuelve a `Hypothesis`, no la reemplaza

**Decisión.** `ConsensusHypothesis` contiene la `Hypothesis` representativa, la lista de
las agrupadas, los agentes de respaldo y refutación, las contradicciones y el veredicto.
`evidence.prioritize()` sigue recibiendo `Sequence[Hypothesis]`.

**Por qué.** `evidence.py` está especificado y testeado contra `Hypothesis`. Cambiarle
la firma obligaría a tocar una spec vigente por una razón de tipos, no de
comportamiento. El único cambio real en `evidence.py` es el criterio de orden nuevo, que
entra como parámetro opcional (`support_count`) con default 1 — así un reporte sin
arbitraje ordena exactamente igual que hoy, que es lo que exige la spec modificada.

### D9 — El saneamiento del hallazgo G va en `parse_hypotheses()`

**Decisión.** `Source(**s)` pasa a construirse desde una whitelist de campos declarados
por el agente (`pmid`, `title`, `journal`, `year`, `url`). Los campos de verificación se
ignoran silenciosamente si vienen.

**Por qué ahí.** Es el único punto por el que entra una `Source` desde un LLM: lo cubre
para los agentes 01, 02, 03 y para la recitación, sin tocar a cada agente.

**Por qué ignorar en vez de fallar.** Un agente que declara `verified: true` no emitió
un JSON inválido; emitió un campo que no le corresponde. Hacer fallar el parseo tumbaría
la hipótesis entera por un campo de más, y la regla del proyecto es no descartar
hipótesis.

## Risks / Trade-offs

- **El agrupamiento del LLM junta dos hipótesis que no son la misma** → El reporte
  perdería una hipótesis distinta detrás del enunciado de otra. Mitigación: el consenso
  conserva las hipótesis agrupadas y el reporte puede mostrarlas; el demo
  (`scripts/demo_agente04.py`) imprime la partición completa para inspección. Es el
  riesgo que justifica que la agrupación sea visible y no implícita.

- **La recitación no mejora nada** → Tres llamadas extra de LLM por análisis para un
  resultado nulo. Mitigación: es un resultado igualmente publicable — "ofrecerles la
  literatura real no alcanza para que citen bien" es un hallazgo de tesis, no un
  fracaso. El número se reporta en cualquier caso.

- **La recitación mete una cita verificada que no sostiene la hipótesis** → Un PMID del
  conjunto ofrecido, con su título correcto, puede igualmente no respaldar lo que la
  hipótesis afirma. La verificación confirma que la cita es real, no que sea pertinente.
  Mitigación: la limitación ya está documentada en `evidence.py` ("la verificación
  confirma que el PMID corresponde al título citado, no que el artículo sostenga la
  hipótesis"); se repite en el veredicto del Árbitro y en la tesis.

- **Presión de tokens en Groq** → +2 llamadas fijas y hasta +3 de recitación sobre las
  11 actuales, con 12k TPM. Mitigación: el bloque de literatura se acota a los artículos
  ya recuperados (5 como máximo hoy) y el prompt de agrupación manda enunciados
  truncados, no fundamentos completos. `_call_llm()` ya reintenta ante 429 con backoff.

- **Colisión con la tarjeta #78 de Fede** → Ambos tocan `pdf_exporter.py`. Mitigación:
  la sección del PDF de este cambio se hace al final, después de que #78 esté mergeada,
  o se coordina en el momento. Está anotado en tasks.md.

- **Se rompe la comparabilidad con las corridas grabadas** → Los artefactos de
  `output/corrida_agente05/` quedan con un contrato viejo. Mitigación: el contrato es
  aditivo y `arbitration: null` los deja válidos; igual conviene regenerar la corrida de
  respaldo de la demo después de mergear.

## Migration Plan

No hay datos persistidos que migrar (`chroma_db/` es descartable y los reportes no se
guardan). El contrato JSON es aditivo, así que el frontend puede mergearse antes o
después del backend sin romperse.

Orden sugerido: modelos y saneamiento (G) → consenso determinista → agente → recitación
→ router → reporte → frontend/PDF. Cada bloque deja la suite verde, así que se puede
frenar en cualquiera de esos puntos.

Rollback: revertir el merge. Al ser aditivo, un reporte generado con el Árbitro sigue
siendo legible por el código anterior salvo por los campos nuevos, que ignora.

## Open Questions

- ¿El reporte muestra las hipótesis agrupadas detrás de cada hipótesis de consenso, o
  sólo el enunciado representativo con la lista de agentes? Afecta sólo a la vista y al
  PDF, no al contrato ni a la lógica: se decide al implementar esa tarea, viendo cuánto
  ocupa en pantalla.
- Umbral de containment para decidir que un agente "cedió" ante una crítica (D4). Se
  arranca con el 0,6 que ya usa `_detect_divergences()` y se ajusta con lo que se vea en
  la corrida real; no cambia ninguna spec.
