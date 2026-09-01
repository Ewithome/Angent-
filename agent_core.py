"""DeepSeek 智能体核心：工具、模型、记忆与组装。"""
from __future__ import annotations

import ast
import operator
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

from building_tools import (
    calculate_brick_wall_quantity,
    calculate_concrete_volume,
    calculate_paint_area,
    calculate_rebar_weight,
    generate_cad_drawing,
)
from knowledge_base import search_building_code

load_dotenv()

DB_PATH = os.getenv("AGENT_MEMORY_DB", "agent_memory.db")
NOTES_DIR = Path(os.getenv("AGENT_NOTES_DIR", "notes"))

# 智能体系统提示词：约束模型只依据检索结果和工具结果回答，避免编造规范条文
SYSTEM_PROMPT = """你是一名专业的建筑规范图集咨询智能体，名叫“规范助手”。
你的职责是帮助客户查询建筑规范标准内容、计算工程用量，并生成建筑平面示意 CAD 图纸。

规则：
1. 回答规范标准问题时，必须优先调用 search_building_code 检索知识库，并引用检索到的来源；知识库没有依据时，明确说明当前知识库未收录，绝不编造条文编号或强制条款。
2. 计算混凝土、砖墙、涂料、钢筋用量时，使用对应的计算工具，并展示计算过程。
3. 用户要求生成或设置 CAD 图纸时，使用 generate_cad_drawing，输出 DXF 文件路径。
4. 遇到普通数学计算时，使用 calculator。
5. 用户要求记住或查看项目信息时，使用 save_note、list_notes、read_note。
6. 回答使用简体中文，面向建筑行业客户，专业、简洁、准确。"""


# ---------- 安全计算器 ----------
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval_expr(node):
    """递归求值 AST 节点，只允许数字和四则运算，避免 eval 任意代码执行。"""
    if isinstance(node, ast.Expression):
        return _eval_expr(node.body)
    if isinstance(node, ast.BinOp):
        return _ALLOWED_OPS[type(node.op)](_eval_expr(node.left), _eval_expr(node.right))
    if isinstance(node, ast.UnaryOp):
        return _ALLOWED_OPS[type(node.op)](_eval_expr(node.operand))
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    raise ValueError(f"不支持的表达式: {ast.dump(node)}")


@tool
def calculator(expression: str) -> str:
    """计算一个数学表达式，支持 + - * / ** % 和小括号，例如 "(1 + 2) * 3" 或 "2 ** 10"。参数是一个数学表达式字符串。"""
    try:
        # 先用 ast 解析成语法树，再交给受限求值器执行
        return str(_eval_expr(ast.parse(expression, mode="eval")))
    except Exception as e:  # noqa: BLE001
        return f"计算出错: {e}"


# ---------- 本地笔记 ----------
def _safe_title(title: str) -> str:
    """把用户提供的标题清理成安全文件名，避免路径注入。"""
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", title.strip())
    return cleaned or "未命名"


@tool
def save_note(title: str, content: str) -> str:
    """把一段内容保存成本地 Markdown 笔记。参数 title 是笔记标题，content 是笔记正文。"""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"{_safe_title(title)}.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(f"# {title}\n\n> {now}\n\n{content}\n", encoding="utf-8")
    return f"已保存笔记：{path}"


@tool
def list_notes() -> str:
    """列出所有已保存的笔记标题。"""
    if not NOTES_DIR.exists():
        return "还没有保存任何笔记。"
    titles = [p.stem for p in sorted(NOTES_DIR.glob("*.md"))]
    return "、".join(titles) if titles else "还没有保存任何笔记。"


@tool
def read_note(title: str) -> str:
    """读取指定标题的本地笔记内容。参数是笔记标题。"""
    path = NOTES_DIR / f"{_safe_title(title)}.md"
    if not path.exists():
        return f"没有找到笔记：{title}。可先用 list_notes 查看已有标题。"
    return path.read_text(encoding="utf-8")


TOOLS = [
    search_building_code,
    calculate_concrete_volume,
    calculate_brick_wall_quantity,
    calculate_paint_area,
    calculate_rebar_weight,
    generate_cad_drawing,
    calculator,
    save_note,
    list_notes,
    read_note,
]


# ---------- 组装 Agent ----------
def build_agent():
    # Streamlit 长驻进程里环境变量不会自动刷新，每次构建时重新读取 .env
    load_dotenv(override=True)

    api_key = os.getenv("DEEPSEEK_API_KEY")
    placeholder_keys = {"your_deepseek_api_key", "sk-在这里填写你的DeepSeekKey"}
    if not api_key or api_key in placeholder_keys:
        raise ValueError("请在 .env 中配置 DEEPSEEK_API_KEY，参考 .env.example")

    model = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=api_key,
        temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0")),
    )

    # SQLite 检查点负责持久化多轮会话记忆，check_same_thread=False 适配 Web 线程模型
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()

    # LangChain v1 标准 Agent 工厂：内部就是 model -> tools -> model 的循环
    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        name="deepseek_personal_assistant",
    )


def thread_config(thread_id: str) -> dict:
    """构造 LangGraph 线程配置，thread_id 用于隔离不同会话的记忆。"""
    return {"configurable": {"thread_id": thread_id}}


def get_final_answer(result: dict) -> str:
    """从 agent 返回的消息列表里取最后一条纯文本回复。"""
    for message in reversed(result["messages"]):
        if getattr(message, "content", None) and not getattr(message, "tool_calls", None):
            return message.content
    return ""
