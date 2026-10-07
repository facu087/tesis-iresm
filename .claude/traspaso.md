# Traspaso de sesión — 2026-10-06

Reemplaza al traspaso del 2026-10-04. Los seis agentes ya están en `develop`: el Agente 06
lo mergeó Facundo el 2026-10-06 (PR #35) y una revisión posterior encontró dos defectos que
se arreglan en la rama `fix/s4-agente06-citas-y-pdf` (ver 4.1). El 2026-10-06 también se
grabaron las respuestas del modo mock desde una corrida real y se encontró y arregló un
defecto del debate (ver secciones 2 y 3).

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

`develop` está en `cc5105b` (PR #38). La suite tenía 1113 tests después del PR #32; con el
PR #38 pasan 1150 en ~57 s, y esta rama deja 1186. Los fallos intermitentes de
`tests/test_agent_05_trials.py` quedaron resueltos (ver 4.7).

### Agentes
| ID | Rol | Estado |
|----|-----|--------|
| 01 | Analista de Literatura | ✅ |
| 02 | Especialista Genómica | ✅ PR #12 |
| 03 | Consultor Clínico | ✅ |
| 04 | Árbitro Verificador | ✅ PR #19 |
| 05 | Navegador de Ensayos | ✅ PR #13 |
| 06 | Sintetizador | ✅ PR #35 (mergeado el 2026-10-06; correcciones en 4.1; pendientes en `fix/s4-agente06-pendientes`) |

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
| #35 | Agente 06 (Sintetizador), de Facundo (merge `1f11917`); ver 4.1 |
| #37 | Facundo: arregla el import circular entre el Agente 06 y el extractor de biomarcadores (el import de `_NON_GENE_TERMS` pasó a ser diferido) |
| #38 | Los tests nunca llaman al proveedor real (merge `cc5105b`); ver 4.9 |

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

### 4.1 #62 Agente 06 (Sintetizador) — mergeado, con correcciones y observaciones abiertas
El PR #35 (Facundo) entró a `develop` el 2026-10-06 (merge `1f11917`). Agregó, según el
código y `openspec/changes/agente-06-sintetizador/`:
- `backend/agents/agent_06_synthesizer.py`: `SynthesizerAgent.synthesize()` escribe un
  párrafo `executive_summary` (máximo 5 oraciones) sobre el `StructuredReport` ya armado.
  Corre una vez al final, después de `build_export()`: **no reemplaza** a `report_builder.py`.
  Nunca decide datos y nunca propaga excepciones (si falla, devuelve `None`).
- Guarda anti-invención (`check_invention()`): descarta el resumen **entero** si cita un
  PMID, un NCT o un símbolo génico que no está en el reporte.
- Tarea `agente06_sintesis` en `model_tasks.py` (`GROQ_MAIN`, techo 4096), campo opcional
  `executive_summary` en `StructuredReport`, respuesta grabada para el modo mock, sección en
  el PDF y en `/report`, tipo en `types.ts`, `scripts/demo_agente06.py` y
  `tests/test_agent_06_synthesizer.py`.

Defectos de la revisión posterior, **arreglados y mergeados** (rama
`fix/s4-agente06-citas-y-pdf`, un commit cada uno, con tests):
- **El resumen podía presentar como respaldo una cita refutada.** `build_context()` le daba al
  LLM todos los PMIDs sin su estado y la guarda aceptaba cualquiera presente en el reporte,
  también uno `inexistente` o `discordante`. Ahora solo se puede citar un PMID cuya fuente
  quedó `verificada` en la verificación contra PubMed; si aparece en varias fuentes con
  estados distintos, solo vale cuando todas lo confirman (criterio conservador). El contexto
  lista los confirmados y de los demás solo dice cuántas referencias no se confirmaron; un
  PMID no confirmado en el resumen se trata como inventado y lo descarta entero.
- **El PDF se caía con el resumen.** `_executive_summary()` pasaba el texto sin escapar a un
  `Paragraph` de ReportLab: `a<b y c>d` levantaba `ValueError` y `<font size=40>` se
  interpretaba como marcado. Ahora se escapa y se dibuja literal.

**Observaciones de la revisión** y su estado en la rama `fix/s4-agente06-pendientes`
(feature `odd/tasks/agente06-pendientes.md`):
- **a.** La guarda de genes toma cualquier sigla de 2 a 8 caracteres en mayúsculas como
  símbolo génico: una sigla ausente del reporte ("DM2", "HSAN") descarta todo el resumen.
  **Mitigada, no cerrada**: la guarda no se tocó (sigue igual de estricta), pero el prompt
  ahora le dice al modelo que no introduzca siglas ni símbolos ausentes del reporte y que
  los escriba con palabras. **T4 cerrada el 2026-10-07**: con la regrabación completa (ver 4.3) el reporte
  mock es el de la corrida y la guarda acepta el resumen grabado: el Agente 06 se ve en mock.
- **b.** El contexto se truncaba a 6000 caracteres desde el final (ensayos y verificación).
  **Cerrada**: `build_context()` acorta solo los textos libres largos (narrativa,
  fundamentos y notas del Árbitro), con el mayor tope común que entre en el límite, y deja
  completos hipótesis (con sus PMIDs confirmados), ensayos y verificación. Si lo obligatorio
  ya excede el límite, no se recorta nada obligatorio y el contexto lo supera.
- **c.** Texto libre sin escapar en el PDF. **Cerrada**: `_t()` en `pdf_exporter.py` escapa
  cada valor al interpolarlo en un `Paragraph` (ver 4.5).

El cambio OpenSpec `agente-06-sintetizador` se archivó el 2026-10-06 (PR #42): la 6.2 se
verificó en el navegador con un reporte de prueba cargado en `sessionStorage` (la sección
aparece arriba de las hipótesis y desaparece con `executive_summary: null`). En mock sigue sin
haber resumen hasta cerrar la T4.

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
- **6.4** Hecha el 2026-10-06: `npm run build` compila en el checkout principal y la captura
  del aviso de modo mock se tomó recorriendo el flujo real en un navegador (19 llamadas mock,
  0 reales). Evidencia adjunta a la tarjeta #81 de Trello el 2026-10-06 (dos capturas y un `.txt`;
  copia local en `output/evidencia/81/`).

Con 6.2, 6.4 y 7.5 hechas, `control-de-costos-del-pipeline` quedó sin tareas abiertas y se
archivó el 2026-10-06 junto con `landing-demostrativa`. Sus specs están en `openspec/specs/`
(`modo-mock-pipeline`, `presupuesto-por-tarea` y `telemetria-de-costos`).

**El modo mock reproduce la corrida completa** (PR #53 + regrabación del 2026-10-07, rama
`feature/s4-regrabar-mock`). `backend/mock/grabadas.json` tiene las 22 respuestas de la
corrida real del 2026-10-07, una por llamada y con su agente. Medido en mock: 9 hipótesis de
consenso sin repetidas (antes 10 con 5 textos repetidos), 10 ensayos y el `executive_summary`
del Agente 06. `regenerar_mock.py` se usó por primera vez con una grabación real y funcionó sin
cambios. Para regrabar otra vez:

```bash
python scripts/medir_costos.py --grabar
python scripts/regenerar_mock.py output/medicion_costos/grabacion.json backend/mock/grabadas.json --fecha AAAA-MM-DD
pytest tests/test_mock_responses.py tests/test_mock_pipeline.py -q
```

Los tests del mock que fijan el contenido de la grabación (fecha, críticas por agente) hay que
actualizarlos con cada regrabación. La corrida del 2026-10-07 (ya con el prompt del Agente 02
sin genes) midió 84.867 tokens en 27 llamadas (5 reintentadas por 429) y 493 s, ninguna
respuesta cortada. El PDF de respaldo para la demo, generado en mock con verificación real
contra PubMed, quedó en `output/demo_respaldo/reporte_mock.pdf` (local, gitignoreado).
Falta la captura real de la tarjeta #80.

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
- No queda ningún cambio OpenSpec abierto (`openspec list` vacío al 2026-10-06). Ese día se
  archivaron `control-de-costos-del-pipeline` y `landing-demostrativa` (PR #45),
  `cliente-clinvar` (PR #43) y `agente-02-genomica` (PR #44). El CLI `openspec` está instalado
  en esta máquina.
- `agente-02-genomica` figuraba con 0 de 26 tareas y varias no estaban cumplidas: el commit
  `4d57f76` (tareas 7.1-7.3, `scripts/demo_agente02.py` y tests) había quedado fuera del PR #12.
  El PR #44 (Facundo) lo cerró: la guarda anti-invención ahora lee `case_genetic_findings` del
  JSON crudo (antes lo buscaba en la `Hypothesis` ya parseada, que no tiene ese campo, y con
  hallazgos en el caso no degradaba nada), PharmGKB usa `pharmgkb_breaker`, y se agregaron los
  tests de tres agentes y el demo. El `SYSTEM_PROMPT` del Agente 02 nombraba `TTR p.Val30Met` en
  su ejemplo JSON, contra la spec; desde `fix/s4-prompt-agente02-sin-genes` usa un marcador
  genérico, pide `case_genetic_findings` vacío en modo orientación y un test impide volver a
  nombrar genes o variantes en el prompt.
- Quedan 6 ramas locales `worktree-agent-*` sin revisar. Los worktrees y las demás ramas ya
  mergeadas se borraron; lo que tenían en `output/` se copió a `output/de-worktrees/`.
- **Texto libre del PDF** (resuelto en `fix/s4-agente06-pendientes`): todo valor que llega a un
  `Paragraph` de `backend/pipeline/pdf_exporter.py` pasa por `_t()`, que escapa `&`, `<` y
  `>` y traduce los caracteres sin glifo antes de escapar; el marcado propio del módulo se
  conserva. Cubre narrativa, hipótesis (texto, fundamento, nota de evidencia, veredicto,
  agentes, objeciones), fuentes, divergencias, ensayos, enfermedades raras, versión y
  descargo. Las celdas de tabla con texto plano (perfil del paciente, etc.) no interpretan
  marcado y no hacen falta. Las URL se imprimen como texto, no como enlaces.
- Tarjeta #73 (Facundo): evidencia adjunta y en QA desde el 2026-10-06. La #75 (Fede) sigue
  en Sprint 4 sin evidencia.

### 4.6 De otros integrantes
- **Facundo**: #71 cliente ClinVar — hecho (PR #41) y en QA desde el 2026-10-06.
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

El defecto de fondo se arregló el 2026-10-06 (rama `fix/s4-limitador-sin-lock`):
`RateLimiter.acquire()` reserva el turno de forma síncrona y duerme después, sin
`asyncio.Lock`, así que usar los limitadores globales desde más de un `asyncio.run` ya no
levanta `RuntimeError`. Lo cubren dos tests nuevos de `tests/test_rate_limiter.py`. La fixture
`_limitadores_aislados` sigue haciendo falta para no arrastrar turnos consumidos entre tests.
Los `ApiCircuitBreaker` conservan su lock: no tienen ningún `await` adentro, así que nunca hay
contención.

En Windows fallan 4 tests que no dependen de esto: tres de `tests/test_ingesta.py` por falta
de Tesseract y `test_hermetico_sin_red_analisis_completo_en_modo_mock` por la codificación de
la salida de un subproceso (`UnicodeDecodeError`). Fallan igual en `develop`.

### 4.8 Evidencia de Trello a regenerar
Los reportes y la evidencia de Trello producidos **antes del 2026-10-06** que muestren el
debate adversarial salieron de corridas donde las críticas no llegaban a los agentes. La que
muestre el debate hay que regenerarla.

### 4.9 Los tests no pueden llamar al proveedor real (PR #38)
Desde el PR #35, los tests de análisis de `tests/test_api.py` llamaban a Groq de verdad: varios
módulos hacen `load_dotenv()` al importarse y el `.env` real traía `GROQ_API_KEY`. Medido en
`output/costos.jsonl`: **88 llamadas reales del Agente 06 el 2026-10-06, 38 fallidas por
límite de velocidad, unos 47.000 tokens** de la cuota. La suite pasó de ~60 s a ~90 s y luego
se colgó con la cuota agotada. La fixture autouse `_sin_clave_del_proveedor` de
`tests/conftest.py` quita `GROQ_API_KEY` antes de cada test, y un test que sí necesita una
clave pone una falsa; ahora una llamada sin aislar falla fuerte. Tras el arreglo pasan 1150
tests en ~57 s. Regla práctica: si la suite tarda mucho más o se cuelga, hay una llamada de
red o de proveedor sin aislar.

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
8. Qué sigue: el Sintetizador ya está mergeado; falta que el resumen se vea en mock (T4 de 4.1, necesita una llamada real).

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
