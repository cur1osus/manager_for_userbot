import dataclasses
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import TelegramClient  # type: ignore
from telethon.errors import SessionPasswordNeededError  # type: ignore

from bot.db.sqlite.models import Bot


@dataclasses.dataclass
class Result:
    success: bool
    message: str | None


logger = logging.getLogger(__name__)


class Function:
    @staticmethod
    async def get_available_bots(sessionmaker: async_sessionmaker) -> list[Bot]:
        async with sessionmaker() as session:
            return (await session.scalars(select(Bot))).all()

    @staticmethod
    async def create_telethon_session(
        phone: str,
        code: str | int,
        api_id: int,
        api_hash: str,
        phone_code_hash: str,
        password: str | None,
        path: str,
    ) -> Result:
        client = TelegramClient(path, api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                if password:
                    await client.sign_in(password=password)
                elif not password:
                    await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            logger.info("Авторизация прошла успешно!")
            await client.disconnect()
            return Result(success=True, message=None)
        except SessionPasswordNeededError:
            logger.info("Необходим пароль для двухфакторной аутентификации.")
            return Result(success=False, message="password")
        except Exception as e:
            logger.info(f"Ошибка: {e}")
            return Result(success=False, message="error")

    @staticmethod
    async def send_code_via_telethon(
        phone: str,
        api_id: int,
        api_hash: str,
        path: str,
    ) -> str | None:
        """Отправка кода на номер телефона через Telethon"""
        client = TelegramClient(path, api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                r = await client.send_code_request(phone)
                logger.info(f"Код подтверждения отправлен на номер {phone}.")
            await client.disconnect()
            return r.phone_code_hash
        except Exception as e:
            logger.info(f"Ошибка при отправке кода: {e}")
            return None
