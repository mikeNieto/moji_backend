"""
ws_handlers/protocol.py — Funciones helper para construir mensajes del protocolo WS.

Cada función devuelve un str JSON listo para enviar por WebSocket.
Los modelos Pydantic de referencia están en models/ws_messages.py.

Uso:
    from ws_handlers.protocol import make_auth_ok, make_emotion, make_text_chunk
    await websocket.send_text(make_auth_ok(session_id="abc"))
"""

import json
import uuid


# ── Helpers internos ──────────────────────────────────────────────────────────


def _to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def new_session_id() -> str:
    """Genera un UUID v4 como session_id."""
    return str(uuid.uuid4())


# ── Mensajes del servidor ─────────────────────────────────────────────────────


def make_auth_ok(session_id: str) -> str:
    """
    Confirmación de autenticación exitosa.
    {"type": "auth_ok", "session_id": "..."}
    """
    return _to_json({"type": "auth_ok", "session_id": session_id})


def make_user_registered(user_id: str, name: str) -> str:
    """
    Confirmación de registro de nuevo usuario.
    {"type": "user_registered", "user_id": "...", "name": "..."}
    """
    return _to_json({"type": "user_registered", "user_id": user_id, "name": name})


def make_emotion(
    request_id: str,
    emotion: str,
    user_identified: str | None = None,
    confidence: float | None = None,
) -> str:
    """
    Emotion tag enviado ANTES del texto para actualizar la cara de inmediato.
    {"type": "emotion", "request_id": "...", "emotion": "happy", ...}
    """
    msg: dict = {
        "type": "emotion",
        "request_id": request_id,
        "emotion": emotion,
    }
    if user_identified is not None:
        msg["user_identified"] = user_identified
    if confidence is not None:
        msg["confidence"] = confidence
    return _to_json(msg)


def make_text_chunk(request_id: str, text: str) -> str:
    """
    Fragmento de texto de respuesta (streaming progresivo).
    {"type": "text_chunk", "request_id": "...", "text": "..."}
    """
    return _to_json({"type": "text_chunk", "request_id": request_id, "text": text})


def make_capture_request(request_id: str, capture_type: str = "photo") -> str:
    """
    Solicitud de captura de foto o video al cliente.
    {"type": "capture_request", "request_id": "...", "capture_type": "photo"}
    Nota: este tipo de mensaje no está en el schema Pydantic original,
    se extiende el protocolo para comunicar photo_request / video_request.
    """
    return _to_json(
        {
            "type": "capture_request",
            "request_id": request_id,
            "capture_type": capture_type,
        }
    )


def make_response_meta(
    request_id: str,
    response_text: str,
    emojis: list[str],
    actions: list[dict] | None = None,
    duration_per_emoji: int = 2000,
    transition: str = "bounce",
) -> str:
    """
    Metadata de respuesta enviada al finalizar el stream de texto.
    Incluye secuencias de emojis y acciones de movimiento/luz.
    """
    return _to_json(
        {
            "type": "response_meta",
            "request_id": request_id,
            "response_text": response_text,
            "expression": {
                "emojis": emojis,
                "duration_per_emoji": duration_per_emoji,
                "transition": transition,
            },
            "actions": actions or [],
        }
    )


def make_stream_end(request_id: str, processing_time_ms: int = 0) -> str:
    """
    Fin del stream de respuesta.
    {"type": "stream_end", "request_id": "...", "processing_time_ms": 850}
    """
    return _to_json(
        {
            "type": "stream_end",
            "request_id": request_id,
            "processing_time_ms": processing_time_ms,
        }
    )


def make_error(
    error_code: str,
    message: str,
    request_id: str | None = None,
    recoverable: bool = False,
) -> str:
    """
    Mensaje de error del servidor.
    {"type": "error", "error_code": "...", "message": "...", "recoverable": false}
    """
    msg: dict = {
        "type": "error",
        "error_code": error_code,
        "message": message,
        "recoverable": recoverable,
    }
    if request_id is not None:
        msg["request_id"] = request_id
    return _to_json(msg)
