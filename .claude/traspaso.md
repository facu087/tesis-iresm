# Traspaso de sesión — 2026-09-15 (noche)

Reemplaza al traspaso anterior del mismo día. Se cierra con el Sprint 4 casi terminado:
quedan los agentes 04 y 06, y las tarjetas repartidas entre los tres integrantes.

**Para retomar con Claude Code**: "Leé `.claude/traspaso.md` y seguí como orquestador
desde la sección Pendiente."

---

## 1. Modo de trabajo acordado

Claude funciona como **orquestador** del Sprint 4: planifica con OpenSpec y delega la
implementación a un subagente. Reglas que eligió Matías:

| Tema | Regla |
|------|-------|
| Revisión | Frenar después de `/opsx:propose` o `/opsx:update` y mostrar el diseño. **No hacer apply sin su OK.** |
| Git | Rama por tarea desde `origin/develop` → push → PR a `develop` → merge sin esperar revisión. Asunto del merge: `merge: <qué> (Sprint 4)`. |
| Trello | Al terminar: adjuntar evidencia (capturas de la salida + `.json` + `.txt`), actualizar la descripción con los números medidos y mover a `QA`. |
| Reparto | Por **área de archivos**, para que dos personas no toquen el mismo módulo. Ver `.claude/backlog.md` § "Reparto de tareas". |

Lecciones prácticas:
- **Cupo de tokens**: un subagente Opus corriendo solo ya agotó el límite de sesión una vez;
  se retomó con su contexto intacto y sin perder trabajo. Pedirle que **commitee al cerrar
  cada sección** de `tasks.md`, no al final.
- **Adjuntos a Trello**: subirlos con la API REST vía `curl` (`POST /1/cards/{id}/attachments`
  con `-F "file=@ruta"`), **no** con base64 por el MCP: así el archivo no entra al contexto.
  Ojo: al leer las credenciales del `.env` hay que limpiar espacios, o la URL sale malformada.
- **Trello MCP**: llamar `set_active_board` con `kdXM36sU` al empezar. El token vence: si da
  401, se regenera en https://trello.com/power-ups/admin con `expiration=never`.
- **Capturas de la vista**: copiar el reporte a `frontend/public/`, inyectarlo con
  `sessionStorage.setItem('nexus_report', ...)` desde la consola y abrir `/report`.
  Borrar después el archivo de `public/`.
- **Permisos**: el modo automático bloquea pushear a la rama de otro y mergear PRs ajenos.
  Hay que autorizarlo explícitamente.
- IDs útiles: lista Sprint 4 `6a1f6864889d8c5fe2ae2e5d`, lista QA `6a1642161e9946c1c9109254`.
  Miembros: Facundo `6a16173f16a431ed777fb012`, Matías `68d12d1ee9c16db321ba0bdd`,
  Fede `68d1e0706a8d223491726de3`.

---

## 2. Estado al cierre

`develop` está en `8676ebe`. Todo lo de abajo ya está mergeado.

### Agentes
| ID | Rol | Estado |
|----|-----|--------|
| 01 | Analista de Literatura | ✅ |
| 02 | Especialista Genómica | ✅ PR #12 (Facundo) |
| 03 | Consultor Clínico | ✅ |
| 04 | Árbitro Verificador | ⬜ **pendiente — #52, la toma Matías** |
| 05 | Navegador de Ensayos | ✅ PR #13 |
| 06 | Sintetizador | ⬜ pendiente — #62, va último |

### Lo que se cerró hoy
- **#54 Priorización EBM**: `pipeline/evidence.py`, con el nivel topeado por el tipo de
  publicación de la mejor fuente verificada. En QA con evidencia.
- **#53 Agente 05**: `agents/agent_05_trials.py` + `pipeline/trial_matching.py`. En QA.
- **#51 Agente 02**: mergeado (PR #12), ya estaba en QA con su evidencia.
- **4 fixes**: clientes Orphanet y PharmGKB (apuntaban a endpoints dados de baja), el debate
  que se caía si un agente fallaba en la Ronda 1, y los falsos genes del extractor.
- **Reparto de tareas** documentado en `.claude/backlog.md` y comentado en las tarjetas.

### Corrida real del Agente 05 sobre el caso de la tesis
21 ensayos, 2 excluidos por edad, 10 en el reporte. 2 de compatibilidad media y 8 baja,
**ninguna evaluación descartada** (el LLM no inventó NCT IDs). Orphanet marcó 1 coincidencia
exacta: ORPHA:85443. Artefactos en `output/corrida_agente05/`.

---

## 3. Pendiente (en orden)

### 3.1 Matías — #52 Agente 04 (Árbitro Verificador)
Tarjeta `6a1f68c7e380a0c147eb855a`. Toca `verification.py`, `evidence.py` y el paso 7 del
router. Primero `/opsx:propose`, frenar y mostrar el diseño.

- Consume `evidence.classify_hypothesis()` / `prioritize()` de #54, que ya están.
- **Dato clave para el diseño**: en la corrida real de hoy, **ninguno** de los PMIDs que
  citaron los agentes coincide con los que el RAG puso en el prompt, y los 15 resultaron
  discordantes. Los agentes no usan la literatura recuperada.
- Va junto con el **hallazgo G**: `BaseAgent.parse_hypotheses()` (`base_agent.py:92`) arma
  `Source(**s)` con lo que manda el LLM, así que acepta campos de verificación inventados.

### 3.2 Facundo — #73 y #71
- **#73** (`6aa9c5774810fc902e01ac69`): el regex `[A-Z]{2,6}\d{0,2}` no detecta genes con un
  dígito en el medio. Afecta a `SCN1A`, `SCN9A`, `SH3TC2` y `DYNC1H1`, los cuatro relevantes
  para el caso. Hay 4 tests marcados `xfail` en `tests/test_biomarkers.py` esperando el fix.
- **#71** (`6aa99fe42aca2b2e5c0a0dd2`): cliente ClinVar.

### 3.3 Fede — #74 y los hallazgos del RAG
- **#74** (`6aa9d25b6cbb6c906ac02064`): cliente Orphadata. Endpoint ya verificado:
  `GET https://api.orphadata.com/rd-associated-genes/orphacodes/{code}` (200, sin apiKey).
- **Hallazgo A**: el filtro de relevancia del RAG no filtra nada (`retriever.py:33`).
- **Hallazgo B**: los tests del RAG no son herméticos, pegan a PubMed de verdad.
- **Hallazgo H**: lint del frontend con 1 error y 1 warning previos.
- **PDF**: en la portada "NEXUS" se pisa con el subtítulo (`pdf_exporter.py:118-121`) y las
  celdas del resumen se salen del margen. Es lo que lee el médico.
- **Chores de Trello**: borrar el adjunto duplicado de #65 y renombrar el PNG sin extensión
  de #63.

### 3.4 #62 Sintetizador, al final
Depende de que exista el Agente 04 y pisa el `pdf_exporter.py` que va a tocar Fede.

### 3.5 Decisión de alcance pendiente
Fede midió que **los genes del caso (PMP22, MPZ, TTR) no tienen ninguna anotación en
PharmGKB**: son genes de enfermedad, no farmacogenes. El Agente 02 no recibe nada útil de esa
fuente en el caso base. Hay que decidir si la fuente correcta es ClinVar (#71) o si PharmGKB
se consulta solo cuando el caso trae fármacos en el historial.

---

## 4. Demo para el profesor

### Levantar el sistema
```bash
git checkout develop && git pull origin develop
# Backend (raíz del repo), con el Python del venv:
.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000   # :8000
# Frontend:
cd frontend && npm run dev                                        # :3000
```
El `.env` de la máquina de Matías ya está bien: no hace falta el `env PUBMED_API_KEY=`.
Falta **Tesseract**, así que los PDFs escaneados no andan y 3 tests de ingesta fallan.
Los PDFs con texto sí funcionan: hay uno listo en `output/demo_ingesta/informe_clinico.pdf`.

El caso de la tesis en texto está en `output/demo/caso.txt`. Una corrida completa tardaba
~4 min con dos agentes; **ahora son tres en la Ronda 1 más el Agente 05**, así que tarda más
y gasta más cuota de Groq.

**Respaldo por si Groq falla en vivo**: `output/demo/reporte.json` y `reporte.pdf` (con dos
agentes), y `output/corrida_agente05/` (con el Agente 05).

### Guion (~10 min)
1. Qué es NEXUS: genera **hipótesis de investigación**, no diagnósticos.
2. Cargar el caso (texto pegado o el PDF de `demo_ingesta`).
3. Vista de pipeline en tiempo real: ingesta → PICO → RAG → Ronda 1 → debate → Agente 05 y
   verificación en paralelo.
4. Reporte: hipótesis agrupadas por estado con el nivel EBM topeado, ensayos con
   compatibilidad orientativa, sede en Argentina y Orphanet, y la bibliografía con título
   citado vs. real. **Dato fuerte**: las 15 citas de los agentes eran discordantes con
   PubMed, y el sistema lo detecta. Por eso existe el Árbitro.
5. Exportar el PDF.
6. Qué sigue: Árbitro y Sintetizador, planificados con OpenSpec.

---

## 5. Setup de otra computadora
- `npm install -g @fission-ai/openspec@latest` (v1.11.0 o superior).
- MCP de Trello: `claude mcp add trello -s user -e TRELLO_API_KEY=... -e TRELLO_TOKEN=... -- cmd /c npx -y @delorenj/mcp-server-trello`.
  En Windows va **todo en una línea**: los backticks de continuación rompen el registro.
- `gh auth login`. Ojo: la cuenta `lussofacundo-iresm` no tiene permiso de push.
- `.env` con las keys, **comentarios en su propia línea** (si no, se reintroduce el bug de #65).
- Dependencias de Python en el venv del repo:
  `.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`.
