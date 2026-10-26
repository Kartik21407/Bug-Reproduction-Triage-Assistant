"""Typed settings loaded from the environment through pydantic-settings.
Single source for DATABASE_URL, the session secret and the cookie flags."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    # NFR-03 caps a session at 60 minutes. This is the one place that number
    # lives; nothing else hardcodes it.
    session_expire_minutes: int = 60
    session_cookie_name: str = "session"
    cookie_secure: bool = False

    gemini_api_key: str = ""
    # gemini-2.5-flash and gemini-2.5-flash-lite both returned 404 "no
    # longer available to new users" against a real key; confirmed working.
    gemini_model: str = "gemini-3.1-flash-lite"


@lru_cache
def get_settings() -> Settings:
    """Returns the process-wide Settings instance, read from the environment
    once and cached. Call this rather than instantiating Settings() directly."""
    return Settings()
