import asyncio
import logging
import os
import signal
from config import BOT_NAME

logger = logging.getLogger(__name__)

PID_FILE = "_bot.pid"
LOG_FILE = "_bot.log"


async def start_bot(phone: str, path_to_folder: str):
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
    return process


async def bot_has_started(phone: str, path_to_folder: str):
    path_pid = os.path.join(path_to_folder, f"{phone}{PID_FILE}")
    if not os.path.exists(path_pid):
        return False
    with open(f"{phone}{PID_FILE}", "r") as f:
        pid = int(f.read())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


async def stop_bot(phone: str, path_to_folder: str):
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

    os.remove(path_pid)
