from pydantic import SecretStr
from pydantic_settings import BaseSettings
from redis.asyncio import Redis
from sqlalchemy import URL


class SQLiteSettings(BaseSettings):
    db: str
    username: str
    password: str
    host: str


class RedisSettings(BaseSettings):
    host: str
    port: int
    db: int


class Settings(BaseSettings):
    developer_id: int
    dev: bool
    bot_token: SecretStr

    psql: SQLiteSettings = SQLiteSettings(_env_prefix="MYSQL_")  # type: ignore
    redis: RedisSettings = RedisSettings(_env_prefix="REDIS_")  # type: ignore

    def sqlite_dsn(self) -> URL:
        return URL.create(
            drivername="mysql+aiomysql",
            database=self.psql.db,
            username=self.psql.username,
            password=self.psql.password,
            host=self.psql.host,
        )

    async def redis_dsn(self) -> Redis:
        return Redis(host=self.redis.host, port=self.redis.port, db=self.redis.db)
