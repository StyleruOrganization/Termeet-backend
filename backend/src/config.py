from dataclasses import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="backend/settings/.env", env_file_encoding="utf-8", extra="ignore"
    )


class DatabaseConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="db_")

    host: str
    password: str


class Config(BaseSettings):
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @classmethod
    def load(cls) -> "Config":
        return cls()