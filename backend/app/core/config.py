from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENUSAGE_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "OpenUsage WSL Dashboard"
    host: str = "127.0.0.1"
    port: int = 6736
    poll_interval_seconds: int = 300
    use_demo_data: bool = False
    cache_path: Path = Field(default=Path(".cache/usage-cache.json"))
    codex_home: Path = Field(default=Path("~/.codex").expanduser())
    claude_credentials_path: Path = Field(
        default=Path("~/.claude/.credentials.json").expanduser()
    )


settings = Settings()
