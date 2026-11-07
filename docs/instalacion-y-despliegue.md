# Instalación, configuración y despliegue de NEXUS

Esta guía describe cómo instalar, configurar y desplegar NEXUS tal como está el
código en el repositorio. Todos los comandos se ejecutan desde la raíz del
repositorio salvo que se indique otra cosa.

NEXUS consta de dos procesos independientes:

- **Backend**: API FastAPI (`backend.main:app`), Python.
- **Frontend**: aplicación Next.js (`frontend/`), Node.js.

---

## 1. Requisitos

| Componente | Versión / detalle | Fuente |
|------------|-------------------|--------|
| Python | 3.11 o superior; el CI usa 3.12 | `.claude/CLAUDE.md`, `.github/workflows/ci.yml` |
| Node.js | 22 (versión usada por el CI). `frontend/package.json` no declara `engines` | `.github/workflows/ci.yml` |
| npm | El que acompaña a Node 22 (el CI instala con `npm ci`) | `.github/workflows/ci.yml` |
| Tesseract OCR | Binario `tesseract` en el `PATH` (paquete `tesseract-ocr` en Debian/Ubuntu) | `.github/workflows/ci.yml` |
| Datos de idioma OCR | Incluidos en el repositorio: `.tessdata/spa.traineddata` y `.tessdata/eng.traineddata` | `backend/ingestion/extractor.py` |

El extractor fija `TESSDATA_PREFIX` a la carpeta `.tessdata/` del repositorio
durante el OCR, por lo que no es necesario instalar paquetes de idioma del
sistema. Solo se requiere el binario.

**Espacio en disco.** `backend/requirements.txt` incluye `sentence-transformers`,
que arrastra `torch`. Por defecto, `pip` instala la variante con soporte CUDA,
que agrega aproximadamente 5,6 GB de librerías NVIDIA que NEXUS no utiliza (el
código corre en `device="cpu"`). Se recomienda instalar antes la variante CPU
de `torch` (ver sección 2).

---

## 2. Backend en entorno local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# Variante CPU de torch (opcional, recomendada): evita las librerías CUDA.
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r backend/requirements.txt
```

Antes de arrancar, crear el archivo `.env` en la raíz a partir de
`.env.example` y completar al menos las variables obligatorias de la sección 4:

```bash
cp .env.example .env
```

El backend carga `.env` con `python-dotenv` desde el directorio de trabajo, por
lo que debe arrancarse desde la raíz del repositorio:

```bash
uvicorn backend.main:app --reload
```

Por defecto, uvicorn escucha en `http://127.0.0.1:8000`. Comprobación de estado:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"NEXUS","version":"0.3.0"}
```

Al arrancar, el backend crea el esquema SQLite si no existe
(`create_db_and_tables()` en el `lifespan`) e inicia la limpieza periódica de
sesiones vencidas. La documentación interactiva de la API está disponible en
`/docs` y `/redoc` solo fuera de producción.

---

## 3. Frontend en entorno local

```bash
cd frontend
npm install
```

Crear `frontend/.env.local` (gitignoreado):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

- `NEXT_PUBLIC_API_URL`: base del backend. Si no se define, `frontend/src/lib/api.ts`
  usa `http://localhost:8000`.
- `NEXT_PUBLIC_SITE_URL`: origen público del despliegue (con `https://` en
  producción), usado por las etiquetas para compartir. Vacía o malformada cae a
  `http://localhost:3000` con un aviso, sin romper el build
  (`frontend/src/lib/siteUrl.ts`).

Arrancar el servidor de desarrollo:

```bash
npm run dev
```

La aplicación queda en `http://localhost:3000`. Para una compilación de
producción: `npm run build` y luego `npm run start`.

El origen del frontend debe figurar en `ALLOWED_ORIGINS` del backend; el valor
por defecto (`http://localhost:3000`) ya cubre el entorno local.

---

## 4. Variables de entorno

Las variables del backend se definen en `.env` (raíz). Las del frontend, en
`frontend/.env.local`. La columna "Obligatoria" indica si el sistema puede
funcionar sin ella.

| Variable | Obligatoria | Valor por defecto | Función |
|----------|-------------|-------------------|---------|
| `GROQ_API_KEY` | Sí, salvo en modo mock | (ninguno) | Clave del proveedor del modelo (Groq, `gpt-oss`). Sin ella y sin modo mock, el análisis falla con un error explícito. |
| `SECRET_KEY` | Sí | (ninguno) | Firma la cookie de sesión (HMAC). Sin ella, el primer login levanta `SecretKeyNoConfigurada`. |
| `ALLOWED_ORIGINS` | Sí en producción | `http://localhost:3000` (si no está definida) | Lista blanca, separada por comas, para CORS y para la validación `Origin`/`Referer` (mitigación CSRF). Se valida al arrancar. |
| `ALLOWED_HOSTS` | No (recomendada en producción) | Sin restricción | Hosts aceptados en el encabezado `Host`, separados por comas. No acepta `*`. En producción sin definir, avisa por stderr. |
| `ENVIRONMENT` | No | `development` | `production` (sin distinguir mayúsculas) activa HSTS, cookie `Secure`, orígenes `https` obligatorios y desactiva `/docs`. |
| `SESSION_TTL_MINUTES` | No | `60` | Duración de la sesión de cuenta. |
| `SESSION_CLEANUP_INTERVAL_MINUTES` | No | `15` | Intervalo de borrado de sesiones vencidas. `0` desactiva la tarea. |
| `NEXUS_DB_PATH` | No | `./data/nexus.db` | Archivo SQLite de cuentas, sesiones y auditoría. |
| `NEXUS_MOCK_LLM` | No | Apagado | Activa el modo mock (sección 6). Cualquier valor distinto de vacío, `0`, `false` o `no` lo enciende. |
| `NEXUS_EMBEDDING_MODEL` | No | `NeuML/pubmedbert-base-embeddings` | Modelo de embeddings del RAG. Cambiarlo exige reindexar (sección 8). |
| `NEXUS_RAG_MIN_SCORE` | No | `0.55` | Puntaje mínimo de relevancia de un artículo recuperado. Escala `(1 + coseno) / 2`. Un valor inválido o fuera de `[0, 1]` avisa y usa el valor por defecto. |
| `PUBMED_API_KEY` | No | (ninguno) | Aumenta el límite de consultas a NCBI E-utilities. |
| `ORPHANET_API_KEY` | No | Valor por defecto del cliente | La API responde sin credencial. Un valor con espacios o `#` se descarta con aviso. |
| `PROVINCIAL_LICENSE_SEARCH_URL` | No | (ninguno) | Enlace al buscador provincial de matrículas que se muestra al administrador. |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` | No | (ninguno) | Reservadas para la arquitectura de destino. El código actual no las lee. |
| `MAX_FILE_SIZE_MB` | No | `50` | Tamaño máximo del archivo subido a `POST /api/analyze`, en MB. Un archivo mayor recibe un 413. Un valor que no es un entero positivo avisa por stderr y usa 50 (ver nota al final). |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Base del backend para el frontend. |
| `NEXT_PUBLIC_SITE_URL` | No | `http://localhost:3000` | Origen público del frontend. |

**Mínimo para arrancar en local:** `SECRET_KEY` y `GROQ_API_KEY` (o
`NEXUS_MOCK_LLM=1` en su lugar). `ALLOWED_ORIGINS` puede omitirse en local,
pero si se define debe ser válida: el servidor no arranca con `*`, con una
lista vacía, con un origen sin esquema o con ruta, ni con `http` fuera de
`localhost` en producción.

Para generar un valor aleatorio de `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 5. Alta del primer administrador

Ninguna instalación trae una cuenta administradora por defecto. Se crea por
línea de comandos (`backend/cli.py`):

```bash
python -m backend.cli crear-admin --email admin@dominio.example
```

La contraseña se solicita de forma interactiva, sin eco. El comando acepta
también `--password` para scripts, aunque no se recomienda porque queda en el
historial de la shell. Falla si ya existe una cuenta con ese email, y puede
ejecutarse más de una vez para dar de alta varios administradores. Crea el
esquema de la base si todavía no existe.

**Flujo de aprobación de médicos.** Un médico se registra en `/registro` con su
matrícula y acepta el consentimiento de la Ley 25.326; su cuenta queda
pendiente y no puede ejecutar análisis (`POST /api/analyze` y
`POST /api/report/pdf` responden 403). Un administrador revisa las solicitudes
en `/admin/pendientes`, contrasta la matrícula en los buscadores oficiales y
aprueba o rechaza con motivo; cada decisión queda registrada en la tabla de
auditoría. Un médico rechazado puede corregir los datos y reenviar la solicitud
desde `/cuenta`. El detalle de uso se describe en
[manual-de-uso.md](manual-de-uso.md).

---

## 6. Modo mock

Con `NEXUS_MOCK_LLM=1`, el pipeline usa respuestas grabadas de una corrida real
(`backend/mock/grabadas.json`) en lugar de llamar a Groq. Sirve para
demostraciones y desarrollo sin consumir cuota:

```bash
NEXUS_MOCK_LLM=1 uvicorn backend.main:app --reload
```

- Al arrancar, el backend informa por stderr que el modo mock está activo.
- Las respuestas grabadas pasan por el mismo parseo y las mismas validaciones
  que una respuesta real.
- El reporte queda marcado (`metadata.mock`), y la marca se muestra en el
  frontend y en el PDF.
- La Ronda 1 usa los artículos del RAG incluidos en la grabación, sin consultar
  PubMed.

**Salvedad:** la verificación de PMIDs contra PubMed y la búsqueda de ensayos en
ClinicalTrials.gov siguen consultando esos servicios en vivo. Una demostración
en modo mock necesita conexión a internet y sus resultados en esas dos etapas
pueden variar con el tiempo.

---

## 7. Despliegue en producción

El backend **no termina TLS**. Debe ejecutarse detrás de un proxy inverso
(nginx, Caddy o un balanceador) que sí lo haga.

### 7.1 Configuración requerida

En el `.env` del backend:

```bash
ENVIRONMENT=production
SECRET_KEY=<valor aleatorio largo>
ALLOWED_ORIGINS=https://nexus.dominio.example
ALLOWED_HOSTS=api.nexus.dominio.example
GROQ_API_KEY=<clave>
```

Arranque de uvicorn para que vea el esquema real (`https`) que informa el proxy:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
  --proxy-headers --forwarded-allow-ips=127.0.0.1
```

`--forwarded-allow-ips` debe contener la IP del proxy (en el ejemplo, el proxy
corre en la misma máquina).

### 7.2 Efectos de `ENVIRONMENT=production`

- **HSTS**: el backend agrega `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- **Cookie `Secure`**: la cookie de sesión solo viaja por `https`. Si el proxy no
  redirige `http` a `https`, o si uvicorn no recibe los encabezados del proxy,
  el login no funciona; es el comportamiento esperado.
- **Documentación desactivada**: `/docs`, `/redoc` y `/openapi.json` responden 404.
- **Orígenes**: todo origen de `ALLOWED_ORIGINS` debe ser `https`, salvo
  `localhost`, `127.0.0.1` o `::1`.

En todos los entornos, el backend agrega `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`,
`Cross-Origin-Opener-Policy`, una CSP de API (`default-src 'none'`) y
`Cache-Control: no-store` en `/api/*`. CORS acepta solo los métodos `GET`,
`POST` y `PUT` y el encabezado `Content-Type`.

El frontend agrega sus propios encabezados en `frontend/next.config.ts`, con
HSTS solo cuando `NODE_ENV=production`. Para producción, definir
`NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_SITE_URL` con los orígenes `https` reales
antes de `npm run build`, ya que las variables `NEXT_PUBLIC_*` se incorporan en
la compilación.

### 7.3 Ejemplo de proxy inverso (Caddy)

El siguiente archivo es **un ejemplo ilustrativo**, no forma parte del
repositorio. Caddy obtiene los certificados y redirige `http` a `https` de forma
automática:

```caddy
# Caddyfile (ejemplo)
api.nexus.dominio.example {
    reverse_proxy 127.0.0.1:8000
}

nexus.dominio.example {
    reverse_proxy 127.0.0.1:3000
}
```

Equivalente mínimo en nginx (ejemplo; certificados gestionados por separado):

```nginx
server {
    listen 80;
    server_name api.nexus.dominio.example;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.nexus.dominio.example;
    ssl_certificate     /etc/ssl/nexus/fullchain.pem;
    ssl_certificate_key /etc/ssl/nexus/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Un análisis tarda varios minutos (unos 500 s medidos en corridas reales), por lo
que conviene ampliar el tiempo de espera del proxy para `POST /api/analyze`
(en nginx, `proxy_read_timeout`).

### 7.4 Pendiente conocido

El frontend **no tiene `Content-Security-Policy`**. Next.js inyecta scripts en
línea para la hidratación, y una CSP estricta requiere nonces generados por
pedido; activarla sin probarla dejaría la aplicación en blanco. Además, una
respuesta 500 no manejada del backend no lleva los encabezados de seguridad,
porque la genera el middleware más externo de Starlette.

---

## 8. Datos y persistencia

| Ubicación | Contenido | Estado |
|-----------|-----------|--------|
| `NEXUS_DB_PATH` (por defecto `./data/nexus.db`) | Cuentas, sesiones y auditoría (SQLite) | Gitignoreado; se regenera con `create_all()` |
| `chroma_db/` | Colección vectorial del RAG (ChromaDB persistente) | Gitignoreado y descartable |
| `output/` | Telemetría de costos (`costos.jsonl`), artefactos de los scripts de demostración y evaluación | Gitignoreado y descartable |

Borrar `data/` elimina todas las cuentas, incluidas las de administrador, que
deben volver a crearse (sección 5). Los datos clínicos no se persisten más allá
del análisis: el PDF se procesa en memoria.

**Cambio de modelo de embeddings.** Si se modifica `NEXUS_EMBEDDING_MODEL`, la
colección existente en `chroma_db/` fue construida con otro modelo y sus
vectores no son comparables: `backend/rag/chroma_store.py` levanta
`EmbeddingModelMismatch`. La solución es reindexar, ya sea con
`reset_collection()` o borrando `chroma_db/`. Al cambiar de modelo también debe
volver a medirse `NEXUS_RAG_MIN_SCORE`.

---

## 9. Pruebas e integración continua

Backend, desde la raíz y con el entorno virtual activo:

```bash
python -m pytest -q
```

La suite no usa la red: `tests/conftest.py` bloquea toda conexión no local y
hace fallar al test que la intente. Las APIs externas se reemplazan con mocks y
la base de cuentas es una SQLite en memoria. Los tests del RAG necesitan el
modelo ONNX por defecto de ChromaDB (all-MiniLM-L6-v2, unos 80 MB) en
`~/.cache/chroma`; debe descargarse una vez, fuera de pytest:

```bash
python -c "from chromadb.utils import embedding_functions as ef; ef.DefaultEmbeddingFunction()(['warmup'])"
```

Los tests de OCR de `tests/test_ingesta.py` requieren el binario `tesseract`.

Frontend:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm test          # Vitest + React Testing Library sobre jsdom
```

**CI** (`.github/workflows/ci.yml`, GitHub Actions) se ejecuta en cada pull
request y en cada push a `develop` y `master`, sin secretos:

- **Backend**: Python 3.12, instala `tesseract-ocr`, `torch` CPU y
  `backend/requirements.txt`, descarga (con caché) el modelo ONNX de ChromaDB y
  ejecuta `python -m pytest -q`.
- **Frontend**: Node 22, `npm ci`, `npm run lint`, `npx tsc --noEmit` y `npm test`.

---

## 10. Resolución de problemas

| Síntoma | Causa | Solución |
|---------|-------|----------|
| El primer login falla con `SecretKeyNoConfigurada` | Falta `SECRET_KEY` en `.env` | Definirla y reiniciar el backend. |
| El backend no arranca y levanta `ConfiguracionInsegura` | `ALLOWED_ORIGINS` con `*`, vacía, sin esquema, con ruta, o con `http` no local en producción; o `ALLOWED_HOSTS=*` | Listar los orígenes uno por uno como `esquema://host[:puerto]`. |
| El análisis falla con "GROQ_API_KEY no está configurada y el modo mock está desactivado" | Falta la clave y el modo mock está apagado | Definir `GROQ_API_KEY` o activar `NEXUS_MOCK_LLM=1`. |
| Errores 429 de Groq o análisis interrumpidos | Límite de velocidad o cuota diaria del plan gratuito (200.000 tokens por día; un caso consume unos 80.000 a 85.000, es decir, unos dos casos por día) | `call_provider()` reintenta hasta tres veces (8, 20 y 40 s). Agotada la cuota, esperar al día siguiente o usar el modo mock. |
| Aviso por stderr de que el RAG cae a `all-MiniLM-L6-v2` | `sentence-transformers` no está instalado | El RAG funciona con un modelo de dominio general. Para el biomédico, instalar `backend/requirements.txt` completo. |
| `EmbeddingModelMismatch` al consultar el RAG | La colección de `chroma_db/` se construyó con otro modelo | Reindexar con `reset_collection()` o borrar `chroma_db/`. |
| El login funciona en local pero no en producción | Cookie `Secure` sin `https` real: falta la redirección en el proxy o `--proxy-headers` en uvicorn | Revisar la sección 7.1. |
| El navegador bloquea las peticiones por CORS | El origen del frontend no está en `ALLOWED_ORIGINS` | Agregarlo, sin barra final ni ruta. |
| Fallan 8 tests de `tests/test_rag.py` | Falta el modelo ONNX de ChromaDB en `~/.cache/chroma` | Descargarlo con el comando de la sección 9. |
| Fallan los tests de OCR | Falta el binario `tesseract` | Instalar `tesseract-ocr`. |

---

### Nota sobre `MAX_FILE_SIZE_MB`

`POST /api/analyze` rechaza con un 413 ("El archivo supera el límite de N MB.") todo
archivo mayor que `MAX_FILE_SIZE_MB` (50 por defecto), antes de extraer el texto. El
backend lee como mucho el límite más un byte, así que un archivo grande no se carga en
memoria. Sin embargo, el servidor (Starlette) recibe el cuerpo completo y lo guarda en un
temporal antes de que el endpoint lo examine: el límite evita procesarlo, no recibirlo.
En producción conviene cortar antes en el proxy inverso, con un valor algo mayor al de la
variable para dejar lugar a los encabezados del formulario (por ejemplo,
`client_max_body_size 51m;` en nginx o `request_body { max_size 51MB }` en Caddy).
