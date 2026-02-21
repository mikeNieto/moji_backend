"""
Router de registro facial.

Endpoints:
  POST /api/face/register   → registra un usuario con embedding facial desde Android
"""

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_session
from models.requests import FaceRegisterRequest
from models.responses import FaceRegisterResponse
from repositories.users import UserRepository

router = APIRouter(prefix="/api/face", tags=["face"])


@router.post(
    "/register",
    response_model=FaceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_face(
    body: FaceRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Registra un nuevo usuario con su embedding facial (procesado en Android).

    - `user_id`: identificador único de negocio (p.ej. "user_juan_123")
    - `name`: nombre para mostrar
    - `embedding_b64`: vector FaceNet 128D serializado y codificado en base64

    Devuelve 409 si el `user_id` ya existe.
    Devuelve 400 si `embedding_b64` no es base64 válido.
    """
    # Decodificar embedding
    try:
        embedding_bytes = base64.b64decode(body.embedding_b64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="embedding_b64 no es un string base64 válido.",
        ) from exc

    repo = UserRepository(session)

    # Verificar si ya existe
    existing = await repo.get_by_user_id(body.user_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El usuario '{body.user_id}' ya está registrado.",
        )

    try:
        user = await repo.create(
            user_id=body.user_id,
            name=body.name,
            face_embedding=embedding_bytes,
        )
    except IntegrityError as exc:
        # carrera de condición: otro request creó el mismo user_id justo antes
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El usuario '{body.user_id}' ya está registrado.",
        ) from exc

    return FaceRegisterResponse(user_id=user.user_id, name=user.name)
