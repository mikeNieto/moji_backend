"""
ws_handlers/streaming.py — Handler WebSocket principal para /ws/interact.

v3.0 — Moji Amigo Familiar

Implementa el flujo completo:
  1. Acepta la conexión y autentica vía API Key.
  2. Bucle de mensajes: gestiona todos los tipos de mensaje del protocolo v2.0.
  3. Invoca el agente con structured output (MojiResponse).
  4. Envía emotion + text_chunk + response_meta + stream_end.
  5. Background: historial + compactación de memorias + persistencia de persona/memoria.

Uso (registrado en main.py):
    from ws_handlers.streaming import ws_interact

    @app.websocket("/ws/interact")
    async def websocket_interact(websocket: WebSocket):
        await ws_interact(websocket)
"""

import asyncio
import base64
import json
import logging
import time

import db as db_module
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from repositories.memory import MemoryRepository
from repositories.people import PeopleRepository
from services.agent import run_agent
from services.expression import emotion_to_emojis
from services.memory_compaction import compact_memories_async
from services.movement import action_steps_from_list, build_move_sequence
from services.history import ConversationHistory
from services.intent import classify_intent
from ws_handlers.auth import authenticate_websocket
from ws_handlers.protocol import (
    make_capture_request,
    make_emotion,
    make_error,
    make_face_scan_actions,
    make_response_meta,
    make_stream_end,
    make_text_chunk,
    new_request_id,
)

logger = logging.getLogger(__name__)

# Secuencia de giro ESP32 para face_scan_mode
_FACE_SCAN_SEQUENCE: list[dict] = [
    {"action": "turn_right_deg", "degrees": 45, "duration_ms": 500},
    {"action": "pause", "duration_ms": 300},
    {"action": "turn_left_deg", "degrees": 90, "duration_ms": 800},
    {"action": "pause", "duration_ms": 300},
    {"action": "turn_right_deg", "degrees": 45, "duration_ms": 500},
]


# ── Entry point ───────────────────────────────────────────────────────────────


async def ws_interact(websocket: WebSocket) -> None:
    """
    Handler principal para el endpoint WebSocket /ws/interact.

    Acepta la conexión, autentica, y entra en el bucle de mensajes.
    Gestiona múltiples interacciones por conexión hasta que el cliente desconecta.
    """
    await websocket.accept()

    # Autenticar — cierra la conexión si falla, retorna None
    if not await authenticate_websocket(websocket):
        return

    # Historial global persistente (cargado desde BD al iniciar)
    history_service = ConversationHistory()
    await history_service.load_from_db()

    # Estado de la interacción actual
    person_id: str | None = None  # slug de la persona identificada
    request_id: str = ""
    audio_buffer: bytes = b""
    pending_face_embedding: str | None = None  # base64 embedding pendiente de asociar

    logger.info(
        "ws: conexión autenticada, historial con %d mensajes",
        len(history_service._cache),
    )

    try:
        while True:
            # Recibir siguiente mensaje (texto JSON o binario)
            data = await websocket.receive()

            msg_type = data.get("type", "")

            # Desconexión limpia del cliente
            if msg_type == "websocket.disconnect":
                logger.info("ws: cliente desconectado")
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
                person_id = msg.get("person_id") or None
                request_id = msg.get("request_id") or new_request_id()
                audio_buffer = b""  # limpiar buffer de interacción anterior
                pending_face_embedding = msg.get("face_embedding") or None
                logger.debug(
                    "ws: interaction_start person_id=%s request_id=%s has_embedding=%s",
                    person_id,
                    request_id,
                    pending_face_embedding is not None,
                )

            elif client_type == "text":
                user_input = msg.get("content", "")
                if not request_id:
                    request_id = msg.get("request_id") or new_request_id()
                else:
                    request_id = msg.get("request_id") or request_id
                face_emb = msg.get("face_embedding") or pending_face_embedding
                pending_face_embedding = None

                if user_input:
                    await _process_interaction(
                        websocket=websocket,
                        person_id=person_id,
                        request_id=request_id,
                        user_input=user_input,
                        input_type="text",
                        history_service=history_service,
                        face_embedding_b64=face_emb,
                    )

            elif client_type == "audio_end":
                if not request_id:
                    request_id = msg.get("request_id") or new_request_id()
                else:
                    request_id = msg.get("request_id") or request_id
                face_emb = msg.get("face_embedding") or pending_face_embedding
                pending_face_embedding = None

                if audio_buffer:
                    audio_data = audio_buffer
                    audio_buffer = b""
                    await _process_interaction(
                        websocket=websocket,
                        person_id=person_id,
                        request_id=request_id,
                        user_input=None,
                        input_type="audio",
                        audio_data=audio_data,
                        history_service=history_service,
                        face_embedding_b64=face_emb,
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
                if not request_id:
                    request_id = msg.get("request_id") or new_request_id()
                else:
                    request_id = msg.get("request_id") or request_id
                raw_b64 = msg.get("data", "")
                image_bytes: bytes | None = None
                if raw_b64:
                    try:
                        image_bytes = base64.b64decode(raw_b64)
                    except Exception:
                        image_bytes = None
                inline_text: str | None = msg.get("text") or None
                face_emb = msg.get("face_embedding") or pending_face_embedding
                pending_face_embedding = None
                await _process_interaction(
                    websocket=websocket,
                    person_id=person_id,
                    request_id=request_id,
                    user_input=inline_text,
                    input_type="vision",
                    image_data=image_bytes,
                    history_service=history_service,
                    face_embedding_b64=face_emb,
                )

            elif client_type == "video":
                if not request_id:
                    request_id = msg.get("request_id") or new_request_id()
                else:
                    request_id = msg.get("request_id") or request_id
                raw_b64 = msg.get("data", "")
                video_bytes: bytes | None = None
                if raw_b64:
                    try:
                        video_bytes = base64.b64decode(raw_b64)
                    except Exception:
                        video_bytes = None
                inline_text_v: str | None = msg.get("text") or None
                await _process_interaction(
                    websocket=websocket,
                    person_id=person_id,
                    request_id=request_id,
                    user_input=inline_text_v,
                    input_type="vision",
                    video_data=video_bytes,
                    history_service=history_service,
                )

            elif client_type == "multimodal":
                if not request_id:
                    request_id = msg.get("request_id") or new_request_id()
                else:
                    request_id = msg.get("request_id") or request_id

                def _b64_decode(field: str) -> bytes | None:
                    raw = msg.get(field)
                    if not raw:
                        return None
                    try:
                        return base64.b64decode(raw)
                    except Exception:
                        return None

                mm_text: str | None = msg.get("text") or None
                mm_audio = _b64_decode("audio")
                mm_image = _b64_decode("image")
                mm_video = _b64_decode("video")
                mm_audio_mime: str = msg.get("audio_mime", "audio/webm")
                mm_image_mime: str = msg.get("image_mime", "image/jpeg")
                mm_video_mime: str = msg.get("video_mime", "video/mp4")
                face_emb_mm = msg.get("face_embedding") or pending_face_embedding
                pending_face_embedding = None

                input_type_mm = (
                    "vision"
                    if (mm_image or mm_video)
                    else ("audio" if mm_audio else "text")
                )
                await _process_interaction(
                    websocket=websocket,
                    person_id=person_id,
                    request_id=request_id,
                    user_input=mm_text,
                    input_type=input_type_mm,
                    audio_data=mm_audio,
                    image_data=mm_image,
                    video_data=mm_video,
                    audio_mime_type=mm_audio_mime,
                    image_mime_type=mm_image_mime,
                    video_mime_type=mm_video_mime,
                    history_service=history_service,
                    face_embedding_b64=face_emb_mm,
                )

            # ── Mensajes nuevos v2.0 ───────────────────────────────────────────

            elif client_type == "face_scan_mode":
                # Android inicia escaneo facial activo — Moji gira con secuencia predefinida.
                req_id = msg.get("request_id") or new_request_id()
                scan_seq = [build_move_sequence("Escaneo facial", _FACE_SCAN_SEQUENCE)]
                await _send_safe(
                    websocket,
                    make_face_scan_actions(request_id=req_id, actions=scan_seq),
                )

            elif client_type == "person_detected":
                # Android informa de una persona detectada.
                req_id = msg.get("request_id") or new_request_id()
                known = msg.get("known", False)
                detected_pid = msg.get("person_id") or None
                confidence = msg.get("confidence", 0.0)
                if known and detected_pid:
                    person_id = detected_pid
                    logger.info(
                        "ws: persona conocida detectada person_id=%s conf=%.2f",
                        person_id,
                        confidence,
                    )
                else:
                    # Cara desconocida: Moji debe preguntar el nombre
                    context = await _load_moji_context(None)
                    ask_input = (
                        "Acabo de detectar a una persona que no conozco. "
                        "Salúdala con curiosidad y pregúntale su nombre de forma amigable."
                    )
                    await _process_interaction(
                        websocket=websocket,
                        person_id=None,
                        request_id=req_id,
                        user_input=ask_input,
                        input_type="text",
                        history_service=history_service,
                        memory_context=context,
                    )

    except Exception as exc:
        logger.error("ws: error inesperado: %s", exc, exc_info=True)
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
        logger.info("ws: conexión cerrada")


# ── Procesamiento de una interacción ─────────────────────────────────────────


async def _process_interaction(
    *,
    websocket: WebSocket,
    person_id: str | None,
    request_id: str,
    user_input: str | None,
    input_type: str,  # "text" | "audio" | "vision"
    history_service: ConversationHistory,
    audio_data: bytes | None = None,
    audio_mime_type: str = "audio/webm",
    image_data: bytes | None = None,
    image_mime_type: str = "image/jpeg",
    video_data: bytes | None = None,
    video_mime_type: str = "video/mp4",
    face_embedding_b64: str | None = None,
    memory_context: dict | None = None,
) -> None:
    """
    Procesa una interacción completa:
      load context → run_agent (structured output) → emit emotion + text_chunk
      → persist memories/person → emit meta + stream_end → background tasks
    """
    start_time = time.monotonic()

    # 1. Cargar contexto de memorias (si no se pasó ya)
    if memory_context is None:
        memory_context = await _load_moji_context(person_id)

    # 2. Obtener historial global
    history = history_service.get_history()

    logger.info("History (%d mensajes): %s", len(history), history)

    has_media = (
        audio_data is not None or image_data is not None or video_data is not None
    )
    has_face_embedding = face_embedding_b64 is not None

    # 3. Invocar el agente con structured output
    try:
        response = await run_agent(
            user_input=user_input,
            history=history,
            person_id=person_id,
            audio_data=audio_data,
            audio_mime_type=audio_mime_type,
            image_data=image_data,
            image_mime_type=image_mime_type,
            video_data=video_data,
            video_mime_type=video_mime_type,
            memory_context=memory_context,
            has_face_embedding=has_face_embedding,
        )
    except Exception as exc:
        logger.error(
            "ws: error en agente request_id=%s: %s",
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

    # 4. Enviar emoción
    await _send_safe(
        websocket,
        make_emotion(
            request_id=request_id,
            emotion=response.emotion,
            person_identified=person_id,
        ),
    )

    # 5. Enviar el texto de respuesta como un único chunk
    if response.response_text:
        await _send_safe(websocket, make_text_chunk(request_id, response.response_text))

    # 6. Persistir memories en background
    for mem in response.memories:
        asyncio.create_task(
            _save_memory_bg(
                memory_type=mem.memory_type,
                content=mem.content,
                person_id=person_id,
            ),
            name=f"memory-{request_id}",
        )

    # 7. Persistir person_name en background (solo si hay face embedding)
    if has_face_embedding and face_embedding_b64 and response.person_name:
        asyncio.create_task(
            _save_person_name_bg(
                name=response.person_name,
                person_id=person_id,
                face_embedding_b64=face_embedding_b64,
            ),
            name=f"person-{request_id}",
        )

    # 8. Detectar intent de captura
    intent = classify_intent(response.response_text)
    if intent == "photo_request":
        await _send_safe(websocket, make_capture_request(request_id, "photo"))
    elif intent == "video_request":
        await _send_safe(websocket, make_capture_request(request_id, "video"))

    # 9. Construir y enviar response_meta
    # Emojis: primero los contextuales del LLM, luego respaldo de emoción
    emotion_emojis = emotion_to_emojis(response.emotion)
    emojis = (
        (response.emojis + emotion_emojis[:2]) if response.emojis else emotion_emojis
    )
    # Acciones: convertir lista de strings a secuencia ESP32
    actions: list[dict] = []
    if response.actions:
        steps = action_steps_from_list(response.actions)
        if steps:
            actions = [build_move_sequence("Movimiento sugerido por Moji", steps)]

    processing_ms = int((time.monotonic() - start_time) * 1000)

    await _send_safe(
        websocket,
        make_response_meta(
            request_id=request_id,
            response_text=response.response_text,
            emojis=emojis,
            actions=actions,
            person_name=response.person_name,
        ),
    )

    # 10. Enviar stream_end
    await _send_safe(
        websocket,
        make_stream_end(request_id=request_id, processing_time_ms=processing_ms),
    )

    # 11. Background: guardar historial
    if not has_media:
        history_user_msg = user_input or ""
    elif response.media_summary:
        history_user_msg = response.media_summary
    else:
        logger.warning(
            "ws: LLM no rellenó media_summary para interacción media "
            "request_id=%s — usando placeholder",
            request_id,
        )
        history_user_msg = "[audio]" if audio_data is not None else "[imagen/video]"

    asyncio.create_task(
        _save_history_bg(
            history_service=history_service,
            user_message=history_user_msg,
            assistant_message=response.response_text,
            person_id=person_id,
        )
    )

    # 12. Background: compactación de memorias
    asyncio.create_task(
        compact_memories_async(person_id=person_id),
        name=f"compact-memories-{request_id}",
    )


# ── Background tasks ──────────────────────────────────────────────────────────


async def _save_history_bg(
    history_service: ConversationHistory,
    user_message: str,
    assistant_message: str,
    person_id: str | None = None,
) -> None:
    """Guarda los mensajes de la interacción en el historial y compacta si es necesario."""
    try:
        await history_service.add_message("user", user_message, person_id=person_id)
        await history_service.add_message("assistant", assistant_message)
        await history_service.compact_if_needed()
    except Exception as exc:
        logger.warning("ws: error guardando historial: %s", exc)


async def _save_memory_bg(
    memory_type: str,
    content: str,
    person_id: str | None = None,
) -> None:
    """Persiste una memoria extraída del tag [memory:TIPO:contenido] en background."""
    if db_module.AsyncSessionLocal is None:
        return
    try:
        async with db_module.AsyncSessionLocal() as session:
            repo = MemoryRepository(session)
            await repo.save(
                memory_type=memory_type,
                content=content,
                person_id=person_id,
            )
            await session.commit()
    except Exception as exc:
        logger.warning("ws: error guardando memoria type=%s: %s", memory_type, exc)


async def _save_person_name_bg(
    name: str,
    person_id: str | None,
    face_embedding_b64: str,
) -> None:
    """
    Registra (o actualiza) la persona en la BD y guarda su embedding facial.
    Llamado cuando el LLM emite [person_name:NOMBRE] junto a un face_embedding.
    """
    if db_module.AsyncSessionLocal is None:
        return
    try:
        slug = (
            person_id
            or f"persona_{name.lower().replace(' ', '_')[:20]}_{id(name) % 10000:04d}"
        )
        embedding_bytes = base64.b64decode(face_embedding_b64)
        async with db_module.AsyncSessionLocal() as session:
            people_repo = PeopleRepository(session)
            person, created = await people_repo.get_or_create(slug, name)
            if not created and person.name != name:
                await people_repo.update_name(slug, name)
            await people_repo.add_embedding(slug, embedding_bytes)
            await session.commit()
        logger.info("ws: persona registrada person_id=%s name=%s", slug, name)
    except Exception as exc:
        logger.warning("ws: error registrando persona name=%s: %s", name, exc)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _load_moji_context(person_id: str | None) -> dict:
    """Carga el contexto de memorias de Moji desde la BD (general + persona)."""
    if db_module.AsyncSessionLocal is None:
        return {}
    try:
        async with db_module.AsyncSessionLocal() as session:
            repo = MemoryRepository(session)
            return await repo.get_moji_context(person_id=person_id)
    except Exception as exc:
        logger.warning("ws: error cargando contexto person_id=%s: %s", person_id, exc)
        return {}


async def _send_safe(websocket: WebSocket, text: str) -> None:
    """Envía un mensaje de texto ignorando errores si la conexión está cerrada."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(text)
    except Exception as exc:
        logger.debug("ws: _send_safe ignorando error: %s", exc)
