"""API 配置：统一从环境变量和 .env 读取。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DeepSeek 智能体 API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    environment: str = "development"

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    agent_memory_db: str = "agent_memory.db"
    agent_notes_dir: str = "notes"

    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
