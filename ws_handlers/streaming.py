"""
ws_handlers/streaming.py — Handler WebSocket principal para /ws/interact.

Implementa el flujo completo de §3.4:
  1. Acepta la conexión y autentica vía API Key.
  2. Bucle de mensajes: acumula audio binario, maneja texto e interaction_start.
  3. Al recibir audio_end o text: carga memoria, historial y lanza el agente.
  4. Parsea [emotion:TAG] del primer token del stream → envía emotion de inmediato.
  5. Envía text_chunk progresivamente.
  6. Al finalizar el stream: classify_intent → capture_request si aplica.
  7. Envía response_meta y stream_end.
  8. Background: guarda messages en el historial + compactación.

Uso (registrado en main.py):
    from ws_handlers.streaming import ws_interact

    @app.websocket("/ws/interact")
    async def websocket_interact(websocket: WebSocket):
        await ws_interact(websocket)
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import db as db_module
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from db import InteractionRow
from repositories.memory import MemoryRepository
from services.agent import create_agent, run_agent_stream
from services.expression import emotion_to_emojis, parse_emotion_tag
from services.history import ConversationHistory
from services.intent import classify_intent
from ws_handlers.auth import authenticate_websocket
from ws_handlers.protocol import (
    make_capture_request,
    make_emotion,
    make_error,
    make_response_meta,
    make_stream_end,
    make_text_chunk,
    new_session_id,
)

logger = logging.getLogger(__name__)

# Tamaño máximo del buffer de prefijo para detectar el emotion tag completo
_MAX_EMOTION_BUFFER = 200


# ── Entry point ───────────────────────────────────────────────────────────────


async def ws_interact(websocket: WebSocket) -> None:
    """
    Handler principal para el endpoint WebSocket /ws/interact.

    Acepta la conexión, autentica, y entra en el bucle de mensajes.
    Gestiona múltiples interacciones por sesión hasta que el cliente desconecta.
    """
    await websocket.accept()

    # Autenticar — retorna session_id o None (ya closed)
    session_id = await authenticate_websocket(websocket)
    if session_id is None:
        return

    # Objetos de sesión (one per WS connection)
    history_service = ConversationHistory()
    agent = create_agent()

    # Estado de la interacción actual
    user_id: str = "unknown"
    request_id: str = ""
    audio_buffer: bytes = b""

    logger.info("ws: sesión iniciada session_id=%s", session_id)

    try:
        while True:
            # Recibir siguiente mensaje (texto JSON o binario)
            data = await websocket.receive()

            msg_type = data.get("type", "")

            # Desconexión limpia del cliente
            if msg_type == "websocket.disconnect":
                logger.info("ws: cliente desconectado session_id=%s", session_id)
                break

            # ── Mensajes binarios (audio frames) ─────────────────────────────
            raw_bytes = data.get("bytes")
            if raw_bytes:
                audio_buffer += raw_bytes
                continue

            # ── Mensajes de texto (JSON) ──────────────────────────────────────
            raw_text = data.get("text")
            if not raw_text:
                continue

            try:
                msg = json.loads(raw_text)
            except (json.JSONDecodeError, ValueError):
                await _send_safe(
                    websocket,
                    make_error("INVALID_MESSAGE", "Mensaje no es JSON válido"),
                )
                continue

            client_type = msg.get("type", "")

            if client_type == "interaction_start":
                user_id = msg.get("user_id", "unknown")
                request_id = msg.get("request_id") or new_session_id()
                audio_buffer = b""  # limpiar buffer de interacción anterior
                logger.debug(
                    "ws: interaction_start user_id=%s request_id=%s",
                    user_id,
                    request_id,
                )

            elif client_type == "text":
                user_input = msg.get("content", "")
                if not request_id:
                    request_id = msg.get("request_id") or new_session_id()
                else:
                    request_id = msg.get("request_id") or request_id

                if user_input:
                    await _process_interaction(
                        websocket=websocket,
                        user_id=user_id,
                        request_id=request_id,
                        user_input=user_input,
                        input_type="text",
                        history_service=history_service,
                        session_id=session_id,
                        agent=agent,
                    )

            elif client_type == "audio_end":
                if not request_id:
                    request_id = msg.get("request_id") or new_session_id()
                else:
                    request_id = msg.get("request_id") or request_id

                # El audio se procesa si hay datos; por ahora usamos
                # un placeholder ya que el pipeline STT se añadirá posteriormente.
                if audio_buffer:
                    audio_data = audio_buffer
                    audio_buffer = b""
                    await _process_interaction(
                        websocket=websocket,
                        user_id=user_id,
                        request_id=request_id,
                        user_input=None,
                        input_type="audio",
                        audio_data=audio_data,
                        history_service=history_service,
                        session_id=session_id,
                        agent=agent,
                    )
                else:
                    await _send_safe(
                        websocket,
                        make_error(
                            "EMPTY_AUDIO",
                            "No se recibieron datos de audio",
                            request_id=request_id,
                            recoverable=True,
                        ),
                    )

            elif client_type == "image":
                # Multimodal: imagen de contexto o registro
                if not request_id:
                    request_id = msg.get("request_id") or new_session_id()
                else:
                    request_id = msg.get("request_id") or request_id
                purpose = msg.get("purpose", "context")
                await _process_interaction(
                    websocket=websocket,
                    user_id=user_id,
                    request_id=request_id,
                    user_input=f"(imagen de {purpose} recibida)",
                    input_type="vision",
                    history_service=history_service,
                    session_id=session_id,
                    agent=agent,
                )

            elif client_type == "video":
                if not request_id:
                    request_id = msg.get("request_id") or new_session_id()
                else:
                    request_id = msg.get("request_id") or request_id
                duration_ms = msg.get("duration_ms", 0)
                await _process_interaction(
                    websocket=websocket,
                    user_id=user_id,
                    request_id=request_id,
                    user_input=f"(video de {duration_ms}ms recibido)",
                    input_type="vision",
                    history_service=history_service,
                    session_id=session_id,
                    agent=agent,
                )

    except Exception as exc:
        logger.error(
            "ws: error inesperado en sesión %s: %s", session_id, exc, exc_info=True
        )
        if websocket.client_state == WebSocketState.CONNECTED:
            await _send_safe(
                websocket,
                make_error(
                    "INTERNAL_ERROR",
                    "Error interno del servidor",
                    recoverable=False,
                ),
            )
    finally:
        logger.info("ws: sesión cerrada session_id=%s", session_id)


# ── Procesamiento de una interacción ─────────────────────────────────────────


async def _process_interaction(
    *,
    websocket: WebSocket,
    user_id: str,
    request_id: str,
    user_input: str | None,
    input_type: str,  # "text" | "audio" | "vision"
    history_service: ConversationHistory,
    session_id: str,
    agent,
    audio_data: bytes | None = None,
) -> None:
    """
    Procesa una interacción completa:
      load memory → run agent stream → emit emotion + text_chunks → emit meta
    """
    start_time = time.monotonic()

    if user_input is None:
        # audio sin transcripción — placeholder
        user_input = "(audio recibido)"

    # 1. Cargar memoria del usuario
    memories = await _load_memories(user_id)

    # 2. Obtener historial de la sesión
    history = history_service.get_history(session_id)

    # 3. Enriquecer el input con el contexto de memoria
    enriched_input = _build_context_input(user_input, memories)

    # 4. Streaming del agente
    full_response = ""
    emotion_tag = "neutral"
    emotion_sent = False
    prefix_buf = ""

    try:
        async for chunk in run_agent_stream(
            user_input=enriched_input,
            history=history,
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        ):
            if not chunk:
                continue

            if not emotion_sent:
                # Acumular prefijo para detectar el emotion tag completo
                prefix_buf += chunk
                has_closing_bracket = "]" in prefix_buf
                buffer_full = len(prefix_buf) >= _MAX_EMOTION_BUFFER

                if has_closing_bracket or buffer_full:
                    # Parsear el emotion tag del buffer
                    emotion_tag, remaining = parse_emotion_tag(prefix_buf)

                    # Enviar emotion ANTES del texto (§3.4 step 1)
                    await _send_safe(
                        websocket,
                        make_emotion(
                            request_id=request_id,
                            emotion=emotion_tag,
                            user_identified=user_id if user_id != "unknown" else None,
                        ),
                    )
                    emotion_sent = True

                    # Enviar el texto restante del prefijo como primer text_chunk
                    if remaining:
                        await _send_safe(
                            websocket,
                            make_text_chunk(request_id, remaining),
                        )
                        full_response += remaining
            else:
                # Streaming normal de text_chunks
                await _send_safe(websocket, make_text_chunk(request_id, chunk))
                full_response += chunk

    except Exception as exc:
        logger.error(
            "ws: error en agente session_id=%s request_id=%s: %s",
            session_id,
            request_id,
            exc,
            exc_info=True,
        )
        await _send_safe(
            websocket,
            make_error(
                "AGENT_ERROR",
                "Error procesando la solicitud",
                request_id=request_id,
                recoverable=True,
            ),
        )
        return

    # Si el stream terminó sin emitir la emoción (respuesta vacía), emitir neutral
    if not emotion_sent:
        if prefix_buf:
            emotion_tag, remaining = parse_emotion_tag(prefix_buf)
            full_response += remaining
        await _send_safe(
            websocket,
            make_emotion(
                request_id=request_id,
                emotion=emotion_tag,
                user_identified=user_id if user_id != "unknown" else None,
            ),
        )
        if full_response:
            await _send_safe(websocket, make_text_chunk(request_id, full_response))

    # 5. Detectar intent → capture_request si aplica
    intent = classify_intent(full_response)
    if intent == "photo_request":
        await _send_safe(websocket, make_capture_request(request_id, "photo"))
    elif intent == "video_request":
        await _send_safe(websocket, make_capture_request(request_id, "video"))

    # 6. Construir y enviar response_meta
    emojis = emotion_to_emojis(emotion_tag)
    processing_ms = int((time.monotonic() - start_time) * 1000)

    await _send_safe(
        websocket,
        make_response_meta(
            request_id=request_id,
            response_text=full_response,
            emojis=emojis,
        ),
    )

    # 7. Enviar stream_end
    await _send_safe(
        websocket,
        make_stream_end(request_id=request_id, processing_time_ms=processing_ms),
    )

    # 8. Background: guardar mensajes en historial + compactar
    asyncio.create_task(
        _save_history_bg(
            history_service=history_service,
            session_id=session_id,
            user_message=user_input,
            assistant_message=full_response,
        )
    )

    # 9. Background: guardar interacción en BD (solo usuarios registrados)
    if user_id != "unknown":
        asyncio.create_task(
            _save_interaction_bg(
                user_id=user_id,
                input_type=input_type,
                summary=full_response[:500],
            )
        )


# ── Background tasks ──────────────────────────────────────────────────────────


async def _save_history_bg(
    history_service: ConversationHistory,
    session_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """Guarda los mensajes de la interacción en el historial y compacta si es necesario."""
    try:
        await history_service.add_message(session_id, "user", user_message)
        await history_service.add_message(session_id, "assistant", assistant_message)
        await history_service.compact_if_needed(session_id)
    except Exception as exc:
        logger.warning(
            "ws: error guardando historial session_id=%s: %s", session_id, exc
        )


async def _save_interaction_bg(
    user_id: str,
    input_type: str,
    summary: str,
) -> None:
    """Guarda la interacción en la tabla interactions (solo usuarios registrados)."""
    if db_module.AsyncSessionLocal is None:
        return
    try:
        async with db_module.AsyncSessionLocal() as session:
            row = InteractionRow(
                user_id=user_id,
                request_type=input_type,
                summary=summary,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        logger.warning("ws: error guardando interacción user_id=%s: %s", user_id, exc)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _load_memories(user_id: str) -> list:
    """Carga las memorias más importantes del usuario desde la BD."""
    if user_id == "unknown" or db_module.AsyncSessionLocal is None:
        return []
    try:
        async with db_module.AsyncSessionLocal() as session:
            repo = MemoryRepository(session)
            return await repo.get_recent_important(user_id, min_importance=5, limit=5)
    except Exception as exc:
        logger.warning("ws: error cargando memoria user_id=%s: %s", user_id, exc)
        return []


def _build_context_input(user_input: str, memories: list) -> str:
    """
    Añade el contexto de memorias del usuario al input antes de enviarlo al agente.
    Si no hay memorias, devuelve el input sin modificar.
    """
    if not memories:
        return user_input
    memory_lines = [f"- {m.content}" for m in memories]
    memory_block = "\n".join(memory_lines)
    return f"[Contexto del usuario:\n{memory_block}\n]\n\n{user_input}"


async def _send_safe(websocket: WebSocket, text: str) -> None:
    """Envía un mensaje de texto ignorando errores si la conexión está cerrada."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(text)
    except Exception as exc:
        logger.debug("ws: _send_safe ignorando error: %s", exc)
