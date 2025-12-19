from __future__ import annotations

import asyncio
import html
import logging
from typing import Any, Final

import msgpack
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.db.models import Bot as DBBot
from bot.db.models import Job, UserAnalyzed, UserManager
from bot.keyboards.inline import ik_tool_for_pack_users
from bot.utils import fn

logger = logging.getLogger(__name__)

SessionFactory = async_sessionmaker[AsyncSession]

REDIS_PREFIX: Final[str] = "manager_for_userbot"
NOT_ACCEPTED_LAST_ID_KEY: Final[str] = f"{REDIS_PREFIX}:not_accepted:last_id"

# Backward compatibility with legacy `key_builder()` keys.
LEGACY_REDIS_PREFIX: Final[str] = "fsm:0:0:0:default"
LEGACY_NOT_ACCEPTED_LAST_ID_KEY: Final[str] = f"{LEGACY_REDIS_PREFIX}:last_id"

# Conservative delay between outgoing messages to the same user.
SEND_DELAY_SECONDS: Final[float] = 1.0
USERBOT_JOB_TASKS: Final[tuple[str, ...]] = (
    "delete_private_channel",
    "connection_error",
    "flood_wait_error",
)


def _redis_key(*parts: str) -> str:
    return ":".join((REDIS_PREFIX, *parts))


async def _redis_get_int(redis: Redis, key: str) -> int | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Некорректное значение в Redis (%s=%r)", key, raw)
        return None


async def _redis_get_int_fallback(
    redis: Redis, key: str, legacy_key: str
) -> int | None:
    value = await _redis_get_int(redis, key)
    if value is not None:
        return value

    legacy_value = await _redis_get_int(redis, legacy_key)
    if legacy_value is None:
        return None

    # Migrate state forward to the new keyspace.
    await redis.set(key, legacy_value)
    return legacy_value


def _msgpack_unpack(data: Any) -> Any:
    if not data:
        return None
    try:
        return msgpack.unpackb(data, raw=False)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось распаковать msgpack payload")
        return None


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _format_decision_summary(decision: Any) -> str | None:
    if not isinstance(decision, dict):
        return None

    items: list[str] = []
    for key, value in decision.items():
        if key in {"banned"}:
            continue
        if isinstance(value, (str, int, float, bool)) and value not in ("", None):
            items.append(f"{key}={value}")
        if len(items) >= 6:
            break

    return ", ".join(items) if items else None


def _format_not_accepted_message(
    user: UserAnalyzed,
    db_bot: DBBot,
    decision: Any,
) -> str:
    bot_name = db_bot.name or "🌀"
    username = user.username or "нет"
    username = username if username.startswith("@") else f"@{username}"

    msg = (user.additional_message or "").replace("\n", " ").strip()
    msg_short = msg[:200]

    lines = [
        f"<b>Не принято</b> <code>id:{user.id}</code>",
        f"<b>Бот:</b> {_escape(bot_name)} <code>{_escape(db_bot.phone)}</code>",
        f"<b>Юзер:</b> {_escape(username)}",
    ]

    decision_summary = _format_decision_summary(decision)
    if decision_summary:
        lines.append(f"<b>Решение:</b> {_escape(decision_summary)}")

    if msg_short:
        lines.append(f"<b>Текст:</b> <code>{_escape(msg_short)}</code>")

    return "\n".join(lines)


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} сек."

    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} мин. {sec} сек."

    hours, minutes = divmod(minutes, 60)
    return f"{hours} ч. {minutes} мин."


async def send_not_accepted_posts(
    sessionmaker: SessionFactory,
    bot: Bot,
    redis: Redis,
) -> None:
    """Sends short notifications about `accepted=False` items to managers.

    To avoid spamming on first run, when `last_id` is missing we only send the latest
    record (like the legacy implementation).
    """

    async with sessionmaker() as session:
        last_id = await _redis_get_int_fallback(
            redis,
            NOT_ACCEPTED_LAST_ID_KEY,
            LEGACY_NOT_ACCEPTED_LAST_ID_KEY,
        )

        query = (
            select(UserAnalyzed)
            .options(selectinload(UserAnalyzed.bot).selectinload(DBBot.manager))
            .where(UserAnalyzed.accepted.is_(False))
        )
        if last_id is None:
            # First run: send only the latest record to avoid spamming backlog.
            query = query.order_by(UserAnalyzed.id.desc()).limit(1)
        else:
            # Normal mode: process new records deterministically without skipping.
            query = (
                query.where(UserAnalyzed.id > last_id)
                .order_by(UserAnalyzed.id.asc())
                .limit(30)
            )

        candidates = list((await session.scalars(query)).all())
        if not candidates:
            return

        max_seen_id = candidates[-1].id

        for user in candidates:
            db_bot = user.bot
            if db_bot is None:
                continue

            manager = db_bot.manager
            if manager is None or manager.is_antiflood_mode:
                continue

            decision = _msgpack_unpack(user.decision)
            if isinstance(decision, dict) and decision.get("banned"):
                continue

            text = _format_not_accepted_message(user, db_bot, decision)
            try:
                await bot.send_message(
                    manager.id_user,
                    text=text,
                    disable_notification=True,
                )
            except TelegramAPIError as exc:
                logger.warning(
                    "Не удалось отправить уведомление менеджеру %s: %s",
                    manager.id_user,
                    exc,
                )
            await asyncio.sleep(SEND_DELAY_SECONDS)

        await redis.set(NOT_ACCEPTED_LAST_ID_KEY, max_seen_id)


async def _handle_single_job(
    job: Job,
    db_bot: DBBot,
    manager: UserManager,
    bot: Bot,
) -> None:
    match job.task:
        case "delete_private_channel":
            channel = _msgpack_unpack(job.task_metadata)
            await bot.send_message(
                chat_id=manager.id_user,
                text=(
                    "Удалите канал "
                    f"({_escape(str(channel))}), так как вы были в нем забанены или удалены; "
                    "это мешает корректной работе бота."
                ),
            )

        case "connection_error":
            await bot.send_message(
                chat_id=manager.id_user,
                text=f"Ошибка подключения к серверу для бота {_escape(db_bot.name or '🌀')}[{_escape(db_bot.phone)}]",
            )

        case "flood_wait_error":
            db_bot.is_started = False
            data = _msgpack_unpack(job.task_metadata) or {}
            seconds = int(data.get("time", 0)) if isinstance(data, dict) else 0
            await bot.send_message(
                chat_id=manager.id_user,
                text=(
                    f"Ошибка FloodWait (до {_format_duration(seconds)}) для "
                    f"{_escape(db_bot.name or '🌀')}[{_escape(db_bot.phone)}], "
                    "бот был остановлен."
                ),
            )

        case _:
            logger.info("Неизвестная задача %s (job_id=%s)", job.task, job.id)


async def handle_job_from_userbot(
    sessionmaker: SessionFactory,
    bot: Bot,
) -> None:
    async with sessionmaker() as session:
        rows = await session.scalars(
            select(Job)
            .options(selectinload(Job.bot).selectinload(DBBot.manager))
            .where(
                Job.answer.is_(None),
                Job.task.in_(USERBOT_JOB_TASKS),
            )
            .order_by(Job.id.asc())
            .limit(100),
        )
        jobs = list(rows.all())
        if not jobs:
            return

        for job in jobs:
            # Mark as processed even if sending fails to avoid duplicate notifications.
            job.answer = msgpack.packb(True, use_bin_type=True)

            db_bot = job.bot
            if db_bot is None:
                logger.info("Bot не найден для job_id=%s bot_id=%s", job.id, job.bot_id)
                continue

            manager = db_bot.manager
            if manager is None:
                logger.info(
                    "Manager не найден для bot_id=%s (job_id=%s)", db_bot.id, job.id
                )
                continue

            try:
                await _handle_single_job(job, db_bot, manager, bot)
            except TelegramAPIError as exc:
                logger.warning("Ошибка Telegram API при job_id=%s: %s", job.id, exc)
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка при обработке задания job_id=%s", job.id)

        await session.commit()


def _format_pack_message(db_bot: DBBot, users: list[UserAnalyzed]) -> str:
    header = f"Пак от {_escape(db_bot.name or '🌀')}[{_escape(db_bot.phone)}]"

    rows: list[str] = []
    for user in users:
        msg = (user.additional_message or "").replace("\n", " ").strip()
        msg_short = _escape(msg[:10])
        username = user.username or "нет"
        username = username if username.startswith("@") else f"@{username}"
        rows.append(f"<code>{msg_short}</code> - {_escape(username)}")

    return f"{header}\n\n" + "\n\n".join(rows)


async def antiflood_pack_users(
    sessionmaker: SessionFactory,
    bot: Bot,
    redis: Redis,
) -> None:
    """When manager antiflood mode is enabled, send a "pack" to pause processing."""

    async with sessionmaker() as session:
        rows = await session.scalars(
            select(DBBot)
            .options(selectinload(DBBot.manager))
            .where(DBBot.is_started.is_(True))
            .order_by(DBBot.id.asc()),
        )
        active_bot = rows.first()
        if active_bot is None:
            return

        user_manager = active_bot.manager
        if user_manager is None or not user_manager.is_antiflood_mode:
            return

        last_pack_key = _redis_key("antiflood", "last_id", str(active_bot.id))
        legacy_pack_key = f"{LEGACY_REDIS_PREFIX}:antiflood_last_id:{active_bot.id}"
        last_user_id = await _redis_get_int_fallback(
            redis, last_pack_key, legacy_pack_key
        )

        pack_users = await fn.get_closer_data_users(
            session,
            active_bot.id,
            user_manager.limit_pack,
            last_user_id=last_user_id,
        )

        if len(pack_users) < user_manager.limit_pack:
            return

        text = _format_pack_message(active_bot, pack_users)
        try:
            await bot.send_message(
                chat_id=user_manager.id_user,
                text=text,
                reply_markup=await ik_tool_for_pack_users(),
            )
        except TelegramAPIError as exc:
            logger.warning(
                "Не удалось отправить pack (bot_id=%s manager_id=%s): %s",
                active_bot.id,
                user_manager.id_user,
                exc,
            )
            return

        await redis.set(last_pack_key, pack_users[-1].id)
