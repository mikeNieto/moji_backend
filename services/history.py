"""
services/history.py — Historial de conversación global con compactación automática.

v3.0 — Moji Amigo Familiar
  - Historial único y global: sin partición por sesión.
  - El robot recuerda TODAS las conversaciones, persistidas y compactadas.

El historial se mantiene en la BD (tabla conversation_history) para persistir
entre reinicios del servidor. La compactación reduce msgs 0..(N-5) a un resumen
cuando el total supera el umbral (CONVERSATION_COMPACTION_THRESHOLD, default 20).

Uso:
    from services.history import ConversationHistory
    history = ConversationHistory()

    await history.load_from_db()          # recuperar al arrancar el servidor
    await history.add_message("user", "Hola Moji", person_id="persona_juan_01")
    await history.add_message("assistant", "[emotion:greeting] Hola!")
    msgs = history.get_history()
    await history.compact_if_needed()
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
    Gestiona el historial de conversación global del robot.

    - add_message: Persiste un mensaje en la BD y en la caché en memoria.
    - get_history: Devuelve todos los mensajes como lista de dicts.
    - compact_if_needed: Si el historial supera el umbral, lanza compactación
      asíncrona en background (asyncio.create_task) sin bloquear al llamante.
    """

    def __init__(self) -> None:
        # Caché global en memoria: lista de dicts {role, content, index}
        self._cache: list[dict] = []

    # ── API pública ───────────────────────────────────────────────────────────

    async def add_message(
        self,
        role: str,
        content: str,
        person_id: str | None = None,
    ) -> None:
        """
        Añade un mensaje al historial global.

        - `person_id`: slug de la persona identificada en esta interacción (opcional,
          usado solo para logging enriquecido; no se persiste en esta tabla).
        - Persiste en la tabla conversation_history.
        - Actualiza la caché en memoria.
        """
        index = len(self._cache)

        assert db_module.AsyncSessionLocal is not None
        async with db_module.AsyncSessionLocal() as session:
            row = ConversationHistoryRow(
                role=role,
                content=content,
                message_index=index,
                is_compacted=False,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()

        self._cache.append({"role": role, "content": content, "index": index})

    def get_history(self) -> list[dict]:
        """
        Devuelve el historial global como lista de dicts {role, content}.
        Formateada para pasarla directamente como `history` al agente.
        """
        return [{"role": m["role"], "content": m["content"]} for m in self._cache]

    async def load_from_db(self) -> None:
        """
        Carga el historial completo de la BD a la caché. Llamar al iniciar el
        servidor para recuperar conversaciones previas tras un reinicio.
        """
        from sqlalchemy import select

        assert db_module.AsyncSessionLocal is not None
        async with db_module.AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationHistoryRow).order_by(
                    ConversationHistoryRow.message_index
                )
            )
            rows = result.scalars().all()

        self._cache = [
            {"role": r.role, "content": r.content, "index": r.message_index}
            for r in rows
        ]
        logger.info(
            "history: historial cargado desde BD (%d mensajes)", len(self._cache)
        )

    async def compact_if_needed(self) -> None:
        """
        Si el historial tiene >= CONVERSATION_COMPACTION_THRESHOLD mensajes,
        lanza una tarea asíncrona en background para compactar los mensajes más
        antiguos (todos excepto los últimos 5).

        La compactación NO bloquea la respuesta al usuario.
        """
        threshold = settings.CONVERSATION_COMPACTION_THRESHOLD

        if len(self._cache) >= threshold:
            asyncio.create_task(
                self._compact(),
                name="compact-history",
            )

    # ── Implementación interna ────────────────────────────────────────────────

    async def _compact(self) -> None:
        """
        Compacta los mensajes 0..(N-5) del historial en un resumen generado
        por Gemini, reemplazándolos por un único mensaje con is_compacted=True.

        Los últimos 5 mensajes se conservan intactos para mantener el contexto
        reciente de la conversación.
        """
        if len(self._cache) < 6:
            return  # nada que compactar

        keep = 5
        to_compact = self._cache[:-keep]
        to_keep = self._cache[-keep:]

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
            logger.exception("Error compactando historial global")
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
                        ConversationHistoryRow.message_index.in_(old_indices),
                    )
                )
                # Insertar el resumen compactado
                session.add(
                    ConversationHistoryRow(
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
        self._cache = [compacted_entry] + [
            {"role": m["role"], "content": m["content"], "index": i + 1}
            for i, m in enumerate(to_keep)
        ]
        logger.info(
            "history: compactados %d mensajes → 1 resumen + %d recientes",
            len(to_compact),
            keep,
        )
