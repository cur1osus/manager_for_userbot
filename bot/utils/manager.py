import asyncio
import dataclasses
import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Final

import psutil  # type: ignore

from bot.settings import se

logger = logging.getLogger(__name__)

PID_SUFFIX: Final[str] = ".pid"
SESSION_SUFFIX: Final[str] = ".session"
PID_FILE_WAIT_SECONDS: Final[float] = 1.0


@dataclasses.dataclass
class Result:
    success: bool
    message: str | None


@dataclasses.dataclass
class UserData:
    username: str
    item_name: str


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


async def start_bot(phone: str, path_session: str, api_id: int, api_hash: str) -> int:
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


async def bot_run(phone: str) -> bool:
    pid = _read_pid(_pid_file(phone))
    return bool(pid and psutil.pid_exists(pid))


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
    await delete_files_by_name(se.path_to_folder, files)


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
            except Exception as exc:
                logger.info("Не удалось удалить %s: %s", file_path, exc)
