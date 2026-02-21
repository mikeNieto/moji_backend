"""
Dependencias FastAPI compartidas por todos los routers.

Uso:
    from dependencies import get_session
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get(...)
    async def endpoint(session: AsyncSession = Depends(get_session)):
        ...
"""

from collections.abc import AsyncGenerator

import db as db_module
from sqlalchemy.ext.asyncio import AsyncSession


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
