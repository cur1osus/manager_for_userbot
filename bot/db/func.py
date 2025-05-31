from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .sqlite.models import UserManager


async def _get_user_manager_model(
    sessionmaker: async_sessionmaker, id_user: int, username: str
) -> UserManager | None:
    async with sessionmaker() as session:
        user = await session.scalar(
            select(UserManager).where(UserManager.id_user == id_user)
        )
        return user
