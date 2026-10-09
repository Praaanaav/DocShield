from pydantic_settings import BaseSettings


class CacheSettings(BaseSettings):
    """Settings for fastcache, read from environment variables."""

    max_items: int = 1000
    default_ttl: int = 300
    redis_url: str | None = None