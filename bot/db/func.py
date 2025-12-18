from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import UserManager


async def _get_user_manager_model(
    session: AsyncSession, id_user: int
) -> UserManager | None:
    return await session.scalar(
        select(UserManager).where(UserManager.id_user == id_user)
    )
