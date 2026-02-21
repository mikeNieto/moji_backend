"""
Router de memoria de usuarios.

Endpoints:
  POST  /api/users/{user_id}/memory   → guarda una nueva memoria
  GET   /api/users/{user_id}/memory   → lista las memorias del usuario
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_session
from middleware.error_handler import NotFoundError
from models.requests import MemorySaveRequest
from models.responses import MemoryItemResponse, MemoryListResponse, MemorySaveResponse
from repositories.memory import MemoryRepository
from repositories.users import UserRepository

router = APIRouter(prefix="/api/users", tags=["memory"])


def _parse_expires_at(expires_at_str: str | None) -> datetime | None:
    """Convierte un string ISO-8601 a datetime. Devuelve None si es None."""
    if expires_at_str is None:
        return None
    try:
        return datetime.fromisoformat(expires_at_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Formato de expires_at inválido: {expires_at_str!r}. Usa ISO-8601.",
        ) from exc


@router.post(
    "/{user_id}/memory",
    response_model=MemorySaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_memory(
    user_id: str,
    body: MemorySaveRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Guarda una nueva memoria para el usuario.

    Devuelve 404 si el usuario no existe.
    Devuelve 422 si el contenido es detectado como privado por el filtro de palabras clave.
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(user_id)
    if user is None:
        raise NotFoundError(f"Usuario '{user_id}' no encontrado")

    expires_at = _parse_expires_at(body.expires_at)

    mem_repo = MemoryRepository(session)
    saved = await mem_repo.save(
        user_id=user_id,
        memory_type=body.memory_type,
        content=body.content,
        importance=body.importance,
        expires_at=expires_at,
    )

    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "La memoria contiene información privada o sensible y no puede ser guardada."
            ),
        )

    return MemorySaveResponse(id=saved.id)  # type: ignore[arg-type]


@router.get("/{user_id}/memory", response_model=MemoryListResponse)
async def get_memory(user_id: str, session: AsyncSession = Depends(get_session)):
    """
    Devuelve todas las memorias activas del usuario ordenadas por importancia desc.

    Devuelve 404 si el usuario no existe.
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(user_id)
    if user is None:
        raise NotFoundError(f"Usuario '{user_id}' no encontrado")

    mem_repo = MemoryRepository(session)
    memories = await mem_repo.get_for_user(user_id)

    items = [
        MemoryItemResponse(
            id=m.id,  # type: ignore[arg-type]
            memory_type=m.memory_type,
            content=m.content,
            importance=m.importance,
            timestamp=m.timestamp.isoformat(),
            expires_at=m.expires_at.isoformat() if m.expires_at else None,
        )
        for m in memories
    ]
    return MemoryListResponse(user_id=user_id, memories=items, total=len(items))
