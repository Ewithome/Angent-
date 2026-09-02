"""API 配置：统一从环境变量和 .env 读取。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 应用与运行环境
    app_name: str = "建筑规范图集智能体 API"
    app_version: str = "1.1.0"
    api_prefix: str = "/api/v1"
    environment: str = "development"

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    agent_memory_db: str = "agent_memory.db"
    agent_notes_dir: str = "notes"

    # DeepSeek Agent Harness 配置
    harness_home: str = ".harness_home"
    harness_workspace: str = ".harness_workspace"
    harness_model: str | None = None
    harness_max_tokens: int = 16384
    harness_timeout_seconds: int = 300
    harness_system_prompt: str = ""

    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # 自动读取根目录 .env，环境变量优先级高于文件
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次请求都重复解析环境变量。"""
    return Settings()
