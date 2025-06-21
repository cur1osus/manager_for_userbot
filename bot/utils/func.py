import dataclasses
import logging
from typing import Final

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import TelegramClient  # type: ignore
from aiogram.utils.formatting import Code, TextLink
from telethon.errors import SessionPasswordNeededError  # type: ignore

from bot.db.mysql.models import Base, Bot, MonitoringChat


@dataclasses.dataclass
class Result:
    success: bool
    message: str | None


logger = logging.getLogger(__name__)


class Function:
    max_length_message: Final[int] = 4000

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
        **kwargs,
    ):
        if kwargs:
            where: list = []
            for i in kwargs:
                where.extend((i, kwargs[i]))
            _ = await Function.get_data_from_db(
                sessionmaker, model_db, name_value, where
            )
        else:
            _ = await Function.get_data_from_db(sessionmaker, model_db, name_value)

        data_to_add = await Function.collapse_repeated_data(_, data_to_add)
        async with sessionmaker() as session:
            for data in data_to_add:
                _ = {name_value: data} | kwargs
                await session.execute(insert(model_db).values(**_))
            await session.commit()

    @staticmethod
    async def get_data_from_db(
        sessionmaker: async_sessionmaker,
        model_db: type[Base],
        name_value: str | None = None,
        where: list | None = None,
    ) -> list[str]:
        async with sessionmaker() as session:
            if name_value:
                return (
                    [
                        getattr(i, name_value)
                        for i in (
                            await session.scalars(
                                select(model_db)
                                .where(getattr(model_db, where[0]) == where[1])
                                .order_by(model_db.id)
                            )
                        ).all()
                    ]
                    if where
                    else [
                        getattr(i, name_value)
                        for i in (await session.scalars(select(model_db))).all()
                    ]
                )
            if where:
                return list(
                    (
                        await session.scalars(
                            select(model_db)
                            .where(getattr(model_db, where[0]) == where[1])
                            .order_by(model_db.id)
                        )
                    ).all()
                )
            else:
                return list((await session.scalars(select(model_db))).all())

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
    async def watch_data(
        data: list[str], sep: str, q_string_per_page: int, page: int
    ) -> str:
        data_enumerate = list(enumerate(data))
        data_ = data_enumerate[
            (page - 1) * q_string_per_page : page * q_string_per_page
        ]
        s = "".join(f"{ind + 1}) {i}{sep}" for ind, i in data_)
        if len(s) > Function.max_length_message:
            return await Function.watch_data(data, sep, q_string_per_page - 1, page)
        return s

    @staticmethod
    async def count_page(len_data: int, q_string_per_page: int) -> int:
        remains = len_data % q_string_per_page
        return len_data // q_string_per_page + (1 if remains else 0)

    @staticmethod
    async def watch_data_chats(
        chats: list[MonitoringChat],
        sep: str,
        q_string_per_page: int,
        page: int,
    ):
        chats_enumerate = list(enumerate(chats))
        chats_ = chats_enumerate[
            (page - 1) * q_string_per_page : page * q_string_per_page
        ]
        s = "".join(
            f"{ind + 1}) {i.id_chat} ({i.title or 'название загружается...'}){sep}"
            for ind, i in chats_
        )
        if len(s) > Function.max_length_message:
            return await Function.watch_data_chats(
                chats,
                sep,
                q_string_per_page - 1,
                page,
            )
        return s

    @staticmethod
    async def watch_processed_users(processed_users: list[dict], sep: str):
        s = ""
        for i in processed_users:
            del i["id"]
            del i["last_name"]
            for name, value in i.items():
                if name == "username":
                    value = f"@{value}" if value else "нет"
                # elif name == "id":
                #     value = TextLink(value, url=f"tg://user?id={value}").as_html()
                #     continue
                elif name == "phone":
                    value = f"+{value}" if value else "нет"
                    value = Code(value).as_html()
                else:
                    value = Code(value).as_html() if value else "нет"
                s += f"{name}: {value}{sep}"
            s += "\n\n"
        if len(s) > Function.max_length_message:
            s = s[Function.max_length_message :]
            s = f"... {s}"
        return s

    @staticmethod
    def get_log(file_path, line_count=20) -> list[str] | str:
        """
        Получить последние строки из файла.

        :param file_path: Путь к файлу логов.
        :param line_count: Количество строк, которые нужно получить (по умолчанию 20).
        :return: Список последних строк.
        """
        try:
            with open(file_path, "rb") as file:
                file.seek(0, 2)  # Переходим в конец файла
                buffer = bytearray()
                end_of_file = file.tell()

                while len(buffer.splitlines()) <= line_count and file.tell() > 0:
                    # Смещаемся назад блоками по 1024 байта
                    step = min(1024, file.tell())
                    file.seek(-step, 1)
                    buffer = file.read(step) + buffer  # type: ignore
                    file.seek(-step, 1)

                lines = buffer.splitlines()[-line_count:]
                return [line.decode("utf-8") for line in lines]
        except FileNotFoundError:
            return "Файл не найден"
        except Exception as e:
            return f"Ошибка при чтении файла: {e}"
