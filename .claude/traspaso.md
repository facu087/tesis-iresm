# Traspaso de sesión — 2026-10-06

Reemplaza al traspaso del 2026-10-04. El Sprint 4 queda con un solo pendiente grande:
el Agente 06, que espera una rama de Facundo. El 2026-10-06 se grabaron las respuestas
del modo mock desde una corrida real y se encontró y arregló un defecto del debate (ver
secciones 2 y 3).

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

`develop` está en `aaa8366`. La suite tiene 1113 tests (después del PR #32); en corridas
completas dos tests de `tests/test_agent_05_trials.py` fallaron una vez cada uno (ver 4.7).

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

### Lo que se mergeó el 2026-10-06
| PR | Qué |
|----|-----|
| #30 | Grabador de respuestas crudas (`backend/mock/recorder.py`), opción `--grabar` de `scripts/medir_costos.py` y las doce tareas del modo mock con respuestas grabadas (`backend/mock/grabadas.json`) |
| #31 | Las críticas del debate llegan a su destinatario: el parser normaliza el destinatario y el prompt muestra un ID real de ejemplo |
| #32 | Una crítica con destinatario ambiguo queda sin atribuir; el modo real ya no depende del archivo de respuestas grabadas (carga diferida) |

---

## 3. Lo que se midió

### Corridas reales del 2026-10-06 (cifra vigente)

`scripts/medir_costos.py` corre una sola pasada del pipeline y compara `GROQ_MAIN` contra
`GROQ_FAST` sobre las mismas entradas. `--mock` lo recorre sin cuota. Los artefactos quedan en
`output/medicion_costos/` (ignorado por git).

- **Un caso completo consume 80.458 tokens** (43.240 de entrada y 37.218 de salida) en 28
  llamadas (7 fallidas por límite de velocidad y reintentadas); la pasada base tarda 505 s y
  ninguna respuesta se cortó por el techo. **Siguen entrando 2 casos por día** en la cuota
  gratuita de 200.000 tokens. Cada ejecución de `scripts/medir_costos.py` gasta además unos
  20.000 tokens en la comparación de modelos. Artefactos en
  `output/medicion_costos/fix_criticas/` (ignorado por git).
- Por agente: 01 → 21.889; 02 → 20.796; 03 → 21.334; 04 → 5.696; 05 → 7.668; PICO y
  biomarcadores → 3.075.
- **Defecto encontrado: las críticas del debate no llegaban a nadie.** En la Ronda 2 el
  modelo declaraba el destinatario como "Agent 02", "Agent01" o "Agent03", y el debate enruta
  por ID exacto ("01"/"02"/"03"). En la primera corrida real del día, 0 de 21 críticas
  llegaron a su destinatario: las Rondas 3 y 4 revisaban sin críticas, y lo mismo pasaba en
  todas las corridas anteriores. Arreglo en el PR #31 (normalización y ejemplo real en el
  prompt) y refinamiento en el PR #32 (solo se atribuye si el destinatario es inequívoco y
  corresponde a un agente que fue criticado; lo demás queda sin atribuir y no se reasigna).
- **Confirmado contra Groq** (segunda corrida real, con el arreglo): 18 de 18 críticas
  llegaron a su destinatario (7 al agente 01, 3 al 02, 8 al 03) y el modelo devolvió el ID de
  dos dígitos en todas. `debate_revision` pasó de 11.186 a 16.917 tokens de entrada: las
  revisiones ahora reciben las críticas.
- **Las cifras anteriores quedan superadas, no erróneas**: los 77.516 tokens del 2026-10-04
  (27 llamadas, por agente 01 → 20.605; 02 → 20.396; 03 → 21.279; 04 → 4.861; 05 → 7.179) y
  los 78.158 de la primera corrida del 2026-10-06 se midieron con el debate corriendo **sin
  críticas**. Los registros fechados las conservan como se midieron.

### Corridas reales del 2026-10-04 (debate sin críticas)

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
su máquina. El 2026-10-04 se le pidió por comentario en la tarjeta que la pushee; al
2026-10-06 la rama seguía sin estar en GitHub.

**No escribir otra propuesta.** Cuando la rama esté en GitHub, revisar la suya con estos cuatro
puntos, que cambiaron en `develop` después de que la escribió:
- El Sintetizador necesita su tarea en `backend/agents/model_tasks.py` (modelo y techo, **no
  menos de 4096** por lo medido) y su respuesta para el modo mock. Desde el 2026-10-06 las
  respuestas del modo mock ya no se escriben a mano: la del Sintetizador tiene que ser una
  grabación en `backend/mock/grabadas.json`, o la propuesta tiene que decir cómo se produce.
- Los tests que llamen a `POST /api/analyze` necesitan la fixture `client_medico_verificado`
  de `tests/conftest.py`.
- La tarjeta dice "reemplaza a `report_builder.py`" y su diseño agrega un `executive_summary`
  sobre el builder actual. Conviene que la propuesta diga que el builder determinista se
  conserva.

Su diseño, según el comentario: `synthesize()` corre una vez al final, agrega un resumen en
prosa como campo opcional de `StructuredReport`, nunca decide datos, y descarta el resumen
entero si cita un PMID, NCT o gen que no está en el reporte.

### 4.2 Verificar contra Groq los arreglos del parseo — parcial
Los PR #25 y #26 (fuente malformada y hipótesis malformada) se verificaron con tests. Las dos
corridas reales del 2026-10-06 sirvieron para mirar el resultado:
- **Verificado**: el debate tuvo los tres agentes (01, 02 y 03) con hipótesis, críticas,
  revisiones y recitaciones.
- **No verificado**: el aviso `[NEXUS] Respuesta del modelo saneada: …` no apareció en ninguna
  de las dos corridas, es decir, el modelo no devolvió ninguna respuesta malformada y los
  arreglos de parseo tolerante no se ejercitaron. Siguen verificados solo por tests; la falla
  del Agente 03 es intermitente y hay que esperar a que ocurra en una corrida real.

### 4.3 Cierre del control de costos
En `openspec/changes/control-de-costos-del-pipeline/tasks.md`:
- **6.2** Hecha el 2026-10-06: las doce tareas del modo mock usan respuestas de una corrida
  real. Salvedad: las que citan posiciones, PMIDs o NCT pertenecen a esa corrida; en mock se
  aplican por posición a hipótesis distintas y dependen de que PubMed y ClinicalTrials.gov
  devuelvan lo mismo.
- **7.5** Hecha el 2026-10-06: `.claude/CLAUDE.md`, `.claude/backlog.md` y `.claude/stack.md`
  llevan los números medidos.
- **6.4** **Pendiente**: captura de la marca de modo mock en el frontend (el código está y
  pasa `tests/test_pdf_exporter.py` y `npx tsc --noEmit`).

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
  correr `/opsx:archive`. El CLI `openspec` **no está instalado en esta máquina**:
  `npm install -g @fission-ai/openspec@latest` antes de archivar. Los otros cuatro se archivaron el 2026-10-04 y sus specs están en
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

### 4.7 Observaciones de la revisión nativa y tests intermitentes
La revisión nativa de los PR #30 y #31 se aprobó con seis observaciones no bloqueantes; la 1 y
la 2 se arreglaron en el PR #32. Siguen abiertas:
- **3.** `close_recorder()` en `backend/mock/recorder.py` solo captura `OSError`.
- **4.** El camino real de `--grabar` no tiene test automatizado.
- **5.** Un test de `tests/test_recorder.py` corre el script completo en un subproceso y, en
  modo mock, las consultas externas igual salen a la red.
- **6.** `scripts/medir_costos.py` informa que la grabación se escribió aunque la escritura
  haya fallado.

Tests intermitentes (resueltos el 2026-10-06): en corridas de la suite completa fallaban, de a
uno y en corridas distintas, tests de `tests/test_agent_05_trials.py`. La causa era que los
limitadores de `backend/external/rate_limiter.py` son objetos de módulo: `acquire()` duerme con
el `asyncio.Lock` tomado cuando la ráfaga está agotada, el lock queda ligado al event loop de
ese test y el siguiente que lo disputa recibe un `RuntimeError` que el Agente 05 trata como
caída de la API. La fixture `_limitadores_aislados` de `tests/conftest.py` deja limitadores y
breakers como nuevos antes de cada test; `tests/test_aislamiento_limitadores.py` lo cubre.

Queda abierto el defecto de fondo en producción: el limitador sigue durmiendo con el lock
tomado. Con un único event loop (uvicorn) no se manifiesta, pero cualquier código que use
`asyncio.run` más de una vez sobre esos limitadores puede degradar en silencio (estado
`parcial`, ensayos faltantes). El arreglo sería reservar el turno y dormir fuera del lock.

### 4.8 Evidencia de Trello a regenerar
Los reportes y la evidencia de Trello producidos **antes del 2026-10-06** que muestren el
debate adversarial salieron de corridas donde las críticas no llegaban a los agentes. La que
muestre el debate hay que regenerarla.

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

Una corrida real tarda unos 8 minutos y gasta cerca de 40% de la cuota diaria (80.458 de 200.000 tokens): no hacer
pruebas con Groq el mismo día de la demo.

**Respaldo por si Groq falla en vivo**: arrancar el backend con `NEXUS_MOCK_LLM=1`. El pipeline
corre completo con respuestas grabadas de una corrida real del LLM (PubMed, ClinicalTrials.gov y Orphanet se
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
7. Costos: 80.458 tokens por caso, medidos; y cómo medir destapó defectos que el sistema
   escondía detrás de un fallback, entre ellos que las críticas del debate no llegaban a su
   destinatario.
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
