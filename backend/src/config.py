from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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


class ProdDatabaseConfig(DatabaseConfig):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    @property
    def db_url(self):
        return (f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@"
                f"{self.HOST}:{self.PORT}/{self.DB}")


class YandexAuthConfig(ConfigBase):
    CLIENT_ID: str
    CLIENT_SECRET: str
    REDIRECT_URI: str


class Config(BaseSettings):
    prod_db: ProdDatabaseConfig = Field(default_factory=ProdDatabaseConfig)
    yandex_auth: YandexAuthConfig = Field(default_factory=YandexAuthConfig)

    @classmethod
    def load(cls) -> "Config":
        return cls()


config = Config()
