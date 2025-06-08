import dataclasses
import logging

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import TelegramClient  # type: ignore
from telethon.errors import SessionPasswordNeededError  # type: ignore

from bot.db.sqlite.models import Base, Bot


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
                else:
                    await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            logger.info("Авторизация прошла успешно!")
            logger.info((await client.get_me()).first_name)
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

    @staticmethod
    async def add_data_to_db(
        sessionmaker: async_sessionmaker,
        data_to_add: list[str],
        model_db: type[Base],
        name_value: str,
    ):
        _ = await Function.get_data_from_db(sessionmaker, model_db, name_value)
        data_to_add = await Function.collapse_repeated_data(_, data_to_add)
        async with sessionmaker() as session:
            for data in data_to_add:
                _ = {name_value: data}
                await session.execute(insert(model_db).values(**_))
            await session.commit()

    @staticmethod
    async def get_data_from_db(
        sessionmaker: async_sessionmaker, model_db: type[Base], name_value: str
    ) -> list[str]:
        async with sessionmaker() as session:
            return [
                getattr(i, name_value)
                for i in (await session.scalars(select(model_db))).all()
            ]

    @staticmethod
    async def collapse_repeated_data(
        data: list[str], data_to_compare: list[str]
    ) -> list[str]:
        data_to_compare = list(set(data_to_compare))
        for i in data:
            if i in data_to_compare:
                data_to_compare.remove(i)
        return data_to_compare

    @staticmethod
    async def watch_data(data: list[str], sep: str):
        s = "".join(f"{ind + 1}) {i}{sep}" for ind, i in enumerate(data))
        if len(s) > 4096:
            s = s[4096:]
        return f"... {s}"
