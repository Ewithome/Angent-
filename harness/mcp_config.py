"""MCP 服务配置：本地 JSON 存储、内置服务与字段校验。"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

BUILTIN_SERVER_NAME = "building"
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _config_path() -> Path:
    """返回 MCP 配置文件的绝对路径，默认项目根目录 .mcp_servers.json。"""
    raw = os.getenv("MCP_CONFIG_FILE")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / ".mcp_servers.json"


class McpServerConfig(BaseModel):
    """一个 MCP 服务的完整配置，支持 stdio 与 streamable-http 两种传输。"""

    name: str = Field(description="服务名称，作为工具命名空间，例如 github、filesystem")
    label: str = Field(default="", description="网页端展示名称")
    enabled: bool = Field(default=True, description="是否在下次 Harness 启动时加载")
    transport: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        description="传输方式：stdio 为本地进程，streamable-http 为 HTTP 服务",
    )
    command: str | None = Field(default=None, description="stdio 模式可执行程序")
    args: list[str] = Field(default_factory=list, description="stdio 模式启动参数")
    env: dict[str, str] = Field(default_factory=dict, description="stdio 模式附加环境变量")
    cwd: str | None = Field(default=None, description="stdio 模式工作目录")
    url: str | None = Field(default=None, description="streamable-http 模式端点地址")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP 模式附加请求头")
    tool_call_timeout_ms: int = Field(
        default=120_000,
        ge=1_000,
        le=600_000,
        description="单次工具调用超时，单位毫秒",
    )
    fail_on_startup_error: bool = Field(
        default=False,
        description="连接失败时是否让 Harness 启动失败；建议保持 False",
    )
    builtin: bool = Field(default=False, description="是否为项目内置服务，只读")
    description: str = Field(default="", description="用途说明")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not _NAME_PATTERN.match(value):
            raise ValueError("服务名称仅支持字母、数字、下划线和中划线，最长 32 位")
        return value

    @model_validator(mode="after")
    def _validate_transport_fields(self) -> "McpServerConfig":
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio 模式必须配置 command 可执行程序")
        if self.transport == "streamable-http" and not self.url:
            raise ValueError("streamable-http 模式必须配置 url 端点地址")
        return self


def builtin_server() -> McpServerConfig:
    """项目自带的知识库与建筑工具 MCP 服务，始终自动加载。"""
    return McpServerConfig(
        name=BUILTIN_SERVER_NAME,
        label="企业知识库与建筑工具（内置）",
        description="规范检索、用量计算、CAD 图纸生成与项目纪要工具",
        transport="stdio",
        command=str(Path(sys.executable).resolve()),
        args=["-m", "harness.mcp_server"],
        cwd=str(PROJECT_ROOT),
        tool_call_timeout_ms=120_000,
        fail_on_startup_error=True,
        builtin=True,
    )


class McpConfigStore:
    """管理自定义 MCP 服务配置的本地 JSON 文件。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or _config_path()).resolve()

    def _load_file(self) -> list[McpServerConfig]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"MCP 配置文件解析失败: {exc}") from exc
        if not isinstance(payload, list):
            raise ValueError("MCP 配置文件内容必须是一个服务数组")
        return [
            McpServerConfig.model_validate(item)
            for item in payload
            if isinstance(item, dict)
        ]

    def _write_file(self, servers: list[McpServerConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [server.model_dump() for server in servers]
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def list_custom(self) -> list[McpServerConfig]:
        """返回用户配置的外部 MCP 服务，内置服务不写入 JSON。"""
        return [server for server in self._load_file() if not server.builtin]

    def list_all(self) -> list[McpServerConfig]:
        """返回内置服务与用户自定义服务的合集，用于界面和接口展示。"""
        return [builtin_server(), *self.list_custom()]

    def get_custom(self, name: str) -> McpServerConfig | None:
        return next(
            (server for server in self.list_custom() if server.name == name),
            None,
        )

    def upsert(self, server: McpServerConfig) -> McpServerConfig:
        """新增或覆盖一个自定义 MCP 服务。"""
        if server.name == BUILTIN_SERVER_NAME:
            raise ValueError(f"{BUILTIN_SERVER_NAME} 是内置服务名称，不能修改")
        custom_server = server.model_copy(update={"builtin": False})
        servers = self.list_custom()
        servers = [
            item for item in servers if item.name != custom_server.name
        ]
        servers.append(custom_server)
        self._write_file(servers)
        return custom_server

    def delete(self, name: str) -> bool:
        """删除自定义 MCP 服务；内置服务返回 False。"""
        if name == BUILTIN_SERVER_NAME:
            return False
        servers = self.list_custom()
        remaining = [server for server in servers if server.name != name]
        if len(remaining) == len(servers):
            return False
        self._write_file(remaining)
        return True


_default_store: McpConfigStore | None = None


def get_mcp_store() -> McpConfigStore:
    """获取进程级默认 MCP 配置存储。"""
    global _default_store
    if _default_store is None:
        _default_store = McpConfigStore()
    return _default_store


def list_enabled_servers() -> list[McpServerConfig]:
    """返回实际写入 Harness patch 的服务列表。"""
    store = get_mcp_store()
    custom = [server for server in store.list_custom() if server.enabled]
    return [builtin_server(), *custom]
