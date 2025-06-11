from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .mysql.models import UserManager


async def _get_user_manager_model(
    sessionmaker: async_sessionmaker, id_user: int
) -> UserManager | None:
    async with sessionmaker() as session:
        return await session.scalar(
            select(UserManager).where(UserManager.id_user == id_user)
        )
