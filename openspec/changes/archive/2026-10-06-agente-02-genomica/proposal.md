## Why

El pipeline corre hoy con dos de los tres agentes de la Ronda 1 (01 Literatura y 03 Clínico): falta la
perspectiva genómica que la arquitectura asigna al Agente 02 (tarjeta #51). El caso base de la tesis
—neuropatía axonal sensitivomotora, hombre de 42 años, padre con "problemas de equilibrio", panel CMT de
40 genes negativo y compromiso autonómico— es justamente un caso donde la etiología hereditaria no
cubierta por el panel es una hipótesis central, aunque el documento **no trae ninguna variante**. El
agente tiene que aportar esa lectura sin inventar hallazgos genéticos que el paciente no tiene.

## What Changes

- Nuevo **Agente 02 — Especialista Genómica** (`backend/agents/agent_02_genomics.py`): hereda `BaseAgent`,
  corre sobre Groq `GROQ_MAIN` y llama al LLM **solo** vía `BaseAgent._call_llm()` (el swap a GPT-4o
  queda en ese método, fuera de este cambio). Devuelve el mismo JSON de hipótesis que 01 y 03.
- Nuevo **contexto genómico determinista** (`GenomicContext`): se arma sin LLM a partir de
  `BiomarkerProfile` y de la síntesis PICO, separa lo que el caso **reporta** (variantes, hallazgos
  genéticos positivos) de lo que solo **menciona** (genes nombrados, estudios genéticos negativos) y
  descarta siglas que no son genes (hoy el extractor devuelve `CMT` como gen en el caso base).
- **Dos modos** del agente, decididos por datos y no por el LLM: *con hallazgos genómicos* e
  *orientación* (sin variantes ni hallazgos positivos). En modo orientación las hipótesis se formulan
  como etiologías hereditarias y estudios a considerar, nunca como hallazgos del paciente.
- **Guarda anti-invención**: cada hipótesis declara qué hallazgos genéticos del caso usa; si cita alguno
  que no figura en el `GenomicContext`, o si en modo orientación menciona una variante concreta en el
  texto, la hipótesis **no se descarta** pero se degrada a prioridad `LOW` con una advertencia visible.
- **Enriquecimiento con PharmGKB** por símbolo de gen (solo símbolos; nunca texto clínico ni nombres de
  fármacos en español), con estado por fuente (`consultada`, `sin_resultados`, `no_disponible`,
  `no_consultada`) para que el agente no confunda "API caída" con "sin interacciones".
- `backend/external/pharmgkb.py`: deja de tragar excepciones (`except Exception: pass`), usa el
  `pharmgkb_limiter` / `pharmgkb_breaker` existentes y se verifica contra la API real (el demo actual
  usa datos simulados).
- **Ronda 1**: el orquestador corre 01, 02 y 03 en paralelo; el enriquecimiento genómico corre en paralelo
  con el del RAG. **Debate (Rondas 2–4)**: el Agente 02 participa con el mismo bloque genómico; el debate
  pasa a incluir solo a los agentes que tienen output de Ronda 1 (hoy un agente caído en Ronda 1
  provoca `KeyError` en la Ronda 2).
- Frontend: la vista de pipeline pasa a decir "Agentes 01, 02 y 03 en simultáneo".
- **ClinVar queda fuera** de este cambio (ver design.md, D6): no hay cliente, el caso base no tiene
  variantes que consultar y el `GenomicContext` ya admite fuentes adicionales sin tocar el agente.

## Capabilities

### New Capabilities
- `agente-especialista-genomica`: Agente 02 — prompt, modos con hallazgos / orientación, formato JSON,
  guarda anti-invención, participación en Ronda 1 y en el debate, y atribución de sus hipótesis.
- `contexto-genomico`: construcción determinista del perfil genómico del caso, saneamiento de símbolos,
  enriquecimiento con PharmGKB con anonimización y estado explícito por fuente.

### Modified Capabilities
<!-- No hay specs vigentes en openspec/specs/ (no se backfillean los Sprints 1–3). Los cambios de
     comportamiento del orquestador y del debate se especifican dentro de `agente-especialista-genomica`. -->

## Impact

- **Código nuevo**: `backend/agents/agent_02_genomics.py`, `backend/models/genomics.py`,
  `backend/pipeline/genomic_context.py`, `tests/test_agent_02_genomics.py`,
  `tests/test_genomic_context.py`, `scripts/demo_agente02.py`.
- **Código modificado**: `backend/pipeline/orchestrator.py`, `backend/pipeline/debate.py`,
  `backend/models/case.py` (campo opcional `genomic_context`), `backend/external/pharmgkb.py`,
  `backend/agents/__init__.py`, `frontend/src/app/analyzing/page.tsx`, `tests/test_orchestrator.py`,
  `tests/test_debate.py`, `tests/test_pharmgkb.py`, `scripts/demo_orquestador.py`.
- **Sin cambios**: `BaseAgent`, `Hypothesis`, `Report`, `report_builder.py`, `api/schemas.py`,
  `api/router.py`. La atribución por agente funciona sin tocar `report_builder` porque se reconstruye
  por `agent_name`.
- **Costo en Groq**: por análisis se pasa de 10 a 14 llamadas al LLM (PICO 1 + biomarcadores 1 +
  3 agentes × 4 rondas). Las rondas siguen siendo paralelas, pero con 3 llamadas simultáneas sube la
  probabilidad de 429 en el tier gratuito y de esperas de backoff (8/20/40 s).
- **APIs externas**: PharmGKB recibe solo símbolos de genes saneados (máx. 3 por caso). En el caso base
  no se hace ninguna llamada externa nueva.
- **Documentación**: `.claude/CLAUDE.md`, `.claude/backlog.md`, `.claude/architecture.md` (ClinVar fuera
  del prototipo del Agente 02).
