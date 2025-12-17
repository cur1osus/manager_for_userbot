from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Awaitable, Callable, Final

import psutil  # type: ignore
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.formatting import Code
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient  # type: ignore
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.errors.rpcerrorlist import FloodWaitError

from bot.db.mysql.models import MonitoringChat, UserAnalyzed
from bot.settings import se

logger = logging.getLogger(__name__)

PID_SUFFIX: Final[str] = ".pid"
SESSION_SUFFIX: Final[str] = ".session"
PID_FILE_WAIT_SECONDS: Final[float] = 1.0


@dataclasses.dataclass
class Result:
    success: bool
    message: str | None


def _pid_file(phone: str) -> Path:
    return Path(se.path_to_folder) / f"{phone}{PID_SUFFIX}"


def _read_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text().strip())
    except FileNotFoundError:
        logger.info("PID-файл не найден: %s", pid_path)
    except (OSError, ValueError) as exc:
        logger.warning("Не удалось прочитать PID-файл %s: %s", pid_path, exc)
    return None


class Function:
    max_length_message: Final[int] = 4000

    @staticmethod
    async def get_closer_data_users(
        session: AsyncSession,
        bot_id: int,
        limit: int = 30,
        last_user_id: int | None = None,
    ) -> list[UserAnalyzed]:
        conditions = [
            UserAnalyzed.accepted.is_(True),
            UserAnalyzed.sended.is_(False),
            UserAnalyzed.bot_id == bot_id,
        ]
        if last_user_id is not None:
            conditions.append(UserAnalyzed.id > last_user_id)

        query = select(UserAnalyzed).where(and_(*conditions)).order_by(
            UserAnalyzed.id.asc()
        ).limit(limit)
        users = await session.scalars(query)

        return list(users.all())

    @staticmethod
    async def set_general_message(state: FSMContext, message: Message) -> None:
        data_state = await state.get_data()
        message_id = data_state.get("message_id")
        await Function._delete_keyboard(message_id, message)
        await state.update_data(message_id=message.message_id)

    @staticmethod
    async def state_clear(state: FSMContext) -> None:
        new_data = {}
        data_state = await state.get_data()
        for key, value in data_state.items():
            if key.startswith("rmsg_"):
                new_data[key] = value
            elif key == "message_id":
                new_data[key] = value
        await state.clear()
        await state.set_data(new_data)

    @staticmethod
    async def _delete_keyboard(
        message_id_to_delete: int | None, message: Message
    ) -> None:
        if message_id_to_delete:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message_id_to_delete,
                    reply_markup=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Не удалось удалить клавиатуру: %s", exc)

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
    ) -> str:
        chats_enumerate = list(enumerate(chats))
        chats_ = chats_enumerate[
            (page - 1) * q_string_per_page : page * q_string_per_page
        ]
        s = "".join(
            f"{ind + 1}) {i.chat_id} ({i.title or '🌀'}){sep}" for ind, i in chats_
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
    async def watch_processed_users(
        processed_users: list[dict[str, Any]],
        sep: str,
        q_string_per_page: int,
        page: int,
        formatting: list[bool],
    ) -> str:
        processed_users = processed_users[
            (page - 1) * q_string_per_page : page * q_string_per_page
        ]
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
            return await Function.watch_processed_users(
                processed_users, sep, q_string_per_page - 1, page, formatting
            )
        return Code(rows_str).as_html() if copy else rows_str

    class Manager:
        @staticmethod
        async def start_bot(
            phone: str, path_session: str, api_id: int, api_hash: str
        ) -> int:
            script_path = Path(se.script_path)
            if not script_path.exists():
                logger.error("Bash script not found: %s", script_path)
                return -1

            await asyncio.create_subprocess_exec(
                str(script_path),
                path_session,
                str(api_id),
                api_hash,
                phone,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setpgrp,
                start_new_session=True,
            )

            await asyncio.sleep(PID_FILE_WAIT_SECONDS)

            path_pid = _pid_file(phone)
            pid = _read_pid(path_pid)
            if pid:
                logger.info("Bot started with PID: %s", pid)
                return pid

            logger.error("PID file not created for %s", phone)
            return -1

        @staticmethod
        async def bot_run(phone: str) -> bool:
            pid = _read_pid(_pid_file(phone))
            return bool(pid and psutil.pid_exists(pid))

        @staticmethod
        async def stop_bot(phone: str, delete_session: bool = False) -> None:
            pid_file = _pid_file(phone)
            pid = _read_pid(pid_file)
            if pid is None:
                logger.info("PID-файл не найден для %s", phone)
                return

            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                logger.info("Отправлен сигнал завершения процессу с PID: %s", pid)
            except ProcessLookupError:
                logger.info("Процесс не найден: %s", pid)
            except PermissionError:
                logger.info("Нет прав на завершение процесса: %s", pid)

            files = [pid_file.name]
            if delete_session:
                files.append(f"{phone}{SESSION_SUFFIX}")
            await Function.Manager.delete_files_by_name(se.path_to_folder, files)

        @staticmethod
        async def delete_files_by_name(folder_path: str, filenames: list[str]) -> None:
            folder = Path(folder_path)
            if not folder.exists():
                logger.info("Папка %s не существует.", folder)
                return

            targets = set(filenames)
            for file_path in folder.iterdir():
                if file_path.is_file() and file_path.name in targets:
                    try:
                        file_path.unlink()
                        logger.info("Удален файл: %s", file_path)
                    except Exception as exc:  # noqa: BLE001
                        logger.info("Не удалось удалить %s: %s", file_path, exc)

    class Telethon:
        @staticmethod
        def _is_valid_phone(phone: str) -> bool:
            return bool(phone) and phone.lstrip("+").isdigit()

        @staticmethod
        def _is_valid_api_id(api_id: int) -> bool:
            return isinstance(api_id, int) and api_id > 0

        @staticmethod
        def _is_valid_api_hash(api_hash: str) -> bool:
            return isinstance(api_hash, str) and len(api_hash) == 32

        @staticmethod
        def _is_valid_session_path(path: str) -> bool:
            session_path = str(path)
            return bool(session_path) and session_path.endswith(SESSION_SUFFIX)

        @classmethod
        async def _with_client(
            cls,
            path: str,
            api_id: int,
            api_hash: str,
            action: Callable[[TelegramClient], Awaitable[Result]],
            context: str,
        ) -> Result:
            client: TelegramClient | None = None
            try:
                session_path = str(path)
                client = TelegramClient(session_path, api_id, api_hash)
                await client.connect()
                logger.info(context)
                return await action(client)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Критическая ошибка при работе с сессией: %s", exc)
                return Result(success=False, message="critical_error")
            finally:
                if client:
                    try:
                        await client.disconnect()  # pyright: ignore
                    except Exception as disconnect_exc:  # noqa: BLE001
                        logger.debug(
                            "Ошибка при отключении клиента: %s", disconnect_exc
                        )

        @classmethod
        async def create_telethon_session(
            cls,
            phone: str,
            code: str | int,
            api_id: int,
            api_hash: str,
            phone_code_hash: str,
            password: str | None,
            path: str,
        ) -> Result:
            if not cls._is_valid_phone(phone):
                return Result(success=False, message="invalid_phone")
            if not cls._is_valid_api_id(api_id):
                return Result(success=False, message="invalid_api_id")
            if not cls._is_valid_api_hash(api_hash):
                return Result(success=False, message="invalid_api_hash")
            if not cls._is_valid_session_path(path):
                return Result(success=False, message="invalid_path")

            code_str = str(code).strip()

            async def _authorize(client: TelegramClient) -> Result:
                if await client.is_user_authorized():
                    me = await client.get_me()
                    logger.info(
                        "Пользователь уже авторизован: %s (@%s)",
                        me.first_name,
                        me.username,
                    )
                    return Result(success=True, message=None)

                try:
                    if password:
                        await client.sign_in(password=password)
                    else:
                        await client.sign_in(
                            phone=phone, code=code_str, phone_code_hash=phone_code_hash
                        )

                    if await client.is_user_authorized():
                        me = await client.get_me()
                        logger.info("Авторизация прошла успешно!")
                        logger.info(
                            "Пользователь: %s (@%s)", me.first_name, me.username
                        )
                        return Result(success=True, message=None)
                    return Result(success=False, message="auth_failed")
                except PhoneCodeInvalidError:
                    logger.warning("Неверный код для номера %s.", phone)
                    return Result(success=False, message="invalid_code")
                except PhoneCodeExpiredError:
                    logger.warning("Код устарел для номера %s.", phone)
                    return Result(success=False, message="code_expired")
                except SessionPasswordNeededError:
                    logger.info("Требуется пароль 2FA для номера %s.", phone)
                    return Result(success=False, message="password_required")
                except FloodWaitError as e:
                    logger.warning(
                        "Ожидание FloodWait: необходимо подождать %s секунд.", e.seconds
                    )
                    return Result(success=False, message=f"flood_wait:{e.seconds}")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Неожиданная ошибка при авторизации: %s", exc)
                    return Result(success=False, message=f"error:{exc!s}")

            return await cls._with_client(
                path,
                api_id,
                api_hash,
                _authorize,
                f"Подключение к Telegram для номера {phone}...",
            )

        @classmethod
        async def send_code_via_telethon(
            cls,
            phone: str,
            api_id: int,
            api_hash: str,
            path: str,
        ) -> Result:
            if not cls._is_valid_phone(phone):
                logger.warning("Неверный формат номера телефона: %s", phone)
                return Result(success=False, message="Неверный формат номера телефона")
            if not cls._is_valid_api_id(api_id):
                logger.warning("Неверный API ID: %s", api_id)
                return Result(success=False, message="Неверный API ID")
            if not cls._is_valid_api_hash(api_hash):
                logger.warning("Неверный или отсутствующий API Hash.")
                return Result(success=False, message="Неверный API Hash")
            if not cls._is_valid_session_path(path):
                logger.warning("Некорректный путь к сессии: %s", path)
                return Result(success=False, message="Некорректный путь к сессии")

            async def _send_code(client: TelegramClient) -> Result:
                if await client.is_user_authorized():
                    logger.info("Пользователь с номером %s уже авторизован.", phone)
                    return Result(success=False, message="Пользователь уже авторизован")

                try:
                    result = await client.send_code_request(
                        phone=phone,
                        force_sms=False,
                    )
                    phone_code_hash = result.phone_code_hash
                    logger.info(
                        "Код подтверждения успешно отправлен на %s. Hash: %s...",
                        phone,
                        phone_code_hash[:8],
                    )
                    return Result(success=True, message=phone_code_hash)
                except PhoneNumberInvalidError:
                    logger.warning("Неверный номер телефона: %s", phone)
                    return Result(success=False, message="Неверный номер телефона")
                except PhoneNumberBannedError:
                    logger.exception(
                        "Номер %s заблокирован (banned) в Telegram.", phone
                    )
                    return Result(success=False, message="Номер заблокирован")
                except SessionPasswordNeededError:
                    logger.warning(
                        "Для номера %s требуется пароль (2FA), но сессия не авторизована.",
                        phone,
                    )
                    return Result(success=False, message="Требуется пароль")
                except FloodWaitError as e:
                    wait_msg = f"Ограничение FloodWait: нельзя отправлять код. Подождите {e.seconds} секунд."
                    logger.warning(wait_msg)
                    return Result(success=False, message=wait_msg)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Неизвестная ошибка при отправке кода на %s: %s", phone, exc
                    )
                    return Result(
                        success=False,
                        message=f"Неизвестная ошибка при отправке кода на {phone}: {exc}",
                    )

            return await cls._with_client(
                path,
                api_id,
                api_hash,
                _send_code,
                f"Подключение к Telegram для отправки кода на {phone}...",
            )

    # Backward-compatible wrappers
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
        return await Function.Telethon.create_telethon_session(
            phone, code, api_id, api_hash, phone_code_hash, password, path
        )

    @staticmethod
    async def send_code_via_telethon(
        phone: str,
        api_id: int,
        api_hash: str,
        path: str,
    ) -> str | None:
        result = await Function.Telethon.send_code_via_telethon(
            phone, api_id, api_hash, path
        )
        return result.message if result.success else None
