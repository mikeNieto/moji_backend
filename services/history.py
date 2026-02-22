"""
services/history.py — Historial de conversación con compactación automática.

v2.0 — Robi Amigo Familiar
  - Sesiones identificadas por `session_id` + `person_id` opcional.
  - Sin dependencia de `user_id`.

El historial se mantiene en la BD (tabla conversation_history) para persistir
entre reinicios del servidor. La compactación reduce msgs 0–(N-5) a un resumen
cuando el total supera el umbral (CONVERSATION_COMPACTION_THRESHOLD, default 20).

Uso:
    from services.history import ConversationHistory
    history = ConversationHistory()

    await history.add_message("sess_abc", "user", "Hola Robi", person_id="persona_juan_01")
    await history.add_message("sess_abc", "assistant", "[emotion:greeting] Hola!")
    msgs = history.get_history("sess_abc")
    await history.compact_if_needed("sess_abc")
"""

import asyncio
import logging
from datetime import datetime, timezone

import db as db_module
from config import settings
from db import ConversationHistoryRow
from services.gemini import get_model

logger = logging.getLogger(__name__)


class ConversationHistory:
    """
    Gestiona el historial de conversación por sesión.

    - add_message: Persiste un mensaje en la BD y en la caché en memoria.
    - get_history: Devuelve los mensajes de la sesión como lista de dicts.
    - compact_if_needed: Si el historial supera el umbral, lanza compactación
      asíncrona en background (asyncio.create_task) sin bloquear al llamante.
    """

    def __init__(self) -> None:
        # Caché en memoria: session_id → lista de dicts {role, content, index}
        self._cache: dict[str, list[dict]] = {}

    # ── API pública ───────────────────────────────────────────────────────────

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        person_id: str | None = None,
    ) -> None:
        """
        Añade un mensaje al historial de la sesión.

        - `person_id`: slug de la persona identificada en esta interacción (opcional,
          usado solo para logging enriquecido; no se persiste en esta tabla).
        - Persiste en la tabla conversation_history.
        - Actualiza la caché en memoria.
        """
        msgs = self._cache.setdefault(session_id, [])
        index = len(msgs)

        assert db_module.AsyncSessionLocal is not None
        async with db_module.AsyncSessionLocal() as session:
            row = ConversationHistoryRow(
                session_id=session_id,
                role=role,
                content=content,
                message_index=index,
                is_compacted=False,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()

        msgs.append({"role": role, "content": content, "index": index})

    def get_history(self, session_id: str) -> list[dict]:
        """
        Devuelve el historial de la sesión como lista de dicts {role, content}.
        Formateada para pasarla directamente como `history` al agente.
        """
        msgs = self._cache.get(session_id, [])
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    async def load_from_db(self, session_id: str) -> None:
        """
        Carga el historial de la BD a la caché. Llamar al inicio de una sesión
        para recuperar conversaciones previas tras un reinicio del servidor.
        """
        from sqlalchemy import select

        assert db_module.AsyncSessionLocal is not None
        async with db_module.AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationHistoryRow)
                .where(ConversationHistoryRow.session_id == session_id)
                .order_by(ConversationHistoryRow.message_index)
            )
            rows = result.scalars().all()

        self._cache[session_id] = [
            {"role": r.role, "content": r.content, "index": r.message_index}
            for r in rows
        ]

    async def compact_if_needed(self, session_id: str) -> None:
        """
        Si el historial de la sesión tiene >= CONVERSATION_COMPACTION_THRESHOLD
        mensajes, lanza una tarea asíncrona en background para compactar los
        mensajes más antiguos (todos excepto los últimos 5).

        La compactación NO bloquea la respuesta al usuario.
        """
        msgs = self._cache.get(session_id, [])
        threshold = settings.CONVERSATION_COMPACTION_THRESHOLD

        if len(msgs) >= threshold:
            asyncio.create_task(
                self._compact(session_id),
                name=f"compact-{session_id}",
            )

    # ── Implementación interna ────────────────────────────────────────────────

    async def _compact(self, session_id: str) -> None:
        """
        Compacta los mensajes 0..(N-5) del historial en un resumen generado
        por Gemini, reemplazándolos por un único mensaje con is_compacted=True.

        Los últimos 5 mensajes se conservan intactos para mantener el contexto
        reciente de la conversación.
        """
        msgs = self._cache.get(session_id, [])
        if len(msgs) < 6:
            return  # nada que compactar

        keep = 5
        to_compact = msgs[:-keep]
        to_keep = msgs[-keep:]

        # Construir el texto a resumir
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in to_compact
        )
        summary_prompt = (
            f"Resume de forma concisa la siguiente conversación, "
            f"manteniendo los hechos y preferencias clave del usuario:\n\n"
            f"{conversation_text}"
        )

        try:
            model = get_model()
            summary_msg = await model.ainvoke(summary_prompt)
            summary_text = (
                summary_msg.content
                if hasattr(summary_msg, "content")
                else str(summary_msg)
            )
        except Exception:
            logger.exception("Error compactando historial de sesión %s", session_id)
            return

        # Actualizar BD: borrar los mensajes compactados y añadir el resumen
        from sqlalchemy import delete

        assert db_module.AsyncSessionLocal is not None
        async with db_module.AsyncSessionLocal() as session:
            async with session.begin():
                # Eliminar las filas antiguas
                old_indices = [m["index"] for m in to_compact]
                await session.execute(
                    delete(ConversationHistoryRow).where(
                        ConversationHistoryRow.session_id == session_id,
                        ConversationHistoryRow.message_index.in_(old_indices),
                    )
                )
                # Insertar el resumen compactado
                session.add(
                    ConversationHistoryRow(
                        session_id=session_id,
                        role="assistant",
                        content=f"[RESUMEN] {summary_text}",
                        message_index=0,
                        is_compacted=True,
                        timestamp=datetime.now(timezone.utc),
                    )
                )

        # Actualizar la caché en memoria
        compacted_entry = {
            "role": "assistant",
            "content": f"[RESUMEN] {summary_text}",
            "index": 0,
        }
        self._cache[session_id] = [compacted_entry] + [
            {"role": m["role"], "content": m["content"], "index": i + 1}
            for i, m in enumerate(to_keep)
        ]
