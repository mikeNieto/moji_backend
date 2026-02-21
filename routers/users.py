"""
Router de usuarios.

Endpoints:
  GET    /api/users                      → lista todos los usuarios
  GET    /api/users/{user_id}            → detalle de un usuario
  DELETE /api/users/{user_id}/memory     → elimina todas las memorias del usuario
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_session
from middleware.error_handler import NotFoundError
from models.responses import MemoryDeleteResponse, UserListResponse, UserResponse
from repositories.memory import MemoryRepository
from repositories.users import UserRepository

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_to_response(user) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        name=user.name,
        created_at=user.created_at.isoformat(),
        last_seen=user.last_seen.isoformat(),
        has_face_embedding=user.face_embedding is not None,
    )


@router.get("", response_model=UserListResponse)
async def list_users(session: AsyncSession = Depends(get_session)):
    """Devuelve todos los usuarios ordenados por last_seen desc."""
    repo = UserRepository(session)
    users = await repo.list_all()
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=len(users),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, session: AsyncSession = Depends(get_session)):
    """Devuelve el detalle de un usuario por su user_id de negocio."""
    repo = UserRepository(session)
    user = await repo.get_by_user_id(user_id)
    if user is None:
        raise NotFoundError(f"Usuario '{user_id}' no encontrado")
    return _user_to_response(user)


@router.delete("/{user_id}/memory", response_model=MemoryDeleteResponse)
async def delete_user_memory(
    user_id: str, session: AsyncSession = Depends(get_session)
):
    """Elimina todas las memorias del usuario. Devuelve el número de registros borrados."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(user_id)
    if user is None:
        raise NotFoundError(f"Usuario '{user_id}' no encontrado")

    mem_repo = MemoryRepository(session)
    deleted = await mem_repo.delete_for_user(user_id)
    return MemoryDeleteResponse(deleted=deleted)
