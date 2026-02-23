"""
routers/restore.py — Endpoint de restauración del estado de Moji v2.0.

GET /api/restore
    Devuelve el estado completo para que la app Android re-sincronice tras
    una desconexión: personas conocidas, zonas + paths, memorias generales.

No requiere cuerpo de request. La autenticación se delega al APIKeyMiddleware.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_session
from models.responses import (
    RestoreMemoryResponse,
    RestorePersonResponse,
    RestoreResponse,
)
from repositories.memory import MemoryRepository
from repositories.people import PeopleRepository

router = APIRouter(prefix="/api", tags=["restore"])


@router.get("/restore", response_model=RestoreResponse)
async def restore(session: AsyncSession = Depends(get_session)) -> RestoreResponse:
    """
    Devuelve el estado completo de Moji para re-sincronización del cliente Android.

    - **people**: todas las personas conocidas con embeddings
    - **general_memories**: memorias generales (sin persona asociada)
    """
    people_repo = PeopleRepository(session)
    memory_repo = MemoryRepository(session)

    # ── Personas ──────────────────────────────────────────────────────────────
    all_people = await people_repo.list_all()
    all_embeddings = await people_repo.get_all_embeddings()

    # Index embeddings by person_id for fast lookup
    import base64
    from collections import defaultdict

    embeddings_by_person: dict[str, list[str]] = defaultdict(list)
    for emb in all_embeddings:
        embeddings_by_person[emb.person_id].append(
            base64.b64encode(emb.embedding).decode()
        )

    people_out = [
        RestorePersonResponse(
            person_id=p.person_id,
            name=p.name,
            first_seen=p.first_seen,
            last_seen=p.last_seen,
            interaction_count=p.interaction_count,
            notes=p.notes,
            face_embeddings=embeddings_by_person.get(p.person_id, []),
        )
        for p in all_people
    ]

    # ── Memorias generales ────────────────────────────────────────────────────
    general_mems = await memory_repo.get_general(include_expired=False, limit=50)
    memories_out = [
        RestoreMemoryResponse(
            id=m.id,  # type: ignore[arg-type]
            memory_type=m.memory_type,
            content=m.content,
            importance=m.importance,
            created_at=m.timestamp,
            person_id=m.person_id,
        )
        for m in general_mems
    ]

    return RestoreResponse(
        people=people_out,
        general_memories=memories_out,
    )
