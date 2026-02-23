"""
MemoryRepository — CRUD asíncrono sobre la tabla `memories`.

v2.0 — Moji Amigo Familiar
  - `user_id` reemplazado por `person_id` nullable (hay memorias generales)
  - `memory_type` expandido: experience | zone_info | person_fact | general
  - Nuevo campo `zone_id` nullable para memorias contextualizadas en lugar
  - Nuevo método `get_moji_context()` para construir el prompt del agente

Uso:
    async with AsyncSessionLocal() as session:
        repo = MemoryRepository(session)
        mem = await repo.save(
            memory_type="person_fact",
            content="A Juan le gusta el café",
            person_id="persona_juan_01",
            importance=7,
        )
        ctx = await repo.get_moji_context()
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import MemoryRow
from models.entities import Memory


# ── Filtro de privacidad (basado en palabras clave) ───────────────────────────

_PRIVACY_KEYWORDS: frozenset[str] = frozenset(
    [
        # Datos personales sensibles
        "contraseña",
        "password",
        "clave",
        "pin",
        "tarjeta",
        "crédito",
        "débito",
        "cuenta bancaria",
        "dni",
        "pasaporte",
        "número de seguridad",
        "seguridad social",
        "dirección",
        "domicilio",
        # Salud
        "medicamento",
        "diagnóstico",
        "enfermedad",
        "tratamiento",
        # En inglés
        "address",
        "passport",
        "credit card",
        "debit card",
        "bank account",
        "social security",
        "medication",
        "diagnosis",
    ]
)


def is_private(content: str) -> bool:
    """
    Devuelve True si el contenido contiene alguna palabra clave sensible.
    Comparación case-insensitive.
    """
    lower = content.lower()
    return any(kw in lower for kw in _PRIVACY_KEYWORDS)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_entity(row: MemoryRow) -> Memory:
    return Memory(
        id=row.id,
        person_id=row.person_id,
        zone_id=row.zone_id,
        memory_type=row.memory_type,
        content=row.content,
        importance=row.importance,
        timestamp=row.timestamp,
        expires_at=row.expires_at,
    )


# ── Repositorio ───────────────────────────────────────────────────────────────


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        memory_type: str,
        content: str,
        *,
        person_id: str | None = None,
        zone_id: int | None = None,
        importance: int = 5,
        expires_at: datetime | None = None,
    ) -> Memory | None:
        """
        Persiste una nueva memoria.

        - `person_id` nullable: None para memorias generales de Moji.
        - `zone_id` nullable: contexto espacial opcional.
        - `memory_type` debe ser uno de: experience | zone_info | person_fact | general.
        - Devuelve None si el contenido es detectado como privado.
        """
        if is_private(content):
            return None

        row = MemoryRow(
            person_id=person_id,
            zone_id=zone_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_entity(row)

    async def get_for_person(
        self,
        person_id: str,
        *,
        memory_type: str | None = None,
        include_expired: bool = False,
        limit: int | None = None,
    ) -> list[Memory]:
        """
        Devuelve memorias ligadas a una persona, ordenadas por importancia desc
        y timestamp desc. Filtro opcional por tipo.
        """
        stmt = select(MemoryRow).where(MemoryRow.person_id == person_id)

        if memory_type is not None:
            stmt = stmt.where(MemoryRow.memory_type == memory_type)

        if not include_expired:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                (MemoryRow.expires_at.is_(None)) | (MemoryRow.expires_at > now)
            )

        stmt = stmt.order_by(MemoryRow.importance.desc(), MemoryRow.timestamp.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return [_row_to_entity(r) for r in result.scalars().all()]

    async def get_general(
        self,
        *,
        memory_type: str | None = None,
        include_expired: bool = False,
        limit: int | None = None,
    ) -> list[Memory]:
        """
        Devuelve memorias generales de Moji (person_id IS NULL).
        Filtro opcional por tipo.
        """
        stmt = select(MemoryRow).where(MemoryRow.person_id.is_(None))

        if memory_type is not None:
            stmt = stmt.where(MemoryRow.memory_type == memory_type)

        if not include_expired:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                (MemoryRow.expires_at.is_(None)) | (MemoryRow.expires_at > now)
            )

        stmt = stmt.order_by(MemoryRow.importance.desc(), MemoryRow.timestamp.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return [_row_to_entity(r) for r in result.scalars().all()]

    async def get_recent_important(
        self,
        person_id: str | None = None,
        *,
        min_importance: int = 5,
        limit: int = 5,
    ) -> list[Memory]:
        """
        Devuelve las memorias más importantes, opcionalmente de una persona concreta.
        Si `person_id` es None devuelve las memorias generales más importantes.
        """
        now = datetime.now(timezone.utc)
        if person_id is not None:
            person_filter = MemoryRow.person_id == person_id
        else:
            person_filter = MemoryRow.person_id.is_(None)

        stmt = (
            select(MemoryRow)
            .where(person_filter)
            .where(MemoryRow.importance >= min_importance)
            .where((MemoryRow.expires_at.is_(None)) | (MemoryRow.expires_at > now))
            .order_by(MemoryRow.timestamp.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_row_to_entity(r) for r in result.scalars().all()]

    async def get_moji_context(
        self,
        *,
        person_id: str | None = None,
        max_general: int = 10,
        max_person: int = 8,
        max_zone_info: int = 5,
    ) -> dict[str, list[Memory]]:
        """
        Recupera el contexto completo que se inyecta en el prompt del agente:

        Claves del dict devuelto:
          "general"      — memorias generales de Moji (experience + general)
          "person"       — memorias ligadas a `person_id` (si se provee)
          "zone_info"    — memorias de tipo zone_info (mapa mental resumido)

        Ordena por importancia desc dentro de cada grupo.
        """
        now = datetime.now(timezone.utc)
        active_filter = (MemoryRow.expires_at.is_(None)) | (MemoryRow.expires_at > now)

        # Memorias generales (experience + general, sin persona)
        general_stmt = (
            select(MemoryRow)
            .where(MemoryRow.person_id.is_(None))
            .where(MemoryRow.memory_type.in_(["experience", "general"]))
            .where(active_filter)
            .order_by(MemoryRow.importance.desc(), MemoryRow.timestamp.desc())
            .limit(max_general)
        )
        general_result = await self._session.execute(general_stmt)
        general_memories = [_row_to_entity(r) for r in general_result.scalars().all()]

        # Memorias de zona (mapa mental)
        zone_stmt = (
            select(MemoryRow)
            .where(MemoryRow.memory_type == "zone_info")
            .where(active_filter)
            .order_by(MemoryRow.importance.desc(), MemoryRow.timestamp.desc())
            .limit(max_zone_info)
        )
        zone_result = await self._session.execute(zone_stmt)
        zone_memories = [_row_to_entity(r) for r in zone_result.scalars().all()]

        # Memorias de la persona actual
        person_memories: list[Memory] = []
        if person_id is not None:
            person_stmt = (
                select(MemoryRow)
                .where(MemoryRow.person_id == person_id)
                .where(active_filter)
                .order_by(MemoryRow.importance.desc(), MemoryRow.timestamp.desc())
                .limit(max_person)
            )
            person_result = await self._session.execute(person_stmt)
            person_memories = [_row_to_entity(r) for r in person_result.scalars().all()]

        return {
            "general": general_memories,
            "person": person_memories,
            "zone_info": zone_memories,
        }

    async def delete(self, memory_id: int) -> bool:
        """Elimina una memoria por su PK. Devuelve True si existía."""
        result = await self._session.execute(
            select(MemoryRow).where(MemoryRow.id == memory_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def delete_for_person(self, person_id: str) -> int:
        """Elimina todas las memorias de una persona. Devuelve el número de filas borradas."""
        result = await self._session.execute(
            delete(MemoryRow)
            .where(MemoryRow.person_id == person_id)
            .returning(MemoryRow.id)
        )
        return len(result.fetchall())

    async def replace_with_compacted(
        self,
        old_ids: list[int],
        memory_type: str,
        content: str,
        person_id: str | None = None,
        zone_id: int | None = None,
        importance: int = 7,
    ) -> Memory | None:
        """
        Sustituye un conjunto de memorias antiguas por una sola memoria compactada.
        Usado por services/memory_compaction.py.
        Devuelve la nueva memoria, o None si el contenido es privado.
        """
        # Borrar las antiguas
        if old_ids:
            await self._session.execute(
                delete(MemoryRow).where(MemoryRow.id.in_(old_ids))
            )

        return await self.save(
            memory_type=memory_type,
            content=content,
            person_id=person_id,
            zone_id=zone_id,
            importance=importance,
        )
