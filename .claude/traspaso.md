# Traspaso de sesión — 2026-10-04

Reemplaza al traspaso del 2026-09-15. El Sprint 4 queda con un solo pendiente grande:
el Agente 06, que espera una rama de Facundo.

**Para retomar con Claude Code**: "Leé `.claude/traspaso.md` y seguí como orquestador
desde la sección Pendiente."

---

## 1. Modo de trabajo acordado

Claude funciona como **orquestador**: planifica con OpenSpec lo grande y delega la
implementación a un subagente. Los arreglos chicos (un fix, un rebase, documentación) van
directo, sin propuesta. Reglas que eligió Matías:

| Tema | Regla |
|------|-------|
| Revisión | Frenar después de `/opsx:propose` o `/opsx:update` y mostrar el diseño. **No hacer apply sin su OK.** |
| Git | Rama por tarea desde `origin/develop` → push → PR a `develop` → merge sin esperar revisión. Asunto del merge: `merge: <qué> (Sprint 4)`. Sin `Co-Authored-By`. |
| Trello | Al terminar: adjuntar evidencia, actualizar la descripción con los números medidos y mover a `QA`. Juan Lencina evalúa por tarjeta y rechaza la que no prueba que funciona. |
| Cuota de Groq | Como máximo dos corridas reales por día. Los subagentes nunca llaman a Groq: verifican con el modo mock. |

Lecciones prácticas:
- **Un commit de "cierre" no significa cerrado.** El control de costos tenía 8 tareas
  destildadas en `tasks.md` detrás de un commit con ese nombre. Antes de mergear, mirar
  `rg '^\s*- \[ \]' openspec/changes/<cambio>/tasks.md`.
- **Medir antes de dar por buena una decisión de costo.** Dos techos de tokens que se bajaron
  "porque la salida es corta" rompieron al Árbitro (ver sección 3).
- **Antes de proponer algo, leer los comentarios de la tarjeta.** El Agente 06 ya tenía una
  propuesta de Facundo anunciada en un comentario.
- **Adjuntos a Trello en la máquina Linux de Matías**: el conector solo adjunta desde una URL.
  Para archivos locales, un script con `curl -F file=@...` contra
  `POST /1/cards/{id}/attachments`, que Matías corre con `! bash <script>`. Las credenciales
  están en `~/.claude.json`, dentro de `.projects["<ruta del repo>"].mcpServers.trello.env`,
  **no** en el `.env` del repo. Claude tiene bloqueada la lectura de `.env` y `.env.example`.
- **Trello MCP**: llamar `set_active_board` con `kdXM36sU` al empezar. Si da 401, el token
  venció: se regenera en https://trello.com/power-ups/admin con `expiration=never`.
- **Python**: el venv está en la raíz del repo (`.venv/bin/python`). Los worktrees no tienen
  uno propio; se usa ese con la ruta absoluta.
- **Worktrees**: van en `../tesis-iresm-worktrees/<nombre>`, nunca en `/tmp`.
- IDs útiles: lista Sprint 4 `6a1f6864889d8c5fe2ae2e5d`, lista QA `6a1642161e9946c1c9109254`.
  Miembros: Facundo `6a16173f16a431ed777fb012`, Matías `68d12d1ee9c16db321ba0bdd`,
  Fede `68d1e0706a8d223491726de3`.

---

## 2. Estado al cierre

`develop` está en `8560444`. La suite tiene 1009 tests en verde.

### Agentes
| ID | Rol | Estado |
|----|-----|--------|
| 01 | Analista de Literatura | ✅ |
| 02 | Especialista Genómica | ✅ PR #12 |
| 03 | Consultor Clínico | ✅ |
| 04 | Árbitro Verificador | ✅ PR #19 |
| 05 | Navegador de Ensayos | ✅ PR #13 |
| 06 | Sintetizador | ⬜ **pendiente — #62, espera la rama de Facundo** |

### Lo que se mergeó el 2026-10-04
| PR | Qué | Tarjeta |
|----|-----|---------|
| #22 | Control de costos: punto único de llamada al LLM, telemetría, modelo y techo por tarea, modo mock | #81, en QA |
| #23 | Registro de médicos con matrícula, revisión admin y `POST /api/analyze` protegido | #83, en QA |
| #24 | Script de medición y arreglo de los techos de tokens | #84, en QA |
| #25 | Una fuente malformada no deja a un agente fuera de la Ronda 1 | #85, en QA |
| #26 | Una hipótesis malformada no deja a un agente fuera de la ronda | #85, en QA |

Antes, el 2026-09-28, había entrado la landing explicativa (PR #21, tarjeta #82, en QA).

---

## 3. Lo que se midió (corridas reales del 2026-10-04)

`scripts/medir_costos.py` corre una sola pasada del pipeline y compara `GROQ_MAIN` contra
`GROQ_FAST` sobre las mismas entradas. `--mock` lo recorre sin cuota. Los artefactos quedan en
`output/medicion_costos/` (ignorado por git).

- **Un caso completo consume 77.516 tokens** en 27 llamadas y tarda unos 8 minutos.
  **Entran 2 casos por día** en la cuota gratuita de 200.000 tokens.
- Por agente: 01 → 20.605; 02 → 20.396; 03 → 21.279; 04 → 4.861; 05 → 7.179.
- **Los `gpt-oss` cuentan el razonamiento dentro de la salida.** Con techos de 512 y 1024,
  la agrupación del Árbitro y la planificación de términos del Agente 05 se cortaban y caían
  en el fallback. Volvieron a 4096. La agrupación usa unos 1.100 tokens de salida aunque
  devuelva solo índices.
- **Las tres tareas de salida validada se quedan en `GROQ_FAST`**: misma partición del
  agrupamiento sobre 14 hipótesis y 10 de 10 etiquetas de compatibilidad iguales. Es una
  corrida por modelo, no una muestra.
- **La Ronda 4 del debate reescribe, no reclasifica**: 11 hipótesis cambiaron de enunciado y
  ninguna de nivel ni de prioridad. Las revisiones del debate son un tercio del consumo.

---

## 4. Pendiente (en orden)

### 4.1 #62 Agente 06 (Sintetizador) — bloqueado
Facundo escribió la propuesta OpenSpec el 2026-09-23 (`openspec/changes/agente-06-sintetizador`,
commit `be1ce89`, rama `feature/s4-agente-06-sintetizador`) y **nunca la subió**: existe solo en
su máquina. El 2026-10-04 se le pidió por comentario en la tarjeta que la pushee.

**No escribir otra propuesta.** Cuando la rama esté en GitHub, revisar la suya con estos tres
puntos, que cambiaron en `develop` después de que la escribió:
- El Sintetizador necesita su tarea en `backend/agents/model_tasks.py` (modelo y techo, **no
  menos de 4096** por lo medido) y su respuesta grabada para el modo mock.
- Los tests que llamen a `POST /api/analyze` necesitan la fixture `client_medico_verificado`
  de `tests/conftest.py`.
- La tarjeta dice "reemplaza a `report_builder.py`" y su diseño agrega un `executive_summary`
  sobre el builder actual. Conviene que la propuesta diga que el builder determinista se
  conserva.

Su diseño, según el comentario: `synthesize()` corre una vez al final, agrega un resumen en
prosa como campo opcional de `StructuredReport`, nunca decide datos, y descarta el resumen
entero si cita un PMID, NCT o gen que no está en el reporte.

### 4.2 Verificar contra Groq los arreglos del parseo
Los PR #25 y #26 se verificaron con tests, no con una corrida real: la falla del Agente 03 es
intermitente y ese día no quedaba cuota. La próxima corrida real sirve de verificación: mirar
si aparece el aviso `[NEXUS] Respuesta del modelo saneada: …` y que el debate tenga tres agentes.

### 4.3 Cierre del control de costos
En `openspec/changes/control-de-costos-del-pipeline/tasks.md` quedan tres tareas:
- **6.2** Regenerar las respuestas grabadas del modo mock desde una corrida real. Hoy están
  escritas a mano.
- **6.4** Captura de la marca de modo mock en el frontend.
- **7.5** Los números medidos ya están en `.claude/CLAUDE.md` y `.claude/backlog.md`; falta
  llevarlos a `.claude/stack.md`.

La comparación de costo contra Claude, GPT-4o y Gemini que muestra `scripts/demo_costos.py`
usa una **muestra sintética**. Con el `costos.jsonl` real ya se puede recalcular con
`usage.recalculate()` y una tabla de tarifas.

### 4.4 Decisiones abiertas
- **Recorte de la Ronda 4**: ahorraría hasta un tercio del consumo. Hace falta más de una
  corrida para decidirlo.
- **Nivel III por saneamiento**: si el modelo manda un nivel de evidencia inválido, la
  hipótesis queda en III y en el reporte se ve igual que una declarada como III. Si para la
  tesis importa distinguirlas, hay que marcarlo en el reporte.
- **PharmGKB**: los genes del caso (PMP22, MPZ, TTR) no tienen anotaciones ahí. Sigue sin
  decidirse si la fuente correcta para el Agente 02 es ClinVar (#71).

### 4.5 Orden y limpieza
- `agente-02-genomica` es el único cambio OpenSpec cerrado que falta archivar: figura con 0 de
  26 tareas aunque está mergeado desde el 2026-09-16. Hay que tildar sus tareas antes de
  correr `/opsx:archive`. Los otros cuatro se archivaron el 2026-10-04 y sus specs están en
  `openspec/specs/` (12 en total).
- Quedan 6 ramas locales `worktree-agent-*` sin revisar. Los worktrees y las demás ramas ya
  mergeadas se borraron; lo que tenían en `output/` se copió a `output/de-worktrees/`.
- Tarjetas #73 y #75 (Facundo y Fede): mergeadas el 2026-09-16 y todavía en Sprint 4 sin
  evidencia.

### 4.6 De otros integrantes
- **Facundo**: #71 cliente ClinVar.
- **Fede**: #74 cliente Orphadata, #76 filtro de relevancia del RAG, #77 lint del frontend,
  #78 portada del PDF.
- Sin asignar: #79 (comentario en el `.env` que desactiva la verificación) y #80 (un agente
  como sostén y objetor de la misma hipótesis).

---

## 5. Demo para el profesor

### Levantar el sistema
```bash
git checkout develop && git pull origin develop
# Backend, desde la raíz del repo:
.venv/bin/python -m uvicorn backend.main:app --port 8000    # :8000
# Frontend:
cd frontend && npm run dev                                   # :3000
```

**Desde el PR #23 el análisis exige sesión.** Antes de la demo:
1. Definir `SECRET_KEY` en el `.env`.
2. Crear el primer admin: `.venv/bin/python -m backend.cli crear-admin --email <email>`
   (pide la contraseña sin mostrarla).
3. Registrar un médico en `/registro`, entrar como admin en `/ingresar` y aprobarlo en
   `/admin/pendientes`.

Una corrida real tarda unos 8 minutos y gasta más de un tercio de la cuota diaria: no hacer
pruebas con Groq el mismo día de la demo.

**Respaldo por si Groq falla en vivo**: arrancar el backend con `NEXUS_MOCK_LLM=1`. El pipeline
corre completo con respuestas grabadas del LLM (PubMed, ClinicalTrials.gov y Orphanet se
siguen consultando de verdad) y el reporte queda marcado como mock en el JSON, el PDF y la
pantalla. Los archivos de respaldo de `output/demo/` que nombraba el traspaso
anterior **no están en la máquina Linux de Matías**.

### Guion (~10 min)
1. Qué es NEXUS: genera **hipótesis de investigación**, no diagnósticos. La landing en `/` lo
   explica.
2. Registro e ingreso: solo un médico con matrícula verificada por un admin puede analizar.
3. Cargar el caso en `/analizar`.
4. Vista de pipeline en tiempo real: ingesta → PICO → RAG → Ronda 1 → debate → verificación →
   Árbitro → Navegador de ensayos.
5. Reporte: hipótesis de consenso con el nivel EBM topeado, veredictos del Árbitro, ensayos
   con compatibilidad y la bibliografía con título citado vs. real.
6. Exportar el PDF.
7. Costos: 77.516 tokens por caso, medidos; y cómo medir destapó tres defectos que el sistema
   escondía detrás de un fallback.
8. Qué sigue: el Sintetizador.

---

## 6. Setup de otra computadora
- `npm install -g @fission-ai/openspec@latest` (v1.11.0 o superior).
- MCP de Trello: `claude mcp add trello -s user -e TRELLO_API_KEY=... -e TRELLO_TOKEN=... -- npx -y @delorenj/mcp-server-trello`.
  En Windows va con `cmd /c` adelante de `npx` y **todo en una línea**.
- `gh auth login`. Ojo: la cuenta `lussofacundo-iresm` no tiene permiso de push.
- `.env` con las keys y `SECRET_KEY`, **comentarios en su propia línea**.
- Dependencias de Python en el venv del repo: `.venv/bin/python -m pip install -r backend/requirements.txt`
  (en Windows, `.venv/Scripts/python.exe`).
- Tesseract para los PDFs escaneados. En la máquina Linux de Matías está instalado.
