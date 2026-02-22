"""
ZonesRepository — CRUD asíncrono sobre las tablas `zones` y `zone_paths`.

Incluye un algoritmo BFS en memoria para encontrar el camino entre dos zonas.

Uso:
    async with AsyncSessionLocal() as session:
        repo = ZonesRepository(session)
        zone = await repo.get_or_create("cocina", "kitchen")
        await repo.set_current_zone(zone.id)
        path = await repo.find_path("sala", "cocina")
"""

from collections import deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import ZonePathRow, ZoneRow
from models.entities import Zone, ZonePath


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_zone(row: ZoneRow) -> Zone:
    return Zone(
        id=row.id,
        name=row.name,
        category=row.category,
        description=row.description,
        known_since=row.known_since,
        accessible=row.accessible,
        current_robi_zone=row.current_robi_zone,
    )


def _row_to_path(row: ZonePathRow) -> ZonePath:
    return ZonePath(
        id=row.id,
        from_zone_id=row.from_zone_id,
        to_zone_id=row.to_zone_id,
        direction_hint=row.direction_hint,
        distance_cm=row.distance_cm,
    )


# ── Repositorio ───────────────────────────────────────────────────────────────


class ZonesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Zones CRUD ────────────────────────────────────────────────────────────

    async def create(
        self,
        name: str,
        category: str = "unknown",
        description: str = "",
        accessible: bool = True,
    ) -> Zone:
        """Inserta una nueva zona en el mapa mental."""
        row = ZoneRow(
            name=name,
            category=category,
            description=description,
            accessible=accessible,
            current_robi_zone=False,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_zone(row)

    async def get_by_id(self, zone_id: int) -> Zone | None:
        """Devuelve la zona por PK."""
        result = await self._session.execute(
            select(ZoneRow).where(ZoneRow.id == zone_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_zone(row) if row else None

    async def get_by_name(self, name: str) -> Zone | None:
        """Devuelve la zona por nombre (case-sensitive)."""
        result = await self._session.execute(
            select(ZoneRow).where(ZoneRow.name == name)
        )
        row = result.scalar_one_or_none()
        return _row_to_zone(row) if row else None

    async def get_or_create(
        self,
        name: str,
        category: str = "unknown",
        description: str = "",
    ) -> tuple[Zone, bool]:
        """
        Devuelve (zona, created).
        Si ya existe una zona con ese nombre la devuelve; si no, la crea.
        """
        zone = await self.get_by_name(name)
        if zone is None:
            zone = await self.create(name, category, description)
            return zone, True
        return zone, False

    async def update(
        self,
        zone_id: int,
        *,
        description: str | None = None,
        category: str | None = None,
        accessible: bool | None = None,
    ) -> Zone | None:
        """Actualiza campos opcionales de una zona. Devuelve None si no existe."""
        result = await self._session.execute(
            select(ZoneRow).where(ZoneRow.id == zone_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if description is not None:
            row.description = description
        if category is not None:
            row.category = category
        if accessible is not None:
            row.accessible = accessible
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_zone(row)

    async def list_all(self) -> list[Zone]:
        """Devuelve todas las zonas conocidas, ordenadas por known_since asc."""
        result = await self._session.execute(
            select(ZoneRow).order_by(ZoneRow.known_since.asc())
        )
        return [_row_to_zone(r) for r in result.scalars().all()]

    async def get_current_zone(self) -> Zone | None:
        """Devuelve la zona donde Robi está ahora (current_robi_zone=True)."""
        result = await self._session.execute(
            select(ZoneRow).where(ZoneRow.current_robi_zone.is_(True))
        )
        row = result.scalar_one_or_none()
        return _row_to_zone(row) if row else None

    async def set_current_zone(self, zone_id: int) -> Zone | None:
        """
        Marca `zone_id` como la zona actual de Robi y desmarca cualquier otra.
        Devuelve la zona activada o None si no existe.
        """
        # Desmarcar todas
        all_result = await self._session.execute(
            select(ZoneRow).where(ZoneRow.current_robi_zone.is_(True))
        )
        for row in all_result.scalars().all():
            row.current_robi_zone = False

        # Marcar la nueva
        target_result = await self._session.execute(
            select(ZoneRow).where(ZoneRow.id == zone_id)
        )
        target = target_result.scalar_one_or_none()
        if target is None:
            await self._session.flush()
            return None
        target.current_robi_zone = True
        await self._session.flush()
        await self._session.refresh(target)
        return _row_to_zone(target)

    # ── ZonePaths CRUD ────────────────────────────────────────────────────────

    async def add_path(
        self,
        from_zone_id: int,
        to_zone_id: int,
        direction_hint: str = "",
        distance_cm: int | None = None,
    ) -> ZonePath:
        """Agrega una arista dirigida entre dos zonas del grafo."""
        row = ZonePathRow(
            from_zone_id=from_zone_id,
            to_zone_id=to_zone_id,
            direction_hint=direction_hint,
            distance_cm=distance_cm,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_path(row)

    async def get_paths_from(self, zone_id: int) -> list[ZonePath]:
        """Devuelve todos los caminos que parten de `zone_id`."""
        result = await self._session.execute(
            select(ZonePathRow).where(ZonePathRow.from_zone_id == zone_id)
        )
        return [_row_to_path(r) for r in result.scalars().all()]

    async def get_paths_for_zone(self, zone_id: int) -> list[ZonePath]:
        """Devuelve todos los caminos que parten O llegan a `zone_id`."""
        result = await self._session.execute(
            select(ZonePathRow).where(
                (ZonePathRow.from_zone_id == zone_id)
                | (ZonePathRow.to_zone_id == zone_id)
            )
        )
        return [_row_to_path(r) for r in result.scalars().all()]

    # ── Navegación (BFS) ──────────────────────────────────────────────────────

    async def find_path(
        self,
        from_zone_name: str,
        to_zone_name: str,
    ) -> list[ZonePath]:
        """
        BFS en memoria sobre el grafo de zonas.
        Devuelve la secuencia de ZonePath que conecta `from_zone_name`
        con `to_zone_name`, o lista vacía si no hay camino.

        Trata el grafo como dirigido (las aristas en zone_paths son de A→B).
        """
        from_zone = await self.get_by_name(from_zone_name)
        to_zone = await self.get_by_name(to_zone_name)
        if from_zone is None or to_zone is None:
            return []
        if from_zone.id == to_zone.id:
            return []

        # Cargar todas las aristas en memoria (grafo pequeño — típico de una casa)
        all_paths_result = await self._session.execute(select(ZonePathRow))
        all_edges: list[ZonePath] = [
            _row_to_path(r) for r in all_paths_result.scalars().all()
        ]

        # Construir lista de adyacencia id→[(path, to_id)]
        adj: dict[int, list[tuple[ZonePath, int]]] = {}
        for edge in all_edges:
            adj.setdefault(edge.from_zone_id, []).append((edge, edge.to_zone_id))

        # BFS
        start: int = from_zone.id  # type: ignore[assignment]
        goal: int = to_zone.id  # type: ignore[assignment]
        queue: deque[tuple[int, list[ZonePath]]] = deque([(start, [])])
        visited: set[int] = {start}

        while queue:
            current_id, path_so_far = queue.popleft()
            for edge, neighbor_id in adj.get(current_id, []):
                if neighbor_id in visited:
                    continue
                new_path = path_so_far + [edge]
                if neighbor_id == goal:
                    return new_path
                visited.add(neighbor_id)
                queue.append((neighbor_id, new_path))

        return []  # sin camino encontrado
