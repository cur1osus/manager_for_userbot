from pydantic import SecretStr
from pydantic_settings import BaseSettings
from redis.asyncio import Redis
from sqlalchemy import URL
from dotenv import load_dotenv

load_dotenv()


class MysqlSettings(BaseSettings):
    db: str
    password: str
    username: str
    host: str


class RedisSettings(BaseSettings):
    host: str
    port: int
    db: int


class Settings(BaseSettings):
    developer_id: int
    dev: bool
    bot_token: SecretStr

    mysql: MysqlSettings = MysqlSettings(_env_prefix="MYSQL_")  # type: ignore
    redis: RedisSettings = RedisSettings(_env_prefix="REDIS_")  # type: ignore

    def sqlite_dsn(self) -> URL:
        return URL.create(
            drivername="mysql+aiomysql",
            database=self.mysql.db,
            username=self.mysql.username,
            password=self.mysql.password,
            host=self.mysql.host,
        )

    async def redis_dsn(self) -> Redis:
        return Redis(host=self.redis.host, port=self.redis.port, db=self.redis.db)
