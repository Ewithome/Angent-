"""DeepSeek 智能体核心：工具、模型、记忆与组装。"""
from __future__ import annotations

import ast
import operator
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

DB_PATH = os.getenv("AGENT_MEMORY_DB", "agent_memory.db")
NOTES_DIR = Path(os.getenv("AGENT_NOTES_DIR", "notes"))

SYSTEM_PROMPT = """你是一个实用的个人助理智能体，名字叫“小助手”。
你只能依据真实工具结果回答，不要编造计算结果、天气或笔记内容。
规则：
1. 遇到数学计算时，使用 calculator，并把计算过程清晰展示给用户。
2. 用户问时间日期时，使用 get_current_time。
3. 用户问天气时，使用 get_weather，城市名可以是中文或英文。
4. 用户要求记住内容时，使用 save_note；要求查看笔记时，先 list_notes 再 read_note。
5. 回答使用简体中文，简洁、友好、直接。"""


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
        return str(_eval_expr(ast.parse(expression, mode="eval")))
    except Exception as e:  # noqa: BLE001
        return f"计算出错: {e}"


# ---------- 时间 ----------
@tool
def get_current_time() -> str:
    """获取当前日期和时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- 天气（Open-Meteo 真实数据，失败时兜底） ----------
_WEATHER_CODES = {
    0: "晴",
    1: "基本晴朗",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "毛毛雨",
    53: "小雨",
    55: "中雨",
    61: "阵雨",
    63: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "强阵雨",
    95: "雷雨",
    99: "强雷雨",
}


@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。参数是城市名，例如 "北京"、"上海"、"London"。"""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh", "format": "json"},
            timeout=8,
        ).json()
        results = geo.get("results") or []
        if not results:
            return f"没有找到城市 {city} 的天气数据。"

        place = results[0]
        name = place.get("name", city)
        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current_weather": True,
                "timezone": "Asia/Shanghai",
            },
            timeout=8,
        ).json()
        current = forecast.get("current_weather", {})
        temp = current.get("temperature")
        weather_code = current.get("weathercode")
        weather_text = _WEATHER_CODES.get(weather_code, f"代码{weather_code}")
        return f"{name}：当前 {temp}°C，{weather_text}（数据来自 Open-Meteo）。"
    except requests.RequestException:
        return f"{city}：天气服务暂时不可用（演示兜底：晴，15~25°C）。"


# ---------- 本地笔记 ----------
def _safe_title(title: str) -> str:
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


TOOLS = [calculator, get_current_time, get_weather, save_note, list_notes, read_note]


# ---------- 组装 Agent ----------
def build_agent():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 中配置 DEEPSEEK_API_KEY，参考 .env.example")

    model = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=api_key,
        temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0")),
    )

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()

    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        name="deepseek_personal_assistant",
    )


def thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def get_final_answer(result: dict) -> str:
    """从 agent 返回的消息列表里取最后一条纯文本回复。"""
    for message in reversed(result["messages"]):
        if getattr(message, "content", None) and not getattr(message, "tool_calls", None):
            return message.content
    return ""
