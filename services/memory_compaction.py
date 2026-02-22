"""
services/memory_compaction.py — Compactación asíncrona de memorias.

Se lanza como asyncio.create_task() después de cada interacción para mantener
el número de memorias manejable sin perder información valiosa.

Proceso:
  1. Recuperar todas las memorias activas de una persona / generales.
  2. Agrupar por memory_type.
  3. Por cada grupo con > COMPACTION_THRESHOLD entradas, pedirle a Gemini que
     las fusione en una sola memoria más rica.
  4. Sustituir las memorias antiguas por el resumen compactado en la BD
     (via MemoryRepository.replace_with_compacted).

Uso:
    import asyncio
    from services.memory_compaction import compact_memories_async

    # Tras una interacción con Juan:
    asyncio.create_task(compact_memories_async(person_id="persona_juan_01"))

    # Para memorias generales de Robi:
    asyncio.create_task(compact_memories_async())
"""

import logging
from collections import defaultdict

import db as db_module
from models.entities import Memory
from repositories.memory import MemoryRepository
from services.gemini import get_model

logger = logging.getLogger(__name__)

# Número mínimo de memorias del mismo tipo para disparar compactación
COMPACTION_THRESHOLD: int = 8

# Importancia asignada a la memoria compactada resultante
COMPACTED_IMPORTANCE: int = 7


# ── Prompt de compactación ────────────────────────────────────────────────────


def _build_compaction_prompt(
    memory_type: str,
    memories: list[Memory],
    person_id: str | None,
) -> str:
    """Construye el prompt que le pedirá a Gemini que fusione las memorias."""
    subject = f"sobre {person_id}" if person_id else "generales de Robi"
    lines = "\n".join(f"  - {m.content} (importancia {m.importance})" for m in memories)

    return (
        f"Eres Robi, un robot doméstico amigable. Tienes {len(memories)} recuerdos "
        f"de tipo '{memory_type}' {subject}. Fusiónanos en un único recuerdo más rico "
        f"y conciso que preserve toda la información relevante. "
        f"Usa prosa natural, máximo 3 frases. No pierdas detalles importantes.\n\n"
        f"Recuerdos a fusionar:\n{lines}\n\n"
        f"Recuerdo fusionado (solo el texto, sin prefijos ni etiquetas):"
    )


# ── Compactación de un grupo de memorias ─────────────────────────────────────


async def _compact_group(
    repo: MemoryRepository,
    memory_type: str,
    memories: list[Memory],
    person_id: str | None,
) -> None:
    """
    Pide a Gemini que fusione `memories` y las reemplaza en la BD.
    Si Gemini falla, se registra el error y se mantienen las memorias originales.
    """
    prompt = _build_compaction_prompt(memory_type, memories, person_id)

    try:
        model = get_model()
        result = await model.ainvoke(prompt)
        raw = result.content if hasattr(result, "content") else result
        if isinstance(raw, list):
            raw = " ".join(item if isinstance(item, str) else str(item) for item in raw)
        compacted_text = str(raw).strip()

        if not compacted_text:
            logger.warning(
                "[COMPACTION] Gemini devolvió texto vacío para type=%s person=%s",
                memory_type,
                person_id,
            )
            return

    except Exception:
        logger.exception(
            "[COMPACTION] Error llamando a Gemini para type=%s person=%s",
            memory_type,
            person_id,
        )
        return

    old_ids = [m.id for m in memories if m.id is not None]
    await repo.replace_with_compacted(
        old_ids=old_ids,
        memory_type=memory_type,
        content=compacted_text,
        person_id=person_id,
        importance=COMPACTED_IMPORTANCE,
    )
    logger.info(
        "[COMPACTION] %d memorias type=%s person=%s → compactadas en 1",
        len(old_ids),
        memory_type,
        person_id,
    )


# ── Punto de entrada público ──────────────────────────────────────────────────


async def compact_memories_async(person_id: str | None = None) -> None:
    """
    Compacta las memorias de una persona concreta o las memorias generales de Robi.

    - Si `person_id` es None, compacta las memorias generales (person_id IS NULL).
    - Por cada tipo de memoria con más de COMPACTION_THRESHOLD entradas activas,
      fusiona todas menos las 2 más recientes (para no perder contexto inmediato).
    - Las memorias de zona (zone_info) se compactan por separado — son el mapa mental.
    - Se lanza como tarea asíncrona en background; los errores se loggean sin propagar.

    Llamar con asyncio.create_task() para no bloquear la respuesta al usuario:
        asyncio.create_task(compact_memories_async(person_id="persona_juan_01"))
    """
    assert db_module.AsyncSessionLocal is not None, "DB no inicializada"

    async with db_module.AsyncSessionLocal() as session:
        repo = MemoryRepository(session)

        # Obtener memorias activas según el sujeto
        if person_id is not None:
            memories = await repo.get_for_person(person_id, include_expired=False)
        else:
            memories = await repo.get_general(include_expired=False)

        if not memories:
            return

        # Agrupar por tipo
        by_type: dict[str, list[Memory]] = defaultdict(list)
        for mem in memories:
            by_type[mem.memory_type].append(mem)

        # Compactar grupos que superen el umbral
        for memory_type, group in by_type.items():
            if len(group) <= COMPACTION_THRESHOLD:
                continue

            # Ordenar por importancia desc, timestamp desc
            group.sort(key=lambda m: (-m.importance, -m.timestamp.timestamp()))

            # Conservar las 2 más recientes/importantes fuera de la compactación
            to_keep = group[:2]
            to_compact = group[2:]

            if len(to_compact) < 2:
                # No tiene sentido compactar un solo recuerdo
                continue

            logger.info(
                "[COMPACTION] Iniciando compactación: type=%s person=%s count=%d",
                memory_type,
                person_id,
                len(to_compact),
            )
            await _compact_group(repo, memory_type, to_compact, person_id)
            _ = to_keep  # las más recientes permanecen intactas

        await session.commit()
