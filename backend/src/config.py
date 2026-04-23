from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent


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


class AuthJWTconfig(ConfigBase):
    PUBLIC_KEY_PATH: Path = BASE_DIR / "certs" / "jwt-public.pem"
    PRIVATE_KEY_PATH: Path = BASE_DIR / "certs" / "jwt-private.pem"
    ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30


class CookiesConfig(ConfigBase):
    HTTPS_TRUE: bool


class Config(BaseSettings):
    prod_db: ProdDatabaseConfig = Field(default_factory=ProdDatabaseConfig)
    yandex_auth: YandexAuthConfig = Field(default_factory=YandexAuthConfig)
    auth_jwt: AuthJWTconfig = Field(default_factory=AuthJWTconfig)
    cookies: CookiesConfig = Field(default_factory=CookiesConfig)

    @classmethod
    def load(cls) -> "Config":
        return cls()


config = Config()
