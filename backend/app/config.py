from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "production"
    database_url: str = "postgresql+asyncpg://booking:booking@db/booking"
    redis_url: str = "redis://redis:6379/0"
    bot_token: str = ""
    admin_ids: str = ""
    mini_app_url: str = "https://localhost"
    dev_auth: bool = False
    uploads_dir: str = "/tmp/booking-uploads"
    auth_max_age: int = 3600

    @model_validator(mode="after")
    def secure(self):
        if self.dev_auth and self.environment != "development":
            raise ValueError("DEV_AUTH is only allowed in development")
        return self

    @property
    def admins(self):
        return {int(x) for x in self.admin_ids.split(",") if x.strip()}


@lru_cache
def settings():
    return Settings()
