import base64

from functools import lru_cache  # cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    database_url: str

    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"
    jwt_private_key_b64: str = ""
    jwt_public_key_b64: str = ""
    jwt_issuer: str = "tuition-auth"
    jwt_audience: str = "tuition-api"
    jwt_expire_minutes: int = 30

    app_timezone: str = "Europe/Istanbul"
    mobile_daily_query_limit: int = 3

    @property
    def jwt_private_key(self) -> str:
        if self.jwt_private_key_b64:
            return base64.b64decode(self.jwt_private_key_b64).decode()
        return (PROJECT_ROOT / self.jwt_private_key_path).read_text()

    @property
    def jwt_public_key(self) -> str:
        if self.jwt_public_key_b64:
            return base64.b64decode(self.jwt_public_key_b64).decode()
        return (PROJECT_ROOT / self.jwt_public_key_path).read_text()


@lru_cache
def get_settings() -> Settings:
    return Settings()