"""
tests/streamlit_simulator/app.py — Simulador Streamlit para Moji Backend

v2.0 — Moji Amigo Familiar

Uso:
    uv run streamlit run tests/streamlit_simulator/app.py

Requiere el backend corriendo:
    uv run uvicorn main:app --reload --ws wsproto
"""

import base64
import json
import struct
import time
import uuid
from pathlib import Path

import requests
import streamlit as st
from websockets.sync.client import connect as ws_connect

# ── Constantes ────────────────────────────────────────────────────────────────

EMOTION_OPENMOJI: dict[str, str] = {
    "happy": "1F600",
    "excited": "1F929",
    "sad": "1F622",
    "empathy": "1FAE6",
    "confused": "1F615",
    "surprised": "1F632",
    "love": "2764",
    "cool": "1F60E",
    "greeting": "1F44B",
    "neutral": "1F610",
    "curious": "1F914",
    "worried": "1F62C",
    "playful": "1F61C",
}
_OPENMOJI_CDN = (
    "https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@latest/color/svg/{code}.svg"
)
_OPENMOJI_SVG = "https://openmoji.org/data/color/svg/{code}.svg"


# ── Helpers ───────────────────────────────────────────────────────────────────


def emoji_url(code: str) -> str:
    return _OPENMOJI_CDN.format(code=code.upper())


def emotion_img_html(emotion: str, size: int = 64) -> str:
    code = EMOTION_OPENMOJI.get(emotion, EMOTION_OPENMOJI["neutral"])
    return (
        f'<img src="{emoji_url(code)}" width="{size}" height="{size}" '
        f'title="{emotion}" style="vertical-align:middle; margin-right:8px;">'
    )


def emoji_row_html(codes: list[str], size: int = 40) -> str:
    imgs = "".join(
        f'<img src="{_OPENMOJI_SVG.format(code=c.upper())}" '
        f'width="{size}" height="{size}" title="{c}" style="margin-right:4px;">'
        for c in codes
    )
    return f'<div style="display:flex;flex-wrap:wrap;gap:2px;align-items:center;">{imgs}</div>'


def generate_fake_embedding_b64() -> str:
    """Genera un embedding facial sintético de 128 float32 normalizados en base64.

    El vector resultante tiene norma 1 (unitario), igual que los embeddings reales
    generados por redes de reconocimiento facial (ArcFace, FaceNet, etc.).
    Produce ~684 bytes en base64 — compatible con el campo face_embedding del backend.
    """
    import random

    raw = [random.gauss(0, 1) for _ in range(128)]
    norm = sum(x * x for x in raw) ** 0.5
    unit = [x / norm for x in raw]
    data = struct.pack("128f", *unit)
    return base64.b64encode(data).decode()


# ── Session state ─────────────────────────────────────────────────────────────


def _init_session() -> None:
    defaults = {
        "ws": None,
        "connected": False,
        "history": [],
        "last_result": None,  # dict con la última respuesta de interacción
        "last_event_result": None,  # dict con la última respuesta de evento Moji
        "camera_on": False,
        "video_mode": "foto",
        # Contadores para resetear widgets (incrementar = nuevo widget vacío)
        "text_gen": 0,
        "audio_gen": 0,
        "photo_gen": 0,
        "video_gen": 0,
        # Flujo persona nueva (wizard multi-paso)
        "new_person_step": 0,  # 0=idle 1=name_asked 2=registered
        "new_person_moji_q": None,  # resultado streaming paso 1
        "new_person_result": None,  # resultado streaming paso 2
        "new_person_registered_name": None,
        "new_person_registered_id": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── WebSocket ─────────────────────────────────────────────────────────────────


def ws_connect_auth(url: str, api_key: str) -> tuple[bool, str]:
    try:
        ws = ws_connect(url, open_timeout=10)
        ws.send(json.dumps({"type": "auth", "api_key": api_key}))
        msg = json.loads(ws.recv(timeout=10))
        if msg.get("type") == "auth_ok":
            st.session_state.ws = ws
            st.session_state.connected = True
            return True, "Conectado"
        ws.close()
        return False, f"Auth rechazada: {msg}"
    except Exception as exc:
        return False, f"Error de conexión: {exc}"


def ws_disconnect() -> None:
    if st.session_state.ws:
        try:
            st.session_state.ws.close()
        except Exception:
            pass
    st.session_state.ws = None
    st.session_state.connected = False


def ws_receive_stream(start_ts: float) -> dict:
    """Lee emotion + text_chunks + response_meta + stream_end del WS activo.

    Retorna el mismo dict que ws_send_and_receive (reutilizable en cualquier
    flujo donde el backend ya inició el stream: person_detected, etc.).
    """
    ws = st.session_state.ws
    emotion = "neutral"
    person_identified: str | None = None
    full_text = ""
    meta = None
    latency_ms = None
    emotion_latency_ms = None
    first_chunk_latency_ms = None
    error = None
    chunks: list[dict] = []

    status_ph = st.empty()
    text_ph = st.empty()

    while True:
        try:
            raw = ws.recv(timeout=60)
        except TimeoutError:
            error = "⏱️ Timeout esperando respuesta del backend."
            break

        msg = json.loads(raw)
        mtype = msg.get("type", "")
        chunk_ts = int((time.monotonic() - start_ts) * 1000)
        chunks.append({"ts_ms": chunk_ts, **msg})

        if mtype == "emotion":
            emotion = msg.get("emotion", "neutral")
            person_identified = msg.get("person_identified")
            emotion_latency_ms = chunk_ts
            person_badge = f" · 👤 `{person_identified}`" if person_identified else ""
            status_ph.markdown(
                f"{emotion_img_html(emotion, 48)} **{emotion}**{person_badge}"
                f" · ⏱️ {emotion_latency_ms} ms",
                unsafe_allow_html=True,
            )
        elif mtype == "text_chunk":
            if first_chunk_latency_ms is None:
                first_chunk_latency_ms = chunk_ts
            full_text += msg.get("text", "")
            text_ph.markdown(full_text)
        elif mtype == "response_meta":
            meta = msg
        elif mtype == "stream_end":
            latency_ms = int((time.monotonic() - start_ts) * 1000)
            break
        elif mtype == "error":
            error = f"❌ [{msg.get('error_code', '?')}] {msg.get('message', 'Error desconocido')}"
            break

    return {
        "emotion": emotion,
        "person_identified": person_identified,
        "text": full_text,
        "meta": meta,
        "latency_ms": latency_ms,
        "emotion_latency_ms": emotion_latency_ms,
        "first_chunk_latency_ms": first_chunk_latency_ms,
        "error": error,
        "chunks": chunks,
    }


def ws_send_and_receive(
    user_text: str | None,
    audio_bytes: bytes | None,
    video_bytes: bytes | None,
    person_id: str,
    face_embedding_b64: str | None = None,
) -> dict:
    """Envía todos los contenidos en un único mensaje multimodal y recibe la respuesta.

    El parámetro face_embedding_b64 activa el flujo de registro de nombre:
    el backend inyecta la instrucción especial al LLM y éste emite [person_name:NOMBRE].
    """
    ws = st.session_state.ws
    request_id = str(uuid.uuid4())
    start_ts = time.monotonic()

    ws.send(
        json.dumps(
            {
                "type": "interaction_start",
                "person_id": person_id if person_id != "unknown" else None,
                "request_id": request_id,
            }
        )
    )

    vid_mode = st.session_state.get("video_mode", "foto")
    payload: dict = {"type": "multimodal", "request_id": request_id}
    if user_text:
        payload["text"] = user_text
    if audio_bytes:
        payload["audio"] = base64.b64encode(audio_bytes).decode()
        payload["audio_mime"] = "audio/webm"
    if video_bytes:
        if vid_mode == "foto":
            payload["image"] = base64.b64encode(video_bytes).decode()
            payload["image_mime"] = "image/jpeg"
        else:
            payload["video"] = base64.b64encode(video_bytes).decode()
            payload["video_mime"] = "video/mp4"
    if face_embedding_b64:
        payload["face_embedding"] = face_embedding_b64
    ws.send(json.dumps(payload))

    return ws_receive_stream(start_ts)


def ws_send_event(payload: dict, wait_types: list[str], timeout: float = 15.0) -> dict:
    """
    Envía un evento WS (face_scan_mode, person_detected, etc.) y espera
    hasta recibir un mensaje de los tipos esperados o timeout.

    Retorna un dict con 'type', 'chunks', 'error'.
    """
    ws = st.session_state.ws
    start_ts = time.monotonic()
    ws.send(json.dumps(payload))

    chunks: list[dict] = []
    received: dict | None = None
    error: str | None = None

    while True:
        elapsed = time.monotonic() - start_ts
        remaining = timeout - elapsed
        if remaining <= 0:
            error = "⏱️ Timeout esperando respuesta del backend."
            break
        try:
            raw = ws.recv(timeout=min(remaining, 10.0))
        except TimeoutError:
            error = "⏱️ Timeout esperando respuesta del backend."
            break

        msg = json.loads(raw)
        mtype = msg.get("type", "")
        chunk_ts = int((time.monotonic() - start_ts) * 1000)
        chunks.append({"ts_ms": chunk_ts, **msg})

        if mtype in wait_types:
            received = msg
            break
        if mtype == "error":
            error = f"❌ [{msg.get('error_code', '?')}] {msg.get('message', 'Error desconocido')}"
            break

    return {
        "received": received,
        "chunks": chunks,
        "error": error,
    }


# ── REST ──────────────────────────────────────────────────────────────────────


def rest_get(base_url: str, path: str, api_key: str) -> tuple[int, dict]:
    try:
        r = requests.get(
            f"{base_url}{path}",
            headers={"X-API-Key": api_key},
            timeout=10,
            verify=False,
        )
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text}
    except Exception as exc:
        return 0, {"error": str(exc)}


# ── App ───────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Moji Simulator v2",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
_init_session()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 Moji Simulator v2")
    st.caption("Herramienta de prueba para el backend de Moji sin Android.")
    st.divider()

    st.subheader("⚙️ Configuración")
    backend_url = st.text_input(
        "URL WebSocket", value="ws://localhost:8000/ws/interact"
    )
    rest_base = (
        backend_url.replace("ws://", "http://")
        .replace("wss://", "https://")
        .rsplit("/ws/", 1)[0]
    )

    api_key = st.text_input("API Key", type="password", value="")
    if not api_key:
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("API_KEY=") and not line.startswith(
                    "API_KEY=change"
                ):
                    api_key = line.split("=", 1)[1].strip()
                    break

    st.divider()
    st.subheader("👤 Persona")
    person_id = st.selectbox(
        "person_id",
        ["unknown", "person_juan", "person_maria", "person_pedro"],
        help="Slug de la persona reconocida. 'unknown' = Moji no reconoció a nadie.",
    )
    custom_person = st.text_input("... o escribe un person_id personalizado", value="")
    if custom_person.strip():
        person_id = custom_person.strip()

    st.divider()
    st.subheader("🔌 Conexión")
    if not st.session_state.connected:
        if st.button("Conectar", type="primary", use_container_width=True):
            if not api_key:
                st.error("Ingresa la API Key primero.")
            else:
                with st.spinner("Conectando..."):
                    ok, msg = ws_connect_auth(backend_url, api_key)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.success("✅ Conectado")
        if st.button("Desconectar", use_container_width=True):
            ws_disconnect()
            st.rerun()

    st.divider()
    st.subheader("🔧 REST")
    if st.button("GET /api/health", use_container_width=True):
        code, body = rest_get(rest_base, "/api/health", api_key)
        (st.success if code == 200 else st.error)(f"**{code}** — {body}")

    if st.button("GET /api/restore", use_container_width=True):
        code, body = rest_get(rest_base, "/api/restore", api_key)
        if code == 200:
            people = body.get("people", [])
            memories = body.get("general_memories", [])
            st.success(
                f"**{code}** — {len(people)} personas · {len(memories)} memorias"
            )
            with st.expander("📦 Datos completos de restauración"):
                st.json(body)
        else:
            st.error(f"**{code}** — {body}")

# ── Layout ────────────────────────────────────────────────────────────────────

main_col, history_col = st.columns([3, 2], gap="large")

with main_col:
    st.header("💬 Interacción")

    # ── Inputs (claves dinámicas — incrementar el contador resetea el widget) ──
    tab_text, tab_audio, tab_video, tab_events = st.tabs(
        ["📝 Texto", "🎙️ Audio", "📹 Video", "🤖 Eventos Moji"]
    )

    with tab_text:
        st.text_area(
            "Mensaje de texto",
            placeholder="Escribe lo que diría el usuario…",
            height=120,
            key=f"input_text_{st.session_state.text_gen}",
            label_visibility="collapsed",
        )

    with tab_audio:
        st.audio_input(
            "Graba tu mensaje de voz", key=f"input_audio_{st.session_state.audio_gen}"
        )

    with tab_video:
        if st.button(
            "🔴 Desactivar cámara"
            if st.session_state.camera_on
            else "📷 Activar cámara",
            key="btn_toggle_camera",
        ):
            st.session_state.camera_on = not st.session_state.camera_on
            if not st.session_state.camera_on:
                st.session_state.photo_gen += 1
                st.session_state.video_gen += 1
            st.rerun()

        if st.session_state.camera_on:
            mode = st.radio(
                "Modo",
                ["foto", "video"],
                format_func=lambda m: (
                    "📷 Foto" if m == "foto" else "🎬 Video (archivo)"
                ),
                horizontal=True,
                key="video_mode",
                label_visibility="collapsed",
            )
            if mode == "foto":
                st.camera_input(
                    "Captura", key=f"input_photo_{st.session_state.photo_gen}"
                )
            else:
                st.file_uploader(
                    "Subir video",
                    type=["mp4", "webm", "mov", "avi"],
                    key=f"input_video_{st.session_state.video_gen}",
                )
        else:
            st.info("Activa la cámara para capturar una foto o subir un video.")

    with tab_events:
        st.caption(
            "Simula los eventos que Android envía a Moji según el protocolo v2.0."
        )

        # ── face_scan_mode ────────────────────────────────────────────────────
        with st.expander("🔍 face_scan_mode — Escaneo facial activo"):
            if st.button(
                "Enviar face_scan_mode",
                use_container_width=True,
                disabled=not st.session_state.connected,
            ):
                req_id = str(uuid.uuid4())
                with st.spinner("Esperando face_scan_actions…"):
                    try:
                        ev_result = ws_send_event(
                            payload={"type": "face_scan_mode", "request_id": req_id},
                            wait_types=["face_scan_actions"],
                        )
                    except Exception as exc:
                        st.session_state.connected = False
                        ev_result = {"received": None, "chunks": [], "error": str(exc)}
                st.session_state.last_event_result = {
                    "kind": "face_scan_mode",
                    **ev_result,
                }
                st.rerun()

        # ── person_detected ───────────────────────────────────────────────────
        with st.expander("👁️ person_detected — Persona detectada"):
            pd_known = st.checkbox("¿Persona conocida?", value=False, key="pd_known")
            pd_pid = st.text_input(
                "person_id (solo si conocida)",
                value="",
                key="pd_pid",
                disabled=not pd_known,
            )
            pd_conf = st.slider(
                "Confianza",
                min_value=0.0,
                max_value=1.0,
                value=0.85,
                step=0.05,
                key="pd_conf",
            )
            if st.button(
                "Enviar person_detected",
                use_container_width=True,
                disabled=not st.session_state.connected,
            ):
                req_id = str(uuid.uuid4())
                with st.spinner("Enviando person_detected…"):
                    try:
                        ws = st.session_state.ws
                        ws.send(
                            json.dumps(
                                {
                                    "type": "person_detected",
                                    "request_id": req_id,
                                    "known": pd_known,
                                    "person_id": pd_pid.strip() or None,
                                    "confidence": pd_conf,
                                }
                            )
                        )
                        ev_result = {
                            "received": {"type": "person_detected_sent"},
                            "chunks": [],
                            "error": None,
                        }
                    except Exception as exc:
                        st.session_state.connected = False
                        ev_result = {"received": None, "chunks": [], "error": str(exc)}
                st.session_state.last_event_result = {
                    "kind": "person_detected",
                    "known": pd_known,
                    "person_id": pd_pid.strip() or None,
                    **ev_result,
                }
                st.rerun()

        # ── flujo_persona_nueva ───────────────────────────────────────────────
        with st.expander("🆕 Flujo Persona Nueva — Registro completo", expanded=False):
            st.caption(
                "Wizard para probar el flujo completo: Moji detecta una persona "
                "desconocida → pregunta el nombre → registra en BD → reencuentro."
            )

            pnf_step = st.session_state.get("new_person_step", 0)

            # Indicador de progreso
            step_cols = st.columns(3)
            for _i, (_sc, _sl, _sa) in enumerate(
                zip(
                    step_cols,
                    ["① Detectar", "② Nombre", "③ Reencuentro"],
                    [
                        "Simular persona desconocida",
                        "Decir nombre + embedding",
                        "Volver a encontrarse",
                    ],
                )
            ):
                with _sc:
                    if _i < pnf_step:
                        st.success(_sl)
                    elif _i == pnf_step:
                        st.info(f"**{_sl}**")
                    else:
                        st.caption(_sl)

            st.markdown("---")

            # ── Paso 0: detectar persona desconocida ──────────────────────────
            if pnf_step == 0:
                st.markdown(
                    "Pulsa el botón para simular que Moji detecta una cara desconocida. "
                    "El backend lanzará el agente para saludar y pedir el nombre."
                )
                pnf_conf = st.slider(
                    "Confianza de detección", 0.5, 1.0, 0.82, 0.01, key="pnf_conf"
                )
                if st.button(
                    "① Simular persona desconocida",
                    type="primary",
                    use_container_width=True,
                    disabled=not st.session_state.connected,
                ):
                    req_id = str(uuid.uuid4())
                    start_ts = time.monotonic()
                    with st.spinner("Moji está saludando a la persona desconocida…"):
                        try:
                            st.session_state.ws.send(
                                json.dumps(
                                    {
                                        "type": "person_detected",
                                        "request_id": req_id,
                                        "known": False,
                                        "person_id": None,
                                        "confidence": pnf_conf,
                                    }
                                )
                            )
                            pnf_r1 = ws_receive_stream(start_ts)
                        except Exception as exc:
                            st.session_state.connected = False
                            pnf_r1 = {
                                "error": str(exc),
                                "emotion": "neutral",
                                "person_identified": None,
                                "text": "",
                                "meta": None,
                                "latency_ms": None,
                                "emotion_latency_ms": None,
                                "first_chunk_latency_ms": None,
                                "chunks": [],
                            }
                    st.session_state.new_person_moji_q = pnf_r1
                    if not pnf_r1.get("error"):
                        st.session_state.new_person_step = 1
                    st.rerun()

            # ── Paso 1: usuario dice su nombre ────────────────────────────────
            elif pnf_step == 1:
                moji_q = st.session_state.get("new_person_moji_q") or {}
                if moji_q.get("error"):
                    st.error(moji_q["error"])
                elif moji_q.get("text"):
                    with st.container(border=True):
                        st.caption("🤖 Moji preguntó:")
                        st.markdown(
                            f"{emotion_img_html(moji_q.get('emotion', 'neutral'), 28)} "
                            f"{moji_q['text']}",
                            unsafe_allow_html=True,
                        )

                st.markdown(
                    "Escribe el nombre de la persona. Se enviará junto con un "
                    "**embedding facial sintético** (128 float32 normalizados) "
                    "para activar el registro en la BD."
                )
                pnf_name = st.text_input(
                    "Nombre de la persona",
                    placeholder="Ana, Carlos, María…",
                    key="pnf_name_input",
                )
                with st.expander("ℹ️ ¿Qué es el embedding sintético?"):
                    st.caption(
                        "Se genera un vector unitario de 128 flotantes aleatorios "
                        "codificado en base64 (~684 bytes). El backend lo almacena en "
                        "la tabla `face_embeddings` y activa la instrucción especial del "
                        "LLM para que emita `[person_name:NOMBRE]` en su respuesta."
                    )

                col_ok, col_back = st.columns(2)
                with col_ok:
                    if st.button(
                        "② Decir nombre (con embedding)",
                        type="primary",
                        use_container_width=True,
                        disabled=not st.session_state.connected
                        or not (pnf_name or "").strip(),
                    ):
                        nombre = pnf_name.strip()
                        fake_emb = generate_fake_embedding_b64()
                        with st.spinner(f"Enviando «Me llamo {nombre}» con embedding…"):
                            try:
                                pnf_r2 = ws_send_and_receive(
                                    user_text=f"Me llamo {nombre}",
                                    audio_bytes=None,
                                    video_bytes=None,
                                    person_id="unknown",
                                    face_embedding_b64=fake_emb,
                                )
                            except Exception as exc:
                                st.session_state.connected = False
                                pnf_r2 = {
                                    "error": str(exc),
                                    "emotion": "neutral",
                                    "person_identified": None,
                                    "text": "",
                                    "meta": None,
                                    "latency_ms": None,
                                    "emotion_latency_ms": None,
                                    "first_chunk_latency_ms": None,
                                    "chunks": [],
                                }
                        st.session_state.new_person_result = pnf_r2
                        if not pnf_r2.get("error"):
                            meta2 = pnf_r2.get("meta") or {}
                            st.session_state.new_person_registered_name = (
                                meta2.get("person_name") or nombre
                            )
                            st.session_state.new_person_step = 2
                        st.rerun()
                with col_back:
                    if st.button("↩ Reiniciar", use_container_width=True):
                        for _k in (
                            "new_person_step",
                            "new_person_moji_q",
                            "new_person_result",
                            "new_person_registered_name",
                            "new_person_registered_id",
                        ):
                            st.session_state[_k] = (
                                0 if _k == "new_person_step" else None
                            )
                        st.rerun()

            # ── Paso 2: persona registrada + reencuentro ──────────────────────
            elif pnf_step == 2:
                reg_name = st.session_state.get("new_person_registered_name") or "?"
                pnf_r2 = st.session_state.get("new_person_result") or {}

                if pnf_r2.get("error"):
                    st.error(pnf_r2["error"])
                else:
                    meta2 = pnf_r2.get("meta") or {}
                    if meta2.get("person_name"):
                        st.success(
                            f"✅ Tag `[person_name:{meta2['person_name']}]` detectado — "
                            f"persona guardada en BD."
                        )
                    else:
                        st.warning(
                            "⚠️ El LLM no emitió `[person_name:]`. "
                            "Revisa el debug o intenta de nuevo con audio."
                        )
                    with st.container(border=True):
                        st.caption("🤖 Moji respondió:")
                        st.markdown(
                            f"{emotion_img_html(pnf_r2.get('emotion', 'neutral'), 28)} "
                            f"{pnf_r2.get('text', '')}",
                            unsafe_allow_html=True,
                        )
                    with st.expander(
                        f"🐛 Debug paso 2 ({len(pnf_r2.get('chunks', []))} chunks)"
                    ):
                        for _ci, _ch in enumerate(pnf_r2.get("chunks", [])):
                            st.markdown(
                                f"**#{_ci + 1}** `{_ch.get('type', '?')}` "
                                f"· `{_ch.get('ts_ms', '?')} ms`"
                            )
                            st.json(_ch)

                st.markdown("---")
                st.markdown("**Obtener person_id** para el reencuentro:")
                reg_pid = st.session_state.get("new_person_registered_id", "")

                if st.button("🔍 Buscar en /api/restore", use_container_width=True):
                    _code, _body = rest_get(rest_base, "/api/restore", api_key)
                    if _code == 200:
                        _people = _body.get("people", [])
                        _match = next(
                            (
                                _p
                                for _p in _people
                                if _p.get("name", "").lower() == reg_name.lower()
                            ),
                            None,
                        )
                        if _match:
                            st.session_state.new_person_registered_id = _match[
                                "person_id"
                            ]
                            reg_pid = _match["person_id"]
                            st.rerun()
                        else:
                            _names = [_p.get("name") for _p in _people]
                            st.warning(
                                f"No encontré '{reg_name}'. Personas en BD: {_names}"
                            )
                    else:
                        st.error(f"Error REST {_code}")

                if reg_pid:
                    st.info(f"person_id: `{reg_pid}`")
                    st.text_input(
                        "Copia al campo 'personalizado' del sidebar para conversar:",
                        value=reg_pid,
                        key="pnf_pid_copy",
                        disabled=True,
                    )
                    col_reenc, _ = st.columns([2, 1])
                    with col_reenc:
                        if st.button(
                            "③ Simular reencuentro (person_detected known=true)",
                            type="primary",
                            use_container_width=True,
                            disabled=not st.session_state.connected,
                        ):
                            _req_id = str(uuid.uuid4())
                            try:
                                st.session_state.ws.send(
                                    json.dumps(
                                        {
                                            "type": "person_detected",
                                            "request_id": _req_id,
                                            "known": True,
                                            "person_id": reg_pid,
                                            "confidence": 0.95,
                                        }
                                    )
                                )
                                _ev = {
                                    "received": {"type": "person_detected_reunion"},
                                    "chunks": [],
                                    "error": None,
                                }
                            except Exception as _exc:
                                st.session_state.connected = False
                                _ev = {
                                    "received": None,
                                    "chunks": [],
                                    "error": str(_exc),
                                }
                            st.session_state.last_event_result = {
                                "kind": "person_detected_reunion",
                                "person_id": reg_pid,
                                "name": reg_name,
                                **_ev,
                            }
                            st.rerun()

                st.markdown("---")
                if st.button(
                    "🔄 Resetear flujo persona nueva", use_container_width=True
                ):
                    for _k in (
                        "new_person_step",
                        "new_person_moji_q",
                        "new_person_result",
                        "new_person_registered_name",
                        "new_person_registered_id",
                    ):
                        st.session_state[_k] = 0 if _k == "new_person_step" else None
                    st.rerun()

    st.divider()

    # ── Botón enviar ──────────────────────────────────────────────────────
    col_send, col_hint = st.columns([1, 3])
    with col_send:
        do_send = st.button(
            "Enviar ▶",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.connected,
        )
    with col_hint:
        if not st.session_state.connected:
            st.caption("⚠️ Conecta primero desde el panel lateral.")

    if do_send:
        # Leer valores actuales de los widgets
        text_val: str = st.session_state.get(
            f"input_text_{st.session_state.text_gen}", ""
        ).strip()

        audio_f = st.session_state.get(f"input_audio_{st.session_state.audio_gen}")
        audio_bytes: bytes | None = None
        if audio_f is not None:
            audio_f.seek(0)
            audio_bytes = audio_f.read()

        video_bytes: bytes | None = None
        video_label = ""
        vid_mode = st.session_state.get("video_mode", "foto")
        if vid_mode == "foto":
            photo_f = st.session_state.get(f"input_photo_{st.session_state.photo_gen}")
            if photo_f is not None:
                photo_f.seek(0)
                video_bytes = photo_f.read()
                video_label = "[foto]"
        else:
            vid_f = st.session_state.get(f"input_video_{st.session_state.video_gen}")
            if vid_f is not None:
                vid_f.seek(0)
                video_bytes = vid_f.read()
                video_label = f"[video: {vid_f.name}]"

        if not text_val and audio_bytes is None and video_bytes is None:
            st.warning("⚠️ Completa al menos un campo antes de enviar.")
        else:
            parts = (
                ([text_val] if text_val else [])
                + (["[audio]"] if audio_bytes else [])
                + ([video_label or "[video]"] if video_bytes else [])
            )
            user_label = " + ".join(parts)

            with st.spinner("Esperando respuesta…"):
                try:
                    result = ws_send_and_receive(
                        text_val or None, audio_bytes, video_bytes, person_id
                    )
                except Exception as exc:
                    st.session_state.connected = False
                    result = {
                        "error": str(exc),
                        "emotion": "neutral",
                        "person_identified": None,
                        "text": "",
                        "meta": None,
                        "latency_ms": None,
                        "emotion_latency_ms": None,
                        "first_chunk_latency_ms": None,
                        "chunks": [],
                    }

            # Guardar resultado en session_state (persiste tras rerun)
            st.session_state.last_result = result
            st.session_state.history.append({"role": "user", "content": user_label})
            st.session_state.history.append(
                {
                    "role": "assistant",
                    "content": result["text"],
                    "emotion": result["emotion"],
                    "person_identified": result.get("person_identified"),
                    "latency_ms": result["latency_ms"],
                    "meta": result["meta"],
                }
            )
            # Incrementar contadores → los widgets aparecen vacíos en el próximo render
            st.session_state.text_gen += 1
            st.session_state.audio_gen += 1
            st.session_state.photo_gen += 1
            st.session_state.video_gen += 1
            st.rerun()

    # ── Última respuesta (renderizada desde session_state, sobrevive al rerun) ─
    result = st.session_state.last_result
    if result:
        st.divider()
        st.subheader("🎭 Última respuesta")

        if result.get("error"):
            st.error(result["error"])
        else:
            emotion = result["emotion"]
            elat = result.get("emotion_latency_ms")
            pid_identified = result.get("person_identified")
            person_badge = f" · 👤 `{pid_identified}`" if pid_identified else ""
            st.markdown(
                f"{emotion_img_html(emotion, 48)} **{emotion}**{person_badge}"
                + (f" · ⏱️ {elat} ms" if elat else ""),
                unsafe_allow_html=True,
            )

            fclat = result.get("first_chunk_latency_ms")
            st.markdown(
                result["text"]
                + (
                    f"\n\n<small style='color:gray;'>⚡ primer chunk: {fclat} ms</small>"
                    if fclat
                    else ""
                ),
                unsafe_allow_html=True,
            )

            meta = result.get("meta")
            if meta:
                # Nombre de persona registrado en este turno
                person_name = meta.get("person_name")
                if person_name:
                    st.success(f"🆕 Persona registrada: **{person_name}**")

                codes = (meta.get("expression") or {}).get("emojis", [])
                if codes:
                    st.markdown(
                        f"**Emojis:** {emoji_row_html(codes, 36)}",
                        unsafe_allow_html=True,
                    )
                actions = meta.get("actions") or []
                if actions:
                    with st.expander(f"⚙️ Acciones ESP32 ({len(actions)})"):
                        st.json(actions)
                with st.expander("📦 response_meta"):
                    st.json(meta)

            chunks = result.get("chunks") or []
            with st.expander(f"🐛 Debug — chunks WS ({len(chunks)})"):
                for i, chunk in enumerate(chunks):
                    st.markdown(
                        f"**#{i + 1}** `{chunk.get('type', '?')}` · `{chunk.get('ts_ms', '?')} ms`"
                    )
                    st.json(chunk)

            if result.get("latency_ms") is not None:
                st.caption(f"⏱️ Latencia total: {result['latency_ms']} ms")

    # ── Último resultado de evento Moji ───────────────────────────────────────
    ev = st.session_state.last_event_result
    if ev:
        st.divider()
        kind = ev.get("kind", "evento")
        st.subheader(f"📡 Último evento: `{kind}`")

        if ev.get("error"):
            st.error(ev["error"])
        else:
            received = ev.get("received") or {}
            rtype = received.get("type", "")

            if rtype == "face_scan_actions":
                actions = received.get("actions", [])
                st.info(f"Secuencia de escaneo — {len(actions)} grupo(s) de acciones")
                if actions:
                    with st.expander("⚙️ Acciones face_scan"):
                        st.json(actions)

            elif rtype == "person_detected_reunion":
                _rpid = ev.get("person_id", "?")
                _rname = ev.get("name", "?")
                st.success(f"✅ Reencuentro enviado: **{_rname}** (`{_rpid}`)")
                st.info(
                    f"El backend actualizó el `person_id` de la sesión WS a `{_rpid}`. "
                    f"Ahora escribe ese person_id en el campo **'personalizado'** del "
                    f"sidebar y envía un mensaje desde la pestaña 📝 Texto para "
                    f"conversar normalmente con {_rname}. "
                    f"Verifica que Moji recuerde cosas de turnos anteriores."
                )

            elif rtype == "person_detected_sent":
                known = ev.get("known", False)
                pid = ev.get("person_id")
                if known and pid:
                    st.success(f"✅ person_detected enviado: **{pid}** (conocida)")
                else:
                    st.success("✅ person_detected enviado: persona desconocida")
            else:
                if received:
                    st.json(received)

        chunks = ev.get("chunks") or []
        if chunks:
            with st.expander(f"🐛 Debug — chunks evento ({len(chunks)})"):
                for i, chunk in enumerate(chunks):
                    st.markdown(
                        f"**#{i + 1}** `{chunk.get('type', '?')}` · `{chunk.get('ts_ms', '?')} ms`"
                    )
                    st.json(chunk)

# ── Historial ─────────────────────────────────────────────────────────────────

with history_col:
    st.header("📜 Historial")

    hist = st.session_state.history
    if not hist:
        st.info("El historial aparecerá aquí después de la primera interacción.")
    else:
        for entry in reversed(hist):
            if entry["role"] == "user":
                with st.chat_message("user"):
                    st.write(entry["content"])
            else:
                with st.chat_message("assistant"):
                    emotion = entry.get("emotion")
                    latency = entry.get("latency_ms")
                    pid_id = entry.get("person_identified")
                    if emotion:
                        badge = f"{emotion_img_html(emotion, 24)} `{emotion}`"
                        if pid_id:
                            badge += f" · 👤 `{pid_id}`"
                        if latency is not None:
                            badge += f" · ⏱️ `{latency} ms`"
                        st.markdown(badge, unsafe_allow_html=True)
                    meta = entry.get("meta")
                    if meta:
                        person_name = meta.get("person_name")
                        if person_name:
                            st.caption(f"🆕 Registrado: {person_name}")
                        codes = (meta.get("expression") or {}).get("emojis", [])
                        if codes:
                            st.markdown(
                                emoji_row_html(codes, 32), unsafe_allow_html=True
                            )
                    st.write(entry["content"])

        if st.button("🗑️ Limpiar historial", use_container_width=True):
            st.session_state.history = []
            st.session_state.last_result = None
            st.session_state.last_event_result = None
            st.rerun()
