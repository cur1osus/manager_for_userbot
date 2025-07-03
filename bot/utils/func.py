import dataclasses
import logging
from typing import Any, Final

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.formatting import Code
from telethon import TelegramClient  # type: ignore
from telethon.errors import SessionPasswordNeededError  # type: ignore

from bot.db.mysql.models import MonitoringChat


@dataclasses.dataclass
class Result:
    success: bool
    message: str | None


logger = logging.getLogger(__name__)


class Function:
    max_length_message: Final[int] = 4000

    @staticmethod
    async def set_general_message(state: FSMContext, message: Message) -> None:
        data_state = await state.get_data()
        message_id = data_state.get("message_id")
        await Function._delete_keyboard(message_id, message)
        await state.update_data(message_id=message.message_id)

    @staticmethod
    async def _delete_keyboard(message_id_to_delete: int | None, message: Message) -> None:
        if message_id_to_delete:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message_id_to_delete,
                    reply_markup=None,
                )
            except Exception as e:
                logger.exception(f"Ошибка при удалении клавиатуры: {e}")

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
            r = None
            if not await client.is_user_authorized():
                r = await client.send_code_request(phone)
                logger.info(f"Код подтверждения отправлен на номер {phone}.")
            await client.disconnect()
            return r.phone_code_hash if r else r
        except Exception as e:
            logger.info(f"Ошибка при отправке кода: {e}")
            return None

    @staticmethod
    async def collapse_repeated_data(data: list[str], data_to_compare: list[str]) -> list[str]:
        data_to_compare = list(set(data_to_compare))
        for i in data:
            if i in data_to_compare:
                data_to_compare.remove(i)
        return data_to_compare

    @staticmethod
    async def watch_data(data: list[str], sep: str, q_string_per_page: int, page: int) -> str:
        data_enumerate = list(enumerate(data))
        data_ = data_enumerate[(page - 1) * q_string_per_page : page * q_string_per_page]
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
    ) -> str:
        chats_enumerate = list(enumerate(chats))
        chats_ = chats_enumerate[(page - 1) * q_string_per_page : page * q_string_per_page]
        s = "".join(f"{ind + 1}) {i.id_chat} ({i.title or '🌀'}){sep}" for ind, i in chats_)
        if len(s) > Function.max_length_message:
            return await Function.watch_data_chats(
                chats,
                sep,
                q_string_per_page - 1,
                page,
            )
        return s

    @staticmethod
    async def watch_processed_users(
        processed_users: list[dict[str, Any]],
        sep: str,
        q_string_per_page: int,
        page: int,
        formatting: list[bool],
    ) -> str:
        processed_users = processed_users[(page - 1) * q_string_per_page : page * q_string_per_page]
        first_name, username, copy = formatting
        rows = []
        for i in processed_users:
            string = []
            for name, value in i.items():
                if name in ["id", "phone", "last_name"]:
                    continue
                if not username and name == "username":
                    continue
                if not first_name and name == "first_name":
                    continue
                if name == "username":
                    value = f"@{value}" if value else "@нет"
                else:
                    value = value or "нет значения"
                    value = value if copy else Code(value).as_html()
                string.append(value)
            string.reverse()
            rows.append(" - ".join(string))
        rows_str = "\n\n".join(rows)
        if len(rows_str) > Function.max_length_message:
            return await Function.watch_processed_users(processed_users, sep, q_string_per_page - 1, page, formatting)
        return Code(rows_str).as_html() if copy else rows_str

    @staticmethod
    def get_log(file_path: str, line_count: int = 20) -> list[str] | str:
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
