"""智能体服务：负责组装 Agent、执行对话和管理会话。"""
from __future__ import annotations

from agent_core import build_agent, get_final_answer, thread_config

_agent = None


def get_agent():
    """惰性单例：API 进程内只构建一次 Agent，复用数据库连接。"""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def run_chat(
    message: str,
    session_id: str = "default",
    engine: str = "langchain",
) -> str:
    """执行一轮对话，engine 支持 langchain 或 harness。"""
    if engine == "harness":
        from harness.agent import run_harness_chat

        return run_harness_chat(message, session_id)

    agent = get_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config=thread_config(session_id),
    )
    return get_final_answer(result)


def list_session_messages(
    session_id: str,
    limit: int = 50,
) -> list[dict[str, str]]:
    """读取指定会话最近的用户/助手消息，供接口对外展示。"""
    agent = get_agent()
    snapshot = agent.get_state(thread_config(session_id))
    messages = snapshot.values.get("messages", [])

    result: list[dict[str, str]] = []
    for message in messages:
        role = getattr(message, "type", "")
        if role not in {"human", "ai"}:
            continue
        content = message.content
        if isinstance(content, list):
            content = " ".join(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict)
            )
        if content:
            result.append({"role": role, "content": str(content)})
    return result[-limit:]


def delete_session(session_id: str) -> None:
    """删除指定会话的持久化记忆。"""
    agent = get_agent()
    checkpointer = agent.checkpointer
    if hasattr(checkpointer, "delete_thread"):
        checkpointer.delete_thread(session_id)
