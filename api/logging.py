"""API 日志配置：控制台 + 滚动文件日志。"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from api.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    # 防止 uvicorn reload 等场景重复挂载文件日志
    if any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        return

    root.setLevel(settings.log_level.upper())
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # 滚动文件日志：单文件最大 5MB，保留 5 个备份
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
