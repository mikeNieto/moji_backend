"""
Dependencias FastAPI compartidas por todos los routers v2.0.

Uso:
"""

from collections.abc import AsyncGenerator

import db as db_module
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.memory import MemoryRepository
from repositories.people import PeopleRepository


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Proporciona una sesión async con transacción automática.
    El commit se realiza al finalizar el request sin excepción;
    el rollback es automático si ocurre una excepción.
    """
    assert db_module.AsyncSessionLocal is not None, (
        "init_db() debe ejecutarse antes del primer request"
    )
    async with db_module.AsyncSessionLocal() as session:
        async with session.begin():
            yield session


async def get_people_repository(
    session: AsyncSession = Depends(get_session),
) -> PeopleRepository:
    """Inyecta un PeopleRepository con la sesión del request."""
    return PeopleRepository(session)


async def get_memory_repository(
    session: AsyncSession = Depends(get_session),
) -> MemoryRepository:
    """Inyecta un MemoryRepository con la sesión del request."""
    return MemoryRepository(session)
