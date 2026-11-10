# Resultados, evaluación y limitaciones

Este capítulo describe cómo se evaluó NEXUS, qué resultados se midieron, qué problemas
aparecieron durante el desarrollo y cómo se corrigieron, cuáles son las limitaciones del
sistema en su estado actual y qué trabajo queda planteado a futuro.

Todas las cifras provienen de registros del repositorio (`.claude/CLAUDE.md`,
`.claude/backlog.md`, `.claude/traspaso.md` y los cambios archivados de OpenSpec en
`openspec/changes/archive/`). Cada cifra se acompaña de su fecha y su fuente. Cuando dos
fuentes no coinciden, se informan ambas.

NEXUS no emite diagnósticos: genera hipótesis de investigación para el médico responsable.
La evaluación que sigue mide la calidad de esas hipótesis y de su respaldo bibliográfico, no
la exactitud de un diagnóstico.

---

## 1. Método de evaluación

### 1.1 Caso de prueba base

Todas las corridas se hicieron sobre un único caso de prueba anonimizado: una **neuropatía
axonal sensitivomotora en un paciente masculino de 42 años**. No contiene datos de un
paciente real. Es el mismo caso que usan los tests de la suite y los scripts de demostración.

### 1.2 Criterios de calidad del reporte

Los criterios están implementados en `backend/pipeline/calidad.py` (tarjeta #59, cambio
OpenSpec `criterios-calidad-reporte`, spec vigente en
`openspec/specs/criterios-calidad-reporte/spec.md`). La función `evaluar()` es pura y
determinista: no usa red ni modelo de lenguaje, y el mismo reporte produce siempre el mismo
resultado. No forma parte del pipeline: es una herramienta de validación del equipo y no se
muestra al médico.

La evaluación produce uno de tres veredictos:

| Veredicto | Condición |
|-----------|-----------|
| `no_evaluable` | El reporte se generó en modo mock, o la verificación bibliográfica quedó `parcial` o `no_disponible`, o el reporte no informa el estado de la verificación. Las métricas se calculan igual. |
| `no_cumple` | El reporte es evaluable pero falla un requisito de consistencia o una métrica. |
| `cumple` | El reporte es evaluable, cumple los requisitos de consistencia y las tres métricas. |

Los requisitos de consistencia son tres: el reporte tiene al menos una hipótesis, lleva el
aviso de que NEXUS no emite diagnósticos, y ninguna hipótesis tiene nivel de evidencia
efectivo I o II sin al menos una fuente verificada.

Las tres métricas, una por dimensión de calidad, son:

| Dimensión | Métrica | Cálculo | Umbral |
|-----------|---------|---------|--------|
| Cobertura | Cobertura de respaldo | hipótesis respaldadas / total de hipótesis | ≥ 0,50 |
| Fuentes verificadas | Precisión de citas | fuentes verificadas / (verificadas + discordantes + inexistentes) | ≥ 0,70 |
| Nivel de evidencia | Sobredeclaración | hipótesis con nivel efectivo por debajo del declarado / total | ≤ 0,50 |

Los umbrales viven en una única tabla versionada, con la versión **`2026-11-provisional`**
(`backend/pipeline/calidad.py:46-51`). Son provisionales por diseño: debían recalibrarse con
la corrida real de la validación end-to-end (tarjeta #58). Toda evaluación incluye la versión
y los umbrales con que se calculó, para que un cambio posterior no reinterprete resultados
anteriores.

La evaluación incluye además indicadores informativos, sin umbral ni efecto en el veredicto:
distribución de niveles de evidencia, estado de las hipótesis, estado de las fuentes, citas
descartadas por no provenir del RAG, anclaje en el RAG, resultado de la recitación (Ronda 5),
contradicciones detectadas por el Árbitro y ensayos clínicos encontrados. Un indicador sin
dato se muestra como no disponible, nunca como cero.

La evaluación nunca copia texto clínico: identifica cada hipótesis por su posición en el
ranking.

### 1.3 Herramientas de medición

| Script | Función | Consumo de cuota |
|--------|---------|------------------|
| `scripts/medir_costos.py` | Ejecuta una pasada real del pipeline y compara `GROQ_MAIN` contra `GROQ_FAST` sobre las mismas entradas. Guarda el reporte (`reporte.json`) y, con `--grabar`, las respuestas crudas del modelo. | Sí: la comparación de modelos gasta unos 20.000 tokens adicionales por ejecución. |
| `scripts/evaluar_reporte.py <reporte.json>` | Evalúa un reporte guardado contra los criterios de calidad. Sale con código 0, 1 o 2 según el veredicto, y con 3 si el archivo no es un reporte válido. | No: sin red ni cuota. |
| `scripts/demo_criterios_calidad.py` | Siete reportes sintéticos del caso base con su veredicto esperado. | No. |

La telemetría de costos registra por cada llamada al proveedor el paso, el modelo, los tokens
de entrada y salida, la latencia y si falló, sin texto clínico ni prompts
(`backend/telemetry/usage.py`).

---

## 2. Resultados

### 2.1 Costo y latencia por caso

La cifra de referencia es la **última medición: 84.666 tokens por caso** (2026-11-03,
tarjeta #92), tomada sobre el pipeline tal como se entrega, con las citas ancladas al RAG. Es
mayor que las dos mediciones del 2026-10-06 (80.458 y 82.968 tokens) que se usaron antes como
referencia; las regrabaciones del modo mock de octubre llegaron a 88.143. El
proveedor actual (Groq, plan gratuito) impone una cuota de **200.000 tokens por día**: con ese
consumo entran **2 casos por día**.

| Fecha | Corrida | Tokens | Llamadas | Reintentadas (429) | Tiempo | Fuente |
|-------|---------|--------|----------|--------------------|--------|--------|
| 2026-10-04 | Medición de la tarjeta #84 (debate sin críticas) | 77.516 | 27 | — | — | `.claude/backlog.md:314-316` |
| 2026-10-06 | Primera corrida del día (debate sin críticas) | 78.158 | — | — | — | `.claude/backlog.md:328-329` |
| 2026-10-06 | Corrida con el arreglo de críticas (antecedente) | 80.458 (43.240 entrada, 37.218 salida) | 28 | 7 | 505 s | `.claude/backlog.md:325-328`, `.claude/CLAUDE.md:93-96` |
| 2026-10-07 | Regrabación del modo mock | 84.867 | 27 | 5 | 493 s | `.claude/traspaso.md:305-306` |
| 2026-10-20 | Regrabación con RAG grabado | 87.320 | 30 | 8 | 495 s | `.claude/traspaso.md:320-321` |
| 2026-10-26 | Regrabación con el prompt de Ronda 5 corregido | 88.143 | 28 | 6 | 526 s | `.claude/traspaso.md:325-326` |
| 2026-11-03 | Validación end-to-end (tarjeta #58) | 85.556 | 30 | 8 | 517 s | `.claude/backlog.md:411`, `.claude/CLAUDE.md:731-732` |
| 2026-11-03 | Verificación de citas ancladas al RAG (tarjeta #92) — **cifra de referencia** | 84.666 | 27 | 6 | 502 s | `.claude/backlog.md:413`, `.claude/CLAUDE.md:735-736` |

Las cifras del 2026-10-04 y de la primera corrida del 2026-10-06 están **superadas, no
erróneas**: se midieron con el debate funcionando sin críticas (ver sección 3.1). En todas las
corridas la latencia de la pasada completa estuvo entre 493 s y 526 s, es decir, alrededor de
ocho minutos y medio por caso.

Desglose por agente de la corrida del 2026-10-06 (`.claude/traspaso.md:172-173`): Agente 01,
21.889 tokens; Agente 02, 20.796; Agente 03, 21.334; Agente 04, 5.696; Agente 05, 7.668;
síntesis PICO y biomarcadores, 3.075. Los tres agentes del debate concentran la mayor parte
del consumo.

La comparación de costo contra la arquitectura de destino (Claude, GPT-4o, Gemini) que muestra
`scripts/demo_costos.py` usa una **muestra sintética** de 18 llamadas, no una corrida real
(`.claude/backlog.md:307-311`): 60.750 tokens de muestra, USD 0 con Groq y alrededor de
USD 1,67 con la arquitectura de destino. No debe leerse como un costo medido.

### 2.2 Calidad del reporte: antes y después de anclar las citas al RAG

La validación end-to-end del 2026-11-03 (tarjeta #58) se hizo con `scripts/medir_costos.py`
sobre `develop` (commit `5bd2d9b`) y se evaluó con `scripts/evaluar_reporte.py`. El pipeline
corrió completo (verificación `completa`, 9 hipótesis de consenso, 3 contradicciones, 10
ensayos), pero el veredicto fue **no cumple**. El RAG ofreció 5 artículos y ninguna cita salió
de ellos: los agentes citaban de memoria (`.claude/backlog.md:411`).

El arreglo (tarjeta #92, cambio OpenSpec `citas-ancladas-rag`) establece que una cita con
PMID solo es válida si ese PMID lo ofreció el RAG. Las demás se descartan antes de la
verificación y su total queda en `verification.fuera_del_rag`. La corrida real de
verificación, del mismo día, **cumple** los tres criterios (`.claude/backlog.md:413`).

| Indicador | Tarjeta #58 (2026-11-03) | Tarjeta #92 (2026-11-03) | Umbral |
|-----------|--------------------------|--------------------------|--------|
| Veredicto | no cumple | cumple | — |
| Cobertura de respaldo | 0,33 (3/9) | 0,91 (10/11) | ≥ 0,50 |
| Precisión de citas | 0,08 (2/25) | 1,00 (8/8) | ≥ 0,70 |
| Sobredeclaración | 0,56 (5/9) | 0,45 (5/11) | ≤ 0,50 |
| Citas fuera del RAG | — (el filtro no existía) | 0 | informativo |
| Anclaje en el RAG | 0 | 6 de 6 | informativo |
| Hipótesis en nivel III | 9 de 9 | 9 de 11 | informativo |
| Recitación (Ronda 5) | mejoró 3 de 9 | 3 hipótesis sin respaldo entraron, 2 mejoraron | informativo |
| Tokens / llamadas / tiempo | 85.556 / 30 / 517 s | 84.666 / 27 / 502 s | — |

Fuentes: `.claude/backlog.md:411` y `:413`;
`openspec/changes/archive/2026-11-03-citas-ancladas-rag/tasks.md:33`; recitación de la #92 en
`.claude/CLAUDE.md:779-781`.

En la #58, de las 25 citas contrastadas, 23 correspondían a PMIDs existentes pero de otro
artículo. En la #92, 9 de las 11 hipótesis siguen en nivel III: el respaldo proviene de
artículos con tipos de publicación de menor nivel de evidencia.

Los umbrales no se recalibraron después de la #58: detectaron un problema real
(`.claude/backlog.md:411`).

Dos salvedades acompañan el resultado de la #92 (`.claude/backlog.md:413`):

- Es **una sola corrida**; la variación entre corridas del modelo no está medida.
- La verificación confirma que el PMID corresponde al artículo citado, no que ese artículo
  respalde la hipótesis. En esa corrida, 8 artículos distintos sostienen 15 citas y uno se
  cita 4 veces. Eso lo debe juzgar la revisión médica (sección 4).

Como referencia, el reporte grabado del modo mock anterior a la #92 fallaba las tres métricas
(0,33, 0,28 y 0,67; `.claude/backlog.md:412`), y su veredicto formal es `no_evaluable` por
ser de modo mock.

### 2.3 Agente 04 (Árbitro): corrida del 2026-09-22

Medido sobre el caso base, con 456 s de duración y sin ningún fallback
(`.claude/backlog.md:158-171`):

| Indicador | Valor |
|-----------|-------|
| Hipótesis del debate → hipótesis de consenso | 14 → 7 |
| Referencias discordantes contra PubMed | 14 de 14 |
| Citas que salieron de los 5 artículos ofrecidos por el RAG | 0 de 14 |
| Ronda 5: hipótesis que recitaron / que obtuvieron respaldo verificable | 7 / 3 |
| Resultado final | 3 respaldadas, 0 pendientes, 4 especulativas, 10 ensayos |

Las 3 fuentes verificadas del reporte final salieron de la recitación: sin la Ronda 5 el caso
habría terminado sin respaldo bibliográfico. Este resultado anticipó el problema que la
tarjeta #92 resolvió de forma estructural.

### 2.4 Agente 05 (Navegador de Ensayos): corrida del 2026-09-15

Medido sobre el caso base, con 294 s de duración y sin `ORPHANET_API_KEY`
(`.claude/backlog.md:458-465`):

| Indicador | Valor |
|-----------|-------|
| Ensayos únicos encontrados | 21 |
| Excluidos por edad / por sexo | 2 / 0 |
| Ensayos en el reporte | 10 |
| Compatibilidad `alta` / `media` / `baja` | 0 / 2 / 8 |
| Evaluaciones descartadas (NCT ID inventado por el LLM) | 0 |
| Hipótesis marcadas como enfermedad rara por Orphanet | 1 (ORPHA 85443, *AL amyloidosis*) |

Ninguna compatibilidad resultó `alta` porque el caso es una neuropatía sin diagnóstico y casi
todos los ensayos de ATTR exigen cardiomiopatía confirmada. El único ensayo con sede en
Argentina (NCT07052903) quedó primero dentro de su nivel de compatibilidad: la sede desempata,
no determina el orden.

---

## 3. Problemas encontrados y su corrección

### 3.1 Las críticas del debate no llegaban a los agentes

En la Ronda 2 el modelo declaraba el destinatario de cada crítica como "Agent 02", "Agent01"
o "Agent03", y el debate enrutaba por ID exacto ("01", "02", "03"). En la primera corrida
real del 2026-10-06, **0 de 21 críticas** llegaron a su destinatario, y lo mismo había ocurrido
en todas las corridas anteriores: las Rondas 3 y 4 revisaban sin críticas. El arreglo (PR #31,
con refinamiento en el PR #32) normaliza el identificador y solo atribuye la crítica cuando el
destinatario es inequívoco. En la segunda corrida del día llegaron **18 de 18**, y la entrada de
la tarea de revisión pasó de 11.186 a 16.917 tokens (`.claude/traspaso.md:174-184`,
`.claude/backlog.md:331-333`).

### 3.2 Baja de los modelos LLaMA en Groq

Groq dio de baja `llama-3.3-70b-versatile` y `llama-3.1-8b-instant`, y la API empezó a
responder 404 `model_not_found`. Se reemplazaron por `openai/gpt-oss-120b` y
`openai/gpt-oss-20b` en el commit `5174330` (`.claude/CLAUDE.md:667-670`). Como efecto
secundario, los `gpt-oss` cuentan el razonamiento dentro de la salida: en la medición del
2026-10-04, los techos de 512 y 1024 tokens de la agrupación del Árbitro y de la planificación
de términos cortaban la respuesta, y volvieron a 4096 (`.claude/backlog.md:316-319`).

### 3.3 El RAG consultaba PubMed en español

La búsqueda bibliográfica del RAG se armaba con la condición clínica en español. Se corrigió
para usar `condition_en`, la condición expresada en inglés médico que produce la síntesis PICO
(`.claude/backlog.md:118`, `.claude/CLAUDE.md:70`).

### 3.4 Citas discordantes y la Ronda 5 de recitación

Los agentes citaban PMIDs que existían en PubMed pero correspondían a otro artículo, por lo que
un chequeo de existencia los aprobaba. Se midió en tres corridas que **9 de cada 10
referencias eran discordantes** (`.claude/backlog.md:184-188`). La verificación bibliográfica
pasó a comparar el título real con el citado (`backend/pipeline/verification.py`). El criterio
de parada original de la arquitectura ("toda hipótesis con referencia verificable") no se
cumplía nunca, con 15 de 15 citas discordantes (`.claude/backlog.md:145-148`). Se reemplazó por
la Ronda 5: las hipótesis sin respaldo vuelven a su autor con el motivo del fallo y los
artículos recuperados por el RAG, en una sola iteración. Lo que sigue sin respaldo queda
especulativo y no se descarta.

### 3.5 Errores de esquema en la Ronda 5 (tarjeta #90)

En la corrida del 2026-10-20 los Agentes 01 y 02 respondieron la recitación con la clave
`hypotheses` en lugar de `recitations`; el parser las rechazaba y la recitación fallaba sin
aviso visible. Se corrigió el 2026-10-26 (PR #70, tarjeta #90): el prompt prohíbe esa clave y
la reescritura de hipótesis, y el parser acepta la forma equivocada solo para la hipótesis cuyo
texto coincide con la ofrecida, avisando por stderr. Medido en modo mock sobre cada grabación:
9 recitadas y 2 mejoradas (2026-10-20) contra 12 recitadas y 4 mejoradas (2026-10-26)
(`.claude/traspaso.md:321-329`, `.claude/CLAUDE.md:771-779`).

### 3.6 Deriva entre las grabaciones del modo mock y PubMed en vivo

El modo mock reproducía las respuestas del modelo, pero la Ronda 1 seguía consultando PubMed
en vivo. Medido el 2026-10-15, PubMed ya devolvía otros artículos que el 2026-10-07: las
recitaciones grabadas citaban PMIDs que ya no se ofrecían y el resumen del Agente 06 se
descartaba por la guarda anti-invención. Desde el 2026-10-20, `--grabar` guarda también lo que
ofreció el RAG (bloque `rag` de `backend/mock/grabadas.json`) y en modo mock la Ronda 1 usa esos
artículos (`.claude/CLAUDE.md:783-788`, `.claude/traspaso.md:316-322`).

### 3.7 El Árbitro tomaba hipótesis sin filtrar

Al implementar la tarjeta #92 apareció que el Árbitro tomaba las hipótesis de la última ronda
del debate, sin filtrar, y las citas descartadas volvían al consenso como pendientes. Se
corrigió en `consensus.build_arbitration_input()`: el Árbitro toma las hipótesis de
`report.hypotheses`, ya filtradas (`.claude/backlog.md:413`).

---

## 4. Revisión médica (tarjeta #60)

Los criterios automáticos no pueden responder tres preguntas: si cada hipótesis es pertinente
para el paciente, si el artículo citado respalda lo que afirma la hipótesis y si falta una
hipótesis que un clínico consideraría obvia. Para eso se diseñó una sesión de revisión con un
médico (idealmente neurólogo o clínico) o el tutor de la tesis, cuyo protocolo está en
`docs/revision-medica.md`.

La sesión dura entre 45 y 60 minutos y trabaja sobre el reporte de la corrida de la #92
(11 hipótesis). Por cada hipótesis, el revisor responde si es pertinente, si la cita la
respalda, si el nivel de evidencia es razonable y si la investigaría en este paciente.
`scripts/revision_medica.py` genera el material (`preparar`, que rechaza reportes de modo mock)
y tabula las respuestas (`tabular`). El indicador central es el número de hipótesis con
**respaldo verificado sin respaldo clínico**, que mide la salvedad principal de la #92.

La sesión no es una evaluación de diagnóstico ni un estudio clínico: es la opinión de una o dos
personas sobre un caso, útil para detectar problemas, no para afirmar eficacia.

**Estado: pendiente.** El material está listo, pero al cierre de este documento la sesión no
se realizó: falta conseguir al revisor (`.claude/backlog.md:414`). No hay resultados de
revisión médica que informar.

---

## 5. Limitaciones

### 5.1 Validez estadística

- **Una sola corrida real por configuración.** Cada cifra de calidad proviene de una corrida;
  la variación entre corridas del modelo no está medida (`.claude/backlog.md:411`, `:413`;
  `.claude/CLAUDE.md:781`).
- **Un solo caso de prueba.** Todas las mediciones se hicieron sobre el caso base de neuropatía
  axonal. No se sabe cómo se comporta el sistema con otras especialidades, otros perfiles de
  paciente o documentos de menor calidad.
- **Umbrales provisionales.** Los umbrales de la versión `2026-11-provisional` no se
  recalibraron con más casos. El cumplimiento de la #92 se mide contra valores que todavía no
  están validados.
- **Respaldo verificado no equivale a respaldo clínico.** La verificación confirma que el PMID
  corresponde al artículo citado, no que el artículo sostenga la hipótesis. Esta pregunta queda
  abierta hasta la revisión médica.

### 5.2 Proveedor de modelo

- **Groq `gpt-oss` es un proveedor temporal.** Todos los agentes usan `openai/gpt-oss-120b`
  (y tres tareas acotadas, `openai/gpt-oss-20b`) mientras se gestionan créditos en las APIs de
  pago. Los resultados no son extrapolables a la arquitectura de destino sin volver a medir.
- **Cuota diaria.** Con 200.000 tokens por día y alrededor de 80.000 a 88.000 por caso, solo
  entran dos corridas reales por día, lo que limita la cantidad de mediciones posibles.

### 5.3 Privacidad

- **Anonimización.** El módulo de anonimización de nombres, fechas e identificadores (tarea 1
  del Sprint 5) no está integrado en `develop` al momento de este documento: figura sin
  completar en `.claude/backlog.md:408`. Según el estado informado por el equipo, se encuentra
  en revisión (PR #82 de GitHub). Por diseño, ese módulo es una red de seguridad determinista, no una
  garantía de desidentificación: puede dejar pasar identificadores que no reconozca. El caso
  base es un caso de prueba sin datos de un paciente real.
- **Verificación de matrícula.** Consultar el padrón público solo prueba que existe una
  matrícula con ese número a nombre de esa persona; cualquiera podría registrarse con los datos
  reales de un médico existente. El diseño delega esa decisión al administrador humano y deja
  auditoría de la fuente consultada: es una mitigación parcial, no una verificación de
  identidad resuelta
  (`openspec/changes/archive/2026-10-04-registro-medicos-matricula/design.md:197-212`).

### 5.4 Seguridad web

- **La CSP del frontend permite el atributo `style`** (`style-src-attr 'unsafe-inline'`),
  porque varios componentes posicionan y animan con él. Un atributo de estilo no ejecuta
  código, pero sí permite alterar la apariencia de la página si se lograra inyectar HTML.
  Los scripts, en cambio, solo corren con el nonce del pedido (`frontend/src/lib/csp.ts`).
- **La CSP obliga a renderizar cada página en cada pedido**: el nonce no puede estar en una
  página generada de antemano, así que no hay caché de páginas.
- Una respuesta 500 sin manejar del backend no lleva los encabezados de seguridad, porque la
  arma el middleware más externo de Starlette (`.claude/CLAUDE.md:850-851`).

### 5.5 Evidencia y recuperación

- **Clasificación EBM.** El tipo de publicación `Systematic Review` existe en PubMed desde
  2019. Las revisiones sistemáticas anteriores, indexadas solo como `Review`, quedan topeadas
  en nivel III (`openspec/specs/clasificacion-evidencia-ebm/spec.md:33`,
  `.claude/backlog.md:426-428`).
- **Negación en los embeddings.** Ningún modelo de embeddings evaluado maneja la negación: con
  "negative CMT panel" en la consulta, los tres traen Charcot-Marie-Tooth entre los primeros
  resultados. El hallazgo negativo llega al agente por la síntesis PICO, pero el recuperador no
  lo usa para filtrar (`.claude/stack.md:102-106`, hallazgo C en `.claude/backlog.md:503`).
- **Umbral de relevancia del RAG.** El valor 0,55 se midió con un solo artículo de control; al
  cambiar de modelo de embeddings hay que volver a medirlo (hallazgo A en
  `.claude/backlog.md:501`).
- **Ruido de ClinicalTrials.gov.** La búsqueda por relevancia trae ensayos ajenos al caso: con
  "Hereditary sensory and autonomic neuropathy" devolvió dos ensayos de tumores sólidos con
  mutación ATM. No se filtran, porque solo los filtros deterministas excluyen, pero el LLM los
  etiquetó `baja` con el motivo explícito (`.claude/backlog.md:467-471`).
- **Numeración de variantes.** La numeración clásica (TTR `Val30Met`) no se convierte a HGVS
  (`p.Val50Met`), y ClinVar devuelve un resultado `ambigua` (`.claude/backlog.md:553-556`).

### 5.6 Reproducibilidad del modo mock

- **La verificación y la búsqueda de ensayos consultan APIs en vivo aun en modo mock.** El
  modo mock fija las respuestas del modelo y la literatura de la Ronda 1, pero la verificación
  de PMIDs y la búsqueda de ensayos siguen consultando PubMed y ClinicalTrials.gov en vivo
  (`.claude/CLAUDE.md:787-788`). Un reporte de modo mock puede cambiar si esas fuentes cambian.

---

## 6. Trabajo futuro

1. **Corrida real de la arquitectura multi-proveedor.** Claude Opus para los Agentes 01, 04 y
   06, GPT-4o para el Agente 02 y Gemini Pro para el Agente 03 ya están implementados detrás
   de `NEXUS_PROVEEDORES=destino` (`backend/agents/model_tasks.py`), con respaldo en Groq por
   llamada, pero solo se probaron con dobles de los SDK. Falta una corrida con las tres claves
   (`scripts/medir_costos.py --grabar`) para medir costo y calidad frente a Groq.
2. **Reconocimiento de entidades biomédicas en español para la anonimización.** Complementar la
   red de seguridad determinista con un modelo de NER clínico en español que detecte
   identificadores no cubiertos por reglas.
3. **Recalibración de umbrales con más casos.** Reemplazar la versión `2026-11-provisional` por
   umbrales derivados de varios casos y de varias corridas por caso, que permitan además medir
   la variación del modelo.
4. **Validación multi-caso con médicos.** Realizar la sesión de la tarjeta #60 y extenderla a
   varios casos y varios revisores, para estimar con qué frecuencia una hipótesis con respaldo
   verificado carece de respaldo clínico.

---

## Apéndice: discrepancias entre fuentes

| Tema | Fuente A | Fuente B | Interpretación |
|------|----------|----------|----------------|
| Corrida del 2026-10-06 | 80.458 tokens, 28 llamadas (7 reintentadas), 505 s (`.claude/backlog.md:325-328`, `.claude/CLAUDE.md:93-96`) | 82.968 tokens, 26 llamadas (4 reintentadas), 495 s (`.claude/backlog.md:567-569`, nota 21) | Probablemente corresponden a pasadas distintas del mismo día; las fuentes no lo aclaran. Ninguna de las dos se usa como cifra de referencia: este documento toma la última medición, 84.666 tokens (2026-11-03), que es mayor que ambas. |
| Proporción de citas discordantes | 15 de 15 (`.claude/backlog.md:147`, `.claude/CLAUDE.md`) | 14 de 14 en la corrida del 2026-09-22 (`.claude/backlog.md:163`); 9 de cada 10 en tres corridas (`.claude/backlog.md:186`) | Mediciones de corridas distintas; todas muestran discordancia casi total antes de la verificación por título. |
| Anclaje en el RAG de la #58 | "de 0 a 6 de 6" (`.claude/backlog.md:413`) | "0/23 → 6/6" (`openspec/changes/archive/2026-11-03-citas-ancladas-rag/tasks.md:33`) | Mismo valor (cero); el denominador 23 son citas del arbitraje, distinto de las 25 citas contrastadas de la precisión. |
