from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_bot_token: str

    llm_provider: str = "anthropic"  # anthropic | openai | copilot | custom

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"

    # OpenAI / custom
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    # GitHub Copilot (non-official)
    github_token: str = ""
    copilot_model: str = "gpt-4o"

    # Webhook (optional — leave empty to use polling)
    # Set to a publicly reachable HTTPS URL when deploying to a server,
    # e.g. https://yourdomain.com/bot  (path is used as the listen path)
    # Telegram only allows ports: 80, 88, 443, 8443
    webhook_url: str = ""
    webhook_secret: str = ""   # random string; Telegram sends it back for verification
    webhook_port: int = 8443
    webhook_listen: str = "0.0.0.0"

    # Storage
    db_path: str = "~/.media_agent/memory.db"
    users_config: str = "config/users.json"

    # Rate limit
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    rate_limit_pipeline_per_window: int = Field(default=6, ge=1)
    rate_limit_chat_per_window: int = Field(default=20, ge=1)


settings = Settings()
