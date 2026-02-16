from dataclasses import field

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="backend/settings/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


class DatabaseConfig(ConfigBase):

    PASSWORD: str
    USER: str
    DB: str
    HOST: str
    PORT: int

    @property
    def db_url(self):
        return (f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@"
                f"{self.HOST}:{self.PORT}/{self.DB}")


class TestDatabaseConfig(DatabaseConfig):
    model_config = SettingsConfigDict(env_prefix="TEST_POSTGRES_")

    @property
    def db_url(self):
        return (f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@"
                f"{self.HOST}:{self.PORT}/{self.DB}")


class ProdDatabaseConfig(DatabaseConfig):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    @property
    def db_url(self):
        return (f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@"
                f"{self.HOST}:{self.PORT}/{self.DB}")


class Config(BaseSettings):
    test_db: TestDatabaseConfig = field(default_factory=TestDatabaseConfig)
    prod_db: ProdDatabaseConfig = field(default_factory=ProdDatabaseConfig)

    @classmethod
    def load(cls) -> "Config":
        return cls()


config = Config()
