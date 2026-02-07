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
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    PASSWORD: str
    USER: str
    DB: str
    HOST: str
    PORT: int

    @computed_field  # Прочитал, что классная практика, помогает в сериализации
    @property
    def db_url(self):
        return (f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@"
                f"{self.HOST}:{self.PORT}/{self.DB}")


class Config(BaseSettings):
    db: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def load(cls) -> "Config":
        return cls()


config = Config()
