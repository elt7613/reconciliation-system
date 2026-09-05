"""Service configuration — all values env-driven (pydantic-settings).

The .env file lives next to this service (ai-service/.env) for local dev; in
production (Dokploy) values come from the platform's environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Shared secret with the Django backend (X-API-Key header). Required —
    # the service fails closed without it.
    ai_service_api_key: str = ""

    # OpenRouter / agent configuration — swappable without code changes.
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3.8-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_temperature: float = 0.1
    llm_max_retries: int = 1
    llm_timeout_seconds: int = 45
    llm_enabled: bool = True


settings = Settings()
