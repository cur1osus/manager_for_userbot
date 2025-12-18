import os
from pathlib import Path

from dotenv import load_dotenv
from redis.asyncio import Redis
from sqlalchemy import URL

load_dotenv()


def _decode_sep(value: str) -> str:
    """Конвертирует escape-последовательности вроде '\\n' в реальные символы."""
    try:
        decoded = value.encode("utf-8").decode("unicode_escape")
    except Exception:
        return value or "\n"
    return decoded or "\n"


class RedisSettings:
    def __init__(self) -> None:
        self.host = os.environ.get("REDIS_HOST", "localhost")
        self.port = int(os.environ.get("REDIS_PORT", 6379))
        self.db = os.environ.get("REDIS_DB", 0)


class DBSettings:
    def __init__(self, _env_prefix: str = "MYSQL_") -> None:
        self.host = os.environ.get(f"{_env_prefix}HOST", "localhost")
        self.port = os.environ.get(f"{_env_prefix}PORT", 3306)
        self.db = os.environ.get(f"{_env_prefix}DB", "database")
        self.username = os.environ.get(f"{_env_prefix}USERNAME", "user")
        self.password = os.environ.get(f"{_env_prefix}PASSWORD", "password")


class Settings:
    def __init__(self) -> None:
        self.bot_token = os.environ.get("BOT_TOKEN", "")
        self.path_to_folder = os.environ.get("PATH_TO_FOLDER", "sessions")
        self.script_path = os.environ.get(
            "SCRIPT_PATH",
            str(Path(__file__).resolve().parent.parent / "start_bot.sh"),
        )
        raw_sep = os.environ.get("SEP", "\n")
        self.sep = _decode_sep(raw_sep)

        self.db: DBSettings = DBSettings()
        self.redis: RedisSettings = RedisSettings()

    def mysql_dsn(self) -> URL:
        return URL.create(
            drivername="mysql+aiomysql",
            database=self.db.db,
            username=self.db.username,
            password=self.db.password,
            host=self.db.host,
        )

    def mysql_dsn_string(self) -> str:
        return URL.create(
            drivername="mysql+aiomysql",
            database=self.db.db,
            username=self.db.username,
            password=self.db.password,
            host=self.db.host,
        ).render_as_string(hide_password=False)

    async def redis_dsn(self) -> Redis:
        return Redis(host=self.redis.host, port=self.redis.port, db=self.redis.db)


se = Settings()
