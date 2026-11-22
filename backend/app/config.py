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
    # gemini-2.5-flash and gemini-2.5-flash-lite return 404 for new keys, and
    # gemini-3.1-flash-lite answered 503 "high demand" for days; this one is
    # confirmed working against the real extraction prompt (ADR-026).
    gemini_model: str = "gemini-3.5-flash-lite"

    # Where the embedding model is stored after its one-time download.
    # Relative to the backend's working directory, so inside Docker it lands
    # in the bind-mounted backend/ folder and survives a container restart.
    embedding_cache_dir: str = ".fastembed_cache"
    # US-20 criterion 2's starting thresholds. An estimate to be revisited,
    # not tuned against labelled data (ADR-018).
    duplicate_likely_threshold: float = 0.80
    duplicate_possible_threshold: float = 0.60

    # Encrypts every stored GitHub token (US-26 criterion 3). A Fernet key;
    # empty means GitHub integration is switched off on this server. Losing
    # or changing it makes stored tokens unreadable, so each user connects
    # again; nothing else is affected.
    token_encryption_key: str = ""

    # US-28: the repository whose open issues are kept in the corpus
    # automatically, as owner/name. Empty means no automatic import until an
    # administrator sets one on the admin page, which then takes precedence.
    corpus_sync_repository: str = ""
    # How often the automatic import runs, in minutes. 0 switches the
    # background schedule off; an administrator can still run it by hand.
    corpus_sync_interval_minutes: int = 60
    # Optional GitHub token for the import, raising the rate limit from 60 to
    # 5,000 requests an hour. Read only; never stored or logged.
    corpus_sync_token: str = ""


@lru_cache
def get_settings() -> Settings:
    """Returns the process-wide Settings instance, read from the environment
    once and cached. Call this rather than instantiating Settings() directly."""
    return Settings()
