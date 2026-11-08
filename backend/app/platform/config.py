"""Application settings loaded from .env and environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EPIC_",
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EPIC"
    app_version: str = "0.1.0"
    env: str = "local"
    host: str = "127.0.0.1"
    port: int = 8765
    timezone: str = "Asia/Shanghai"

    data_dir: Path = ROOT_DIR / "data"
    log_dir: Path | None = None
    database_url: str | None = None

    llm_model: str = "deepseek-chat"
    llm_reasoner_model: str = "deepseek-reasoner"
    llm_daily_budget_usd: float = 5.0

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'epic.db').as_posix()}"

    @property
    def log_path(self) -> Path:
        return Path(self.log_dir) if self.log_dir else self.data_dir / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.log_path.mkdir(parents=True, exist_ok=True)
