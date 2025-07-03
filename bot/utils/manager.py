import asyncio
import logging
import os
import signal

import psutil  # type: ignore

from config import BOT_NAME

logger = logging.getLogger(__name__)

PID_FILE = "_bot.pid"
LOG_FILE = "_bot.log"


async def start_bot(phone: str, path_to_folder: str) -> int:
    path_log = os.path.join(path_to_folder, f"{phone}{LOG_FILE}")
    path_pid = os.path.join(path_to_folder, f"{phone}{PID_FILE}")
    # Открываем файл лога асинхронно через обычный open — asyncio не поддерживает асинхронный доступ к файлам
    log = open(path_log, "a")

    # Запускаем процесс через nohup, без '&', чтобы получить PID
    process = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        BOT_NAME,
        phone,
        stdout=log,
        stderr=log,
        preexec_fn=os.setpgrp,
    )

    with open(path_pid, "w") as f:
        f.write(str(process.pid))

    logger.info(f"Бот запущен с PID: {process.pid}")
    return process.pid


async def bot_has_started(phone: str, path_to_folder: str) -> bool:
    path_pid = os.path.join(path_to_folder, f"{phone}{PID_FILE}")
    if not os.path.exists(path_pid):
        return False
    with open(path_pid, "r") as f:
        pid = int(f.read())
    return psutil.pid_exists(pid)


async def delete_bot(phone: str, path_to_folder: str) -> None:
    path_pid = os.path.join(path_to_folder, f"{phone}{PID_FILE}")
    if not os.path.exists(path_pid):
        logger.info("PID-файл не найден, бот не запущен?")
        return

    with open(path_pid, "r") as f:
        pid = int(f.read())

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        logger.info(f"Отправлен сигнал завершения процессу с PID: {pid}")
    except ProcessLookupError:
        logger.info("Процесс не найден")
    except PermissionError:
        logger.info("Нет прав на завершение процесса")

    await delete_files_by_name(path_to_folder, [f"{phone}_session.session", f"{phone}{PID_FILE}"])


async def delete_files_by_name(folder_path: str, filenames: list[str]) -> None:
    """
    Удаляет файлы с указанными именами в папке.

    :param folder_path: Путь к папке.
    :param filenames: Список имён файлов для удаления (например, ['file1.txt', 'temp.log']).
    """
    if not os.path.exists(folder_path):
        logger.info(f"Папка {folder_path} не существует.")
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path) and filename in filenames:
            try:
                os.remove(file_path)
                logger.info(f"Удален файл: {file_path}")
            except Exception as e:
                logger.info(f"Не удалось удалить {file_path}: {e}")
