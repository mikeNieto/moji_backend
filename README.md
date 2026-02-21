# Robi Backend

Backend del robot doméstico **Robi** — FastAPI + WebSocket streaming + LangChain DeepAgents + Gemini Flash Lite + SQLite asíncrono + Docker Compose (FastAPI + Nginx).

---

## Índice

1. [Prerrequisitos](#prerrequisitos)
2. [Ejecución local (desarrollo)](#ejecución-local-desarrollo)
3. [Ejecutar con Docker (producción)](#ejecutar-con-docker-producción)
4. [Pruebas unitarias](#pruebas-unitarias)
5. [Pruebas de integración](#pruebas-de-integración)
6. [Simulador Streamlit](#simulador-streamlit)
7. [Variables de entorno](#variables-de-entorno)
8. [Fingerprint TLS para Android](#fingerprint-tls-para-android)
9. [Arquitectura resumida](#arquitectura-resumida)

---

## Prerrequisitos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| Python | 3.12 | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | v2 (plugin) | incluido con Docker Desktop / `apt install docker-compose-plugin` |
| openssl | cualquiera | preinstalado en macOS/Linux |

---

## Ejecución local (desarrollo)

```bash
# 1. Clonar / entrar al directorio
cd robi_backend

# 2. Copiar y editar el .env
cp .env.example .env
```

Editar `.env` y completar al menos:

```dotenv
GEMINI_API_KEY=tu-api-key-de-google-ai-studio
API_KEY=una-clave-aleatoria-de-32-caracteres
```

```bash
# 3. Instalar dependencias (crea .venv automáticamente)
uv sync

# 4. Arrancar el servidor en modo desarrollo (reload automático)
uv run uvicorn main:app --reload --ws wsproto --port 8000
```

El backend quedará disponible en:

- **API REST + docs interactivos:** `http://localhost:8000/docs`
- **WebSocket:** `ws://localhost:8000/ws/interact`
- **Health check:** `http://localhost:8000/api/health`

---

## Ejecutar con Docker (producción)

### 1. Generar el certificado TLS autofirmado

El script lee `SERVER_IP` de `.env` automáticamente:

```bash
bash scripts/generate_certs.sh
```

O especificar una IP distinta:

```bash
bash scripts/generate_certs.sh 10.0.0.50
```

Genera `nginx/certs/server.key` y `nginx/certs/server.crt` (RSA 4096 bits, 10 años, SAN incluido).

### 2. Construir e iniciar los contenedores

```bash
docker compose up -d --build
```

### 3. Verificar el estado

```bash
# Estado de los contenedores
docker compose ps

# Logs en tiempo real
docker compose logs -f

# Health check del backend a través de Nginx
curl -k https://192.168.2.200:9393/api/health
```

El backend queda disponible en:

- **API REST + docs:** `https://<SERVER_IP>:9393/docs`
- **WebSocket:** `wss://<SERVER_IP>:9393/ws/interact`

### 4. Detener

```bash
docker compose down
```

> **Nota:** los datos de SQLite (`./data/`) y los archivos de media (`./media/`) se persisten como volúmenes en el host y sobreviven a los reinicios.

---

## Pruebas unitarias

```bash
uv run pytest tests/unit/ -v --tb=short
```

Cubre: modelos Pydantic, BD SQLite in-memory, middleware (auth, error handler, logging), repositorios (users, memory, media), servicios de IA (expression, movement, history, intent, agent), protocolo WS, autenticación WS y handler de streaming completo (emotion tag, media summary, historial).

```bash
# Solo conteo rápido
uv run pytest tests/unit/ -q
```

### Ejecutar todas las pruebas

```bash
uv run pytest
```

---

## Pruebas de integración

Las pruebas de integración levantan la aplicación FastAPI in-process usando `httpx.AsyncClient` y un cliente WebSocket real (sin mocks de red).

```bash
uv run pytest tests/integration/ -v
```

Cubren el flujo completo: `auth` → `interaction_start` → `text` → `emotion` + `text_chunks` + `stream_end`.

> **Nota:** las pruebas de integración mockean `run_agent_stream` para no requerir una `GEMINI_API_KEY` real. Para probar con Gemini real usa el [Simulador Streamlit](#simulador-streamlit).

---

## Simulador Streamlit

Herramienta web para probar el backend completo **sin Android ni ESP32**.

### Arrancar

```bash
uv run streamlit run tests/streamlit_simulator/app.py
```

Se abre en `http://localhost:8501`.

### Uso

#### Panel lateral

| Campo | Descripción |
|---|---|
| URL WebSocket | `ws://localhost:8000/ws/interact` en desarrollo, `wss://<IP>:9393/ws/interact` en producción |
| API Key | Se lee automáticamente de `.env` si existe, o se puede introducir manualmente |
| user_id | Selector con valores predefinidos + campo libre |
| Conectar / Desconectar | Establece el handshake de autenticación y mantiene la sesión activa |
| GET /api/health | Llama al endpoint REST y muestra la respuesta |
| GET /api/users/{id}/memory | Consulta las memorias del usuario indicado |

#### Columna principal

1. **Enviar texto** — escribe el mensaje en el área de texto y pulsa *Enviar texto ▶*. Ver en tiempo real: emoción (OpenMoji), fragmentos de texto acumulados, latencia en ms y `response_meta`.

2. **Enviar audio**
   - **🎤 Grabar** — usa el micrófono del navegador directamente (`st.audio_input`). Al detener la grabación aparece el botón *Enviar grabación ▶*.
   - **📁 Subir archivo** — selecciona un `.wav`, `.aac`, `.mp3` u `.ogg`. El audio se envía como frames binarios por WebSocket, Gemini actúa como STT+LLM sin pipeline intermedio.

#### Columna de historial

Muestra todas las interacciones de la sesión con burbujas de chat, emoji de emoción y latencia. Botón *Limpiar historial* disponible.

---

## Variables de entorno

Todas se definen en `.env` (copia de [`.env.example`](.env.example)):

| Variable | Default | Descripción |
|---|---|---|
| `HOST` | `0.0.0.0` | Dirección de escucha del servidor uvicorn |
| `PORT` | `9393` | Puerto de escucha (en dev directo; en Docker lo usa Nginx en 9393) |
| `ENVIRONMENT` | `development` | `development` habilita `/docs`; `production` los desactiva |
| `SERVER_IP` | `192.168.2.200` | IP del servidor; usada en el cert TLS y en la configuración de Nginx |
| `WS_PING_INTERVAL` | `30` | Segundos entre pings WebSocket keepalive |
| `WS_PING_TIMEOUT` | `10` | Segundos hasta declarar conexión muerta |
| `WS_MAX_MESSAGE_SIZE_MB` | `50` | Tamaño máximo de un frame binario (audio) |
| `API_KEY` | — | Clave de autenticación para la API REST y WebSocket (`X-API-Key` o mensaje `auth`) |
| `ALLOWED_ORIGINS` | `https://192.168.2.200` | Orígenes CORS permitidos (separados por coma) |
| `GEMINI_API_KEY` | — | API Key de Google AI Studio |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Modelo Gemini a usar |
| `GEMINI_MAX_OUTPUT_TOKENS` | `512` | Máximo de tokens en la respuesta |
| `GEMINI_TEMPERATURE` | `0.7` | Temperatura de muestreo del LLM |
| `CONVERSATION_KEEP_ALIVE_MS` | `60000` | ms de escucha continua tras cada interacción |
| `CONVERSATION_COMPACTION_THRESHOLD` | `20` | Compactar historial cada N mensajes |
| `PERSON_SEARCH_TIMEOUT_MS` | `8000` | ms máximos para identificar persona tras wake word |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/robot.db` | URL de la base de datos SQLAlchemy async |
| `MEDIA_DIR` | `./media` | Directorio raíz para uploads y logs de media |
| `MAX_UPLOAD_SIZE_MB` | `50` | Tamaño máximo de archivo subido por REST |
| `LOG_LEVEL` | `INFO` | Nivel de log: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | `./media/logs/robot.log` | Ruta del archivo de log estructurado (structlog JSON) |

---

## Fingerprint TLS para Android

El certificado autofirmado requiere **certificate pinning** en Android para que la app confíe en él.

### Generar y obtener el fingerprint

```bash
bash scripts/generate_certs.sh
```

El script imprime al final el bloque listo para pegar en `res/xml/network_security_config.xml`:

```xml
<network-security-config>
  <domain-config cleartextTrafficPermitted="false">
    <domain includeSubdomains="false">192.168.2.200</domain>
    <pin-set>
      <pin digest="SHA-256">BASE64_DEL_FINGERPRINT==</pin>
    </pin-set>
  </domain-config>
</network-security-config>
```

### Extraer el fingerprint manualmente (si ya existe el cert)

```bash
# Fingerprint SHA-256 en hex
openssl x509 -in nginx/certs/server.crt -noout -fingerprint -sha256

# Fingerprint en Base64 (formato Android)
openssl x509 -in nginx/certs/server.crt -outform DER \
  | openssl dgst -sha256 -binary \
  | openssl base64
```

### Referenciarlo en `AndroidManifest.xml`

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
```

> **Importante:** cuando cambies la IP del servidor (`SERVER_IP` en `.env`), regenera el certificado con `bash scripts/generate_certs.sh` y actualiza el `network_security_config.xml` en la app Android.

---

## Arquitectura resumida

```
Android / ESP32
      │
      │  wss://<IP>:9393/ws/interact
      ▼
  ┌─────────┐    proxy_pass     ┌──────────────────────────────┐
  │  Nginx  │ ──────────────►  │  FastAPI (uvicorn + wsproto) │
  │  :9393  │                  │         :8000                │
  └─────────┘                  └──────────────────────────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                    WebSocket          REST API       Background
                   /ws/interact     /api/health         tasks
                          │         /api/users       (historial,
                          │         /api/memory       memorias)
                          ▼
                   ┌─────────────┐
                   │ LangChain   │
                   │ DeepAgents  │
                   │ + Gemini    │  ◄── STT + LLM unificado
                   │ Flash Lite  │      (audio/imagen/video)
                   └─────────────┘
                          │
                   ┌──────▼──────┐
                   │  SQLite     │
                   │  (async)    │
                   │ users       │
                   │ memories    │
                   │ interactions│
                   │ history     │
                   └─────────────┘
```

**Flujo de una interacción de voz:**

1. Android envía frames binarios de audio → buffer en el servidor
2. `audio_end` dispara el procesamiento
3. Se cargan las memorias del usuario (top 5 por importancia)
4. Se cargan el historial de la sesión
5. Gemini recibe audio + contexto → actúa como STT+LLM en una sola llamada
6. El LLM emite `[emotion:TAG][media_summary: ...]` + respuesta en streaming
7. El servidor parsea la emoción → envía `emotion` al cliente inmediatamente
8. El resumen de media se extrae silenciosamente y se usa como entrada del historial
9. Los `text_chunk` se envían progresivamente al robot (TTS on-device en Android)
10. Al finalizar: `response_meta` (emojis + acciones) + `stream_end`
11. En background: se guarda el historial y la interacción en SQLite
