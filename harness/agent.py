"""DeepSeek Harness 接入封装：配置、MCP patch、进程复用与对话执行。"""
from __future__ import annotations

import json
import hashlib
import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from deepseek_harness import DeepSeekHarness, DeepSeekHarnessConfig

from harness.mcp_config import McpServerConfig, get_mcp_store, list_enabled_servers

# 项目根目录：MCP 工具子进程需要在这里启动，才能导入 knowledge_base 等模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 独立入口直接 import 时也先读取根目录 .env，避免配置延迟生效
load_dotenv(PROJECT_ROOT / ".env", override=True)


def _project_path(name: str, default_name: str) -> Path:
    """读取环境变量目录，相对路径固定解析到项目根目录。"""
    raw = os.getenv(name)
    path = Path(raw) if raw else PROJECT_ROOT / default_name
    return path if path.is_absolute() else PROJECT_ROOT / path


# 默认使用项目内隔离目录；官方建议 Harness home 与 workspace 都保持独立
HARNESS_HOME = _project_path("HARNESS_HOME", ".harness_home").resolve()
HARNESS_WORKSPACE = _project_path("HARNESS_WORKSPACE", ".harness_workspace").resolve()
HARNESS_PROFILE = os.getenv("HARNESS_PROFILE", "sdk-minimal")
HARNESS_MODEL = os.getenv(
    "HARNESS_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
)
HARNESS_MAX_TOKENS = int(os.getenv("HARNESS_MAX_TOKENS", "16384"))
HARNESS_TIMEOUT_SECONDS = int(os.getenv("HARNESS_TIMEOUT_SECONDS", "300"))

SYSTEM_PROMPT = """你是一名企业内部知识库智能体，名叫“规范助手”，当前运行在 DeepSeek Harness 上。
你的职责是回答客户关于建筑规范、制度、产品手册和业务流程的问题，并完成工程用量计算与 CAD 图纸生成。

规则：
1. 检索规范或制度内容前，必须调用 mcp__building__search_knowledge；回答时引用检索到的来源。
2. 知识库没有依据时，明确说明当前知识库未收录，绝不编造条文编号、强制条款或业务流程。
3. 混凝土、砖墙、涂料、钢筋用量计算分别调用对应工具，并向用户说明计算过程。
4. 生成 CAD 图时调用 mcp__building__generate_cad_drawing，并告知 DXF 文件位置。
5. 项目纪要使用 mcp__building__save_project_note / mcp__building__list_project_notes / mcp__building__read_project_note。
6. 所有回答使用简体中文，面向企业内部用户，专业、准确、简洁。"""


def _write_mcp_patch() -> Path:
    """生成一次启动专用的 MCP 配置，把本项目的领域工具挂到 Harness 上。

    patch 中必须使用当前解释器的绝对路径，因此每次启动时重新生成。
    """
    generated_dir = HARNESS_HOME / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    patch_path = generated_dir / "enterprise-building.patch.yml"

    patch_lines = [
        "# MCP 服务配置由 harness/agent.py 自动生成，不要手工提交",
    ]
    for server in list_enabled_servers():
        patch_lines.extend(_mcp_server_patch_rows(server))

    patch_lines.extend(
        [
            "",
            "# 关闭最小 profile 自带的不受限终端/编辑器，避免模型绕过领域工具直接改文件",
        ]
    )
    patch = "\n".join(patch_lines) + """
- id: persistent-bash
  disabled: true
- id: persistent-pwsh
  disabled: true
- id: str-replace-editor
  disabled: true
"""
    patch_path.write_text(patch, encoding="utf-8")
    return patch_path


def _mcp_server_patch_rows(server: McpServerConfig) -> list[str]:
    """把单个 MCP 服务配置转换成 profile patch 的 YAML 行。"""
    config: dict = {
        "serverName": server.name,
        "transport": server.transport,
        "toolCallTimeoutMs": server.tool_call_timeout_ms,
        "failOnStartupError": server.fail_on_startup_error,
    }
    if server.transport == "stdio":
        if server.command:
            config["command"] = server.command
        if server.args:
            config["args"] = server.args
        if server.env:
            config["env"] = server.env
        if server.cwd:
            config["cwd"] = server.cwd
    else:
        if server.url:
            config["url"] = server.url
        if server.headers:
            config["headers"] = server.headers

    return [
        "- insert:",
        f"    - id: mcp-{server.name}",
        "      name: '@deepseek-ai/dsh-mcp-client'",
        f"      config: {json.dumps(config, ensure_ascii=False)}",
    ]


def _api_key() -> str:
    """读取真实 DeepSeek Key；本地 .env 不会被提交到 Git。"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    placeholders = {"your_deepseek_api_key", "sk-在这里填写你的DeepSeekKey"}
    if not key or key in placeholders:
        raise ValueError("请在 .env 中配置 DEEPSEEK_API_KEY，参考 .env.example")
    return key


def _mcp_config_signature() -> str:
    """用配置文件哈希判断 MCP 服务是否变化，用于自动重建 Harness 运行时。"""
    path = get_mcp_store().path
    if not path.exists():
        return "empty"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_runtime() -> DeepSeekHarness:
    """创建并启动 DeepSeek Harness 运行时。"""
    HARNESS_HOME.mkdir(parents=True, exist_ok=True)
    HARNESS_WORKSPACE.mkdir(parents=True, exist_ok=True)
    patch_path = _write_mcp_patch()

    return DeepSeekHarness(
        config=DeepSeekHarnessConfig(
            provider="deepseek-official",
            model=HARNESS_MODEL,
            max_tokens=HARNESS_MAX_TOKENS,
            cwd=str(HARNESS_WORKSPACE),
            dsh_home=str(HARNESS_HOME),
            profile=HARNESS_PROFILE,
            patches=(str(patch_path),),
            api_key=_api_key(),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            env={
                "DSH_SYSTEM_PROMPT": os.getenv("HARNESS_SYSTEM_PROMPT", SYSTEM_PROMPT),
                "PYTHONIOENCODING": "utf-8",
            },
            initialize_timeout_seconds=min(60, max(10, HARNESS_TIMEOUT_SECONDS)),
            request_timeout_seconds=HARNESS_TIMEOUT_SECONDS,
            shutdown_timeout_seconds=3.0,
        )
    )


class HarnessGateway:
    """进程级单例，保证多个请求复用同一个 Harness 运行时与会话持久化。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runtime: DeepSeekHarness | None = None
        self._mcp_signature: str | None = None

    def _ensure_runtime(self) -> DeepSeekHarness:
        with self._lock:
            signature = _mcp_config_signature()
            if (
                self._runtime is not None
                and self._mcp_signature is not None
                and signature != self._mcp_signature
            ):
                # 用户新增/修改 MCP 服务后自动重建运行时，使新工具立即生效
                self._runtime.close()
                self._runtime = None
            if self._runtime is None:
                # 启动较慢且包含真实模型调用，因此只初始化一次
                self._runtime = build_runtime()
                self._runtime.start()
                self._mcp_signature = signature
            return self._runtime

    def run(self, message: str, session_id: str) -> str:
        """执行一轮 Harness 对话，返回最终文本回复。"""
        runtime = self._ensure_runtime()
        with self._lock:
            result = runtime.run(message, session_id=session_id)
        if not result.final_response:
            raise RuntimeError(
                f"Agent Harness 未返回有效回复（finish_reason={result.finish_reason}）"
            )
        return result.final_response

    def close(self) -> None:
        """显式关闭 Harness 子进程，主要用于应用退出与测试清理。"""
        with self._lock:
            if self._runtime is not None:
                try:
                    self._runtime.close()
                finally:
                    self._runtime = None
            self._mcp_signature = None

    def reload_mcp_servers(self) -> None:
        """关闭当前运行时；下一次对话会自动按最新 MCP 配置重新启动。"""
        with self._lock:
            if self._runtime is not None:
                self._runtime.close()
                self._runtime = None
            self._mcp_signature = None

    @staticmethod
    def delete_session(session_id: str) -> bool:
        """删除 Harness 本地 JSONL 会话，返回是否删除成功。"""
        sessions_root = HARNESS_HOME / "sessions"
        if not sessions_root.exists():
            return False
        removed = False
        for session_dir in sessions_root.rglob(session_id):
            jsonl = session_dir / "session.jsonl"
            if session_dir.is_dir() and jsonl.is_file():
                try:
                    jsonl.unlink()
                    removed = True
                except OSError:
                    # 删除失败不阻断界面操作，下次可继续覆盖写入
                    pass
        return removed


_gateway: HarnessGateway | None = None


def get_gateway() -> HarnessGateway:
    """惰性获取全局 Harness 网关。"""
    global _gateway
    if _gateway is None:
        load_dotenv(override=True)
        _gateway = HarnessGateway()
    return _gateway


def run_harness_chat(message: str, session_id: str = "default") -> str:
    """API、Streamlit 与命令行共用的 Harness 对话入口。"""
    return get_gateway().run(message, session_id)
