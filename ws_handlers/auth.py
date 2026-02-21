"""
ws_handlers/auth.py — Autenticación del WebSocket mediante API Key.

El primer mensaje que envía el cliente debe ser el handshake de autenticación:
    {"type": "auth", "api_key": "<secret>", "device_id": "android-uuid"}

Si la API Key es válida, el servidor responde con:
    {"type": "auth_ok", "session_id": "<uuid>"}
y devuelve el session_id para el resto de la sesión.

Si no, cierra la conexión con código 1008 (Policy Violation) y devuelve None.

Uso:
    from ws_handlers.auth import authenticate_websocket

    session_id = await authenticate_websocket(websocket)
    if session_id is None:
        return  # conexión cerrada por auth fallida
"""

import asyncio
import json
import logging
import secrets

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from config import settings
from ws_handlers.protocol import make_auth_ok, make_error, new_session_id

logger = logging.getLogger(__name__)

# Timeout en segundos para recibir el mensaje de auth inicial
_AUTH_TIMEOUT = 10.0


async def authenticate_websocket(
    websocket: WebSocket,
    timeout: float = _AUTH_TIMEOUT,
) -> str | None:
    """
    Autentica una conexión WebSocket recién aceptada.

    Espera el primer mensaje JSON con {"type": "auth", "api_key": "..."}.
    La validación usa `secrets.compare_digest` para evitar timing attacks.

    Args:
        websocket: La instancia WebSocket ya aceptada (después de accept()).
        timeout:   Segundos máximos para esperar el mensaje de auth.

    Returns:
        El session_id (str UUID) si la autenticación fue exitosa.
        None si falló (la conexión ya está cerrada al retornar None).
    """
    try:
        # Esperar el primer mensaje con timeout
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("ws_auth: timeout esperando mensaje de autenticación")
        await _close_with_error(
            websocket,
            error_code="AUTH_TIMEOUT",
            message="Tiempo de espera agotado para autenticación",
        )
        return None
    except Exception as exc:
        logger.warning("ws_auth: error recibiendo mensaje de auth: %s", exc)
        return None

    # Parsear JSON
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("ws_auth: mensaje no es JSON válido")
        await _close_with_error(
            websocket,
            error_code="INVALID_MESSAGE",
            message="El primer mensaje debe ser JSON",
        )
        return None

    # Verificar tipo
    if data.get("type") != "auth":
        logger.warning(
            "ws_auth: primer mensaje no es de tipo 'auth', es '%s'", data.get("type")
        )
        await _close_with_error(
            websocket,
            error_code="INVALID_MESSAGE",
            message="El primer mensaje debe ser de tipo 'auth'",
        )
        return None

    # Validar API Key con comparación constant-time
    api_key: str = str(data.get("api_key", ""))
    if not secrets.compare_digest(api_key.encode(), settings.API_KEY.encode()):
        logger.warning("ws_auth: API Key inválida")
        await _close_with_error(
            websocket,
            error_code="INVALID_API_KEY",
            message="API Key inválida",
        )
        return None

    # Auth OK — generar session_id y enviarlo
    session_id = new_session_id()
    try:
        await websocket.send_text(make_auth_ok(session_id))
    except Exception as exc:
        logger.error("ws_auth: error enviando auth_ok: %s", exc)
        return None

    logger.info("ws_auth: sesión autenticada session_id=%s", session_id)
    return session_id


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _close_with_error(
    websocket: WebSocket,
    error_code: str,
    message: str,
) -> None:
    """Envía un mensaje de error y cierra la conexión WebSocket."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(
                make_error(error_code=error_code, message=message)
            )
        await websocket.close(code=1008)
    except Exception:
        # La conexión puede ya estar cerrada
        pass
