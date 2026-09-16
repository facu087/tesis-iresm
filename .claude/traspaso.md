# Traspaso de sesión — 2026-09-15

Sesión de Claude Code en la computadora de Matias, cerrada a las 17:20 para seguir en
otra máquina. Este archivo reemplaza a la memoria local de esa sesión (no viaja con git).

**Para retomar con Claude Code**: "Leé `.claude/traspaso.md` y seguí como orquestador
desde la sección Pendiente."

---

## 1. Modo de trabajo acordado

Claude funciona como **orquestador** del Sprint 4: planifica con OpenSpec y delega cada
cambio a un subagente en su propio git worktree. Reglas que eligió Matias:

| Tema | Regla |
|------|-------|
| Revisión | Frenar después de `/opsx:propose` y mostrarle el diseño. **No hacer apply sin su OK.** |
| Git | Rama por tarea desde `origin/develop` → push → PR a `develop` → merge sin esperar revisión. Asunto del merge: `merge: <qué> (Sprint 4)` con cuerpo que diga qué tarjeta cierra (`gh pr merge --merge --subject ... --body ...`). |
| Trello | Al terminar: adjuntar evidencia (PNG de la salida + `.txt` + `.json`, como la tarjeta #64), actualizar la descripción y mover a `QA`. |
| Orden | Olas: fixes → #54 → #51 y #53 → #52 → #62. |

Lecciones prácticas:
- **Cupo de tokens**: 4 subagentes Opus en paralelo agotaron el límite de sesión y se
  cortaron a mitad de tarea. Máximo 2–3 en simultáneo. Subir PNGs en base64 a Trello
  consume mucho: dejarlo para el final.
- **Trello MCP**: hay que llamar `set_active_board` con `kdXM36sU` al empezar (no queda
  por defecto). No puede borrar ni renombrar adjuntos: revisar antes de subir, y no usar
  "/" en el nombre del adjunto (Trello guarda el archivo sin extensión).
- **Worktrees**: no traen `.env` ni `frontend/node_modules` (symlinkear). Next.js con
  `node_modules` symlinkeado no arranca con Turbopack: `next dev --webpack`.
- IDs útiles: lista Sprint 4 `6a1f6864889d8c5fe2ae2e5d`, lista QA `6a1642161e9946c1c9109254`.

---

## 2. Qué se hizo hoy

### Ola 0 — evidencia de tarjetas ya implementadas (PR #3, mergeado)
- A **QA con evidencia real**: #63 (RAG + verificador en el flujo), #64 (verificación PMIDs),
  #65 (fix `.env.example`), #66 (embeddings), #67 (query en inglés), #69 (vista con estado
  de verificación), #70 (PDF con estado de verificación). La evidencia de #63/#69/#70 sale
  de una corrida real de `POST /api/analyze` sobre el caso de la tesis.
- `.claude/backlog.md` y `.claude/CLAUDE.md` sincronizados con el estado real.
- **#68 no pasó a QA**: su evidencia muestra `Genes identificados: ['CMT']` (ver fix F4).

### Tarjetas nuevas / editadas en Trello
- **#71** "Cliente ClinVar: significancia clínica de variantes genéticas" (EP05, Sprint 4).
- **#72** "Fix: el debate se caía si un agente fallaba en la Ronda 1" (EP03, Sprint 4).
- **#51** descripción actualizada: ClinVar sale de su alcance y pasa a #71.

### Propuestas OpenSpec (las tres validan con `openspec validate --strict`)
| Tarjeta | Cambio | Rama (en GitHub) | Estado |
|---------|--------|------------------|--------|
| #54 Priorización EBM | `priorizacion-evidencia-ebm` | `feature/s4-priorizacion-evidencia-ebm` | **Mergeada en `develop`** (PR #4, 316 tests en verde). Falta evidencia en Trello y archivar — ver §3.2 |
| #51 Agente 02 Genómica | `agente-02-genomica` | `feature/s4-agente-02-genomica` | Propuesta aprobada, **sin implementar** |
| #53 Agente 05 Ensayos | `agente-05-navegador-ensayos` | `feature/s4-agente-05-navegador-ensayos` | Propuesta aprobada, **sin implementar** |

### Decisiones de Matias sobre las propuestas
**#54 EBM**
- El nivel efectivo = el declarado por el agente, **topeado** por el tipo de publicación de
  su mejor fuente verificada (PubMed `pubtype`, sin consultas extra). Nunca sube.
- Orden del reporte: **estado → nivel → prioridad**.
- Guías de práctica clínica: **máximo II**.
- Revisiones sistemáticas anteriores a 2019 (indexadas solo como "Review") quedan en III:
  **limitación documentada**.
- Estados: respaldada / pendiente / especulativa. "Descartada" se elimina (regla del proyecto).

**#51 Agente 02**
- **ClinVar fuera** (tarjeta #71).
- Hipótesis que cita un hallazgo genético ausente del caso: **se degrada a LOW con aviso**, no se descarta.
- Sin variantes en el caso (caso base): corre en modo orientación.

**#53 Agente 05**
- Incluir `NOT_YET_RECRUITING` (etiquetados) y **ordenar primero los ensayos con sede en
  Argentina** (ordena, no filtra).
- Se aceptan las 2 llamadas extra a Groq; partir `BaseAgent` queda para cuando existan 04 y 06;
  el cliente Orphanet lanza excepción ante error en vez de devolver `[]`.

**Bugs encontrados → cada uno en su rama `fix/` separada** (ver §3.3).

---

## 3. Pendiente (en orden)

### 3.1 Tareas manuales de Matias
1. **`.env` local**: `PUBMED_API_KEY` y `ORPHANET_API_KEY` tienen el comentario como valor
   (el bug de #65). PubMed responde 400 y toda la verificación sale "no_verificable".
   Poner los comentarios en su propia línea. Mientras tanto: `env PUBMED_API_KEY= ORPHANET_API_KEY= <comando>`.
2. **Trello #65**: borrar el adjunto duplicado y corrupto `6aa969ab55bd2b7b4a9caec5` (PNG de 7,4 KB sin preview).
3. **Trello #63**: renombrar el PNG sin extensión `analyze__RAG_en_Ronda_1_y_verificacion_en_paso_7`.

### 3.2 Cerrar #54 (Priorización EBM) — CERRADO 2026-09-15
Mergeado en `develop` (PR #4): `backend/pipeline/evidence.py`, vista y PDF agrupados por
estado, "Evidencia II (el agente declaró I)". Tests: 316 pasados. Se completó todo lo que
quedaba pendiente:
1. ✅ Tarea 5.2: se corrió `python3 scripts/demo_priorizacion_evidencia.py --pubmed`
   (7 hipótesis, PMIDs reales) y quedó marcada en `tasks.md`.
2. ✅ Se abrió la vista de reporte en Chrome con `output/demo_priorizacion_evidencia/reporte.json`
   (inyectado a `sessionStorage` vía consola, ver captura en la tarjeta). Se vio bien: agrupado
   por estado, badge "declarado N", nota del tope, discordancia de PMID 22439958 con título real.
3. ✅ Archivado (`chore/s4-archiva-priorizacion-ebm`, PR #6, mergeado a `develop`):
   `openspec/changes/archive/2026-09-15-priorizacion-evidencia-ebm/`, spec vigente en
   `openspec/specs/clasificacion-evidencia-ebm/`, `.claude/architecture.md` actualizado.
4. ✅ Trello #54 (`6a1f68caeea3d35c92c9f576`): adjuntos `priorizacion.txt`, `reporte.json`,
   `reporte.pdf` y una captura de la vista (comprimida a JPEG ~13KB por límite de tamaño de
   contexto — quedó subida con extensión `.png` por defecto del server MCP, que no
   permite renombrar; no afecta la vista previa de Trello). Descripción actualizada con la
   tabla de topes y la limitación pre-2019. Movida a QA.

Nota de sesión: la cuenta de `gh` logueada al arrancar (`lussofacundo-iresm`) no tenía permiso
de push al repo — hubo que `gh auth login`/`gh auth switch` a `facu087` para poder pushear y
mergear el PR #6.

Efecto visible a tener en cuenta: en reportes nuevos el orden cambia (el nivel pesa más
que la prioridad) y `evidence_level` es el nivel final, no el declarado.

Hallazgos que anotó en `backlog.md`:
- **G**: `BaseAgent.parse_hypotheses()` (`base_agent.py:92`) hace `Source(**s)` con lo que
  manda el LLM, así que acepta campos de verificación inventados. La clasificación de #54
  ya los ignora; el hueco de parseo sigue abierto.
- **H**: `npm run lint` tiene 1 error y 1 warning previos (setState dentro del effect de
  carga en `report/page.tsx`; `analyzing/page.tsx:120`).
- De paso arregló `frontend/next.config.ts` (`experimental.turbo` no existe en Next 16 y
  rompía `npm run build`; pasó a `turbopack.root`).

### 3.3 Fixes (ninguno empezado; se frenaron para ahorrar cupo)
| # | Rama | Qué | Tarjeta |
|---|------|-----|---------|
| F1 | `fix/s4-cliente-orphanet` | `orphanet.py:98` usa `/approximatelymatching` (404); el endpoint real es `ApproximateName/{name}` y la respuesta usa `ORPHAcode`. `_get_genes()` (`:175`) también da 404. El error se ocultaba porque atrapa `Exception` y devuelve `[]`; el demo usa datos simulados. Detalle en `openspec/changes/agente-05-navegador-ensayos/design.md` (rama de #53). | Evidencia real a **#48** (ya en QA, no mover) |
| F2 | `fix/s4-pharmgkb-api-real` | `pharmgkb.py` nunca se probó contra la API real, atrapa todo y no usa rate limiter. Primero verificar con PMP22, MPZ, TTR, CYP2D6; distinguir error de "sin resultados". | Evidencia real a **#49** (ya en QA, no mover) |
| F3 | `fix/s4-debate-agente-caido` | `debate.py:130,145` hace `current_outputs[agent.AGENT_ID]`: `KeyError` si un agente falló en la Ronda 1 → se cae `/api/analyze`. El debate debe seguir con los que respondieron y dejar constancia. | **#72** → QA |
| F4 | `fix/s4-genes-falsos-extractor` | `biomarker_extractor.py:65-67`: `CMT`, `FAP`, `ATTR` están en `_KNOWN_GENES` (son enfermedades). `tests/test_biomarkers.py` no es pytest (script con `main()`, exige CMT como gen): convertirlo en tests reales. | **#68** → QA (evidencia nueva) |

F1 va antes de aplicar #53; F2, F3 y F4 antes de aplicar #51.

### 3.4 Aplicar #53 y #51
Primero actualizar sus artefactos (`/opsx:update`) con las decisiones de §2 y con lo que
cambie en los clientes por F1–F4 (en #53, sacar el fix del cliente Orphanet, que va en F1).
Después `/opsx:apply`, tests, demo, archivar, PR, merge, evidencia y QA.
- #51 (`6a1f68c6653178f9cd22ab75`) toca `orchestrator.py`, `debate.py`, `models/case.py`, `pharmgkb.py`.
- #53 (`6a1f68c910f554b91c7e0718`) toca `router.py` (paso 6), `schemas.py`, `report_builder.py`, `pdf_exporter.py`, frontend.

### 3.5 Proponer #52 (Árbitro — síntesis, Ronda 5) y #62 (Sintetizador)
- #52 (`6a1f68c7e380a0c147eb855a`) consume `evidence.classify_hypothesis()` / `prioritize()` de #54.
- **Dato clave para el diseño de #52**: en la corrida real de hoy, ninguno de los 12 PMIDs
  que citaron los agentes coincide con los 5 que el RAG puso en el prompt, y los 12
  resultaron discordantes. Los agentes no usan la literatura recuperada.
- #62 (`6aa034aec95b5ac3da581be0`) reemplaza a `report_builder.py` sin cambiar `StructuredReport`; va último.
- #71 ClinVar cuando haya tiempo.

### 3.6 Segundo lote de fixes (propuesto, sin decidir)
- PDF: en la portada "NEXUS" se pisa con el subtítulo (`pdf_exporter.py:118-121`); las
  celdas del resumen del caso se salen del margen (`pdf_exporter.py:232-245`). Es lo que lee el médico.
- `rag/indexer.py:152-160` convierte excepciones en 0 artículos sin avisar (RAG vacío silencioso).
- `orchestrator.py:74-76` y `tests/test_rag_integration.py:97-99` citan scores de all-MiniLM
  (0.866→0.781); con PubMedBERT es 0.789→0.707.
- El bloque "Variables de entorno" de `.claude/CLAUDE.md` tiene comentarios en la misma
  línea: copiarlo al `.env` reintroduce el bug de #65.
- `scripts/demo_pdf.py` arma el reporte sin sección `verification`.

---

## 4. Demo para el profesor

### Levantar el sistema
```bash
git checkout develop && git pull origin develop
pip install -r backend/requirements.txt        # torch CPU: ver CLAUDE.md § Setup del RAG
(cd frontend && npm install)

# Backend (raíz del repo). Quitar el env ... si el .env ya está corregido.
env PUBMED_API_KEY= ORPHANET_API_KEY= uvicorn backend.main:app --reload   # :8000

# Frontend
cd frontend && npm run dev                                                # http://localhost:3000
```
Caso de la tesis: el texto `CASO_CLINICO` de `scripts/poc_test.py` (neuropatía axonal
sensitivomotora, varón de 42 años), pegado en la vista de carga.
Una corrida completa tarda **~3 min 40 s** (Groq + PubMed + ChromaDB).

### Respaldo (hacerlo antes de la reunión, por si Groq o PubMed fallan en vivo)
```bash
mkdir -p output/demo
python3 -c "import re;s=open('scripts/poc_test.py').read();print(re.search(r'CASO_CLINICO = \"\"\"(.*?)\"\"\"',s,re.S).group(1).strip())" > output/demo/caso.txt
curl -s -F "text=<output/demo/caso.txt" http://localhost:8000/api/analyze > output/demo/reporte.json
curl -s -X POST -H "Content-Type: application/json" --data @output/demo/reporte.json \
     http://localhost:8000/api/report/pdf > output/demo/reporte.pdf
```

### Guion (~10 min)
1. Qué es NEXUS: genera **hipótesis de investigación**, no diagnósticos.
2. Cargar el caso en la vista de carga.
3. Vista de pipeline en tiempo real (~4 min). Mientras corre: ingesta → PICO → RAG con
   PubMedBERT → Ronda 1 (agentes 01 y 03) → debate Rondas 2–4 → verificación de PMIDs.
4. Reporte: hipótesis agrupadas en respaldadas / pendientes / especulativas, con el nivel
   EBM topeado ("Evidencia II (el agente declaró I)") y el tipo de publicación de cada
   fuente verificada; ensayos clínicos, divergencias y bibliografía con
   título citado vs. real. **Dato fuerte**: en la corrida real las 12 citas de los agentes
   eran discordantes con PubMed — por eso existe el Árbitro Verificador.
5. Exportar el PDF.
6. Qué sigue: agentes 02 y 05 (propuestas aprobadas), síntesis del Árbitro y Sintetizador,
   todo planificado con OpenSpec.

---

## 5. Setup de la otra computadora
- `npm install -g @fission-ai/openspec@latest` (v1.11.0 o superior).
- MCP de Trello configurado en Claude Code (y `set_active_board kdXM36sU`).
- `gh auth login` para PRs y merges.
- `.env` con las keys, **comentarios en su propia línea**.
- Traerse las ramas: `git fetch origin` (quedan en GitHub `feature/s4-agente-02-genomica`,
  `feature/s4-agente-05-navegador-ensayos` y la de #54).
