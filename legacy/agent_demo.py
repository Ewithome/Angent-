"""LangChain 0.2 带工具 Agent 的最小 demo（DeepSeek）。

这是旧版 create_tool_calling_agent 写法，只保留作历史参考。
新版项目使用 LangChain v1 的 create_agent，见根目录 agent_core.py。

流程：用户提问 -> LLM 判断该调用哪个工具 -> 执行工具 -> 把结果交给 LLM 生成最终回答。
"""
import ast
import operator
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

# ---------- 1. 模型：DeepSeek（OpenAI 兼容接口） ----------
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)


# ---------- 2. 工具：定义模型可以调用的函数 ----------
# 用 ast 做安全求值，避免 eval 直接执行任意代码
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.BinOp):
        return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    raise ValueError(f"不支持的表达式: {ast.dump(node)}")


@tool
def calculator(expression: str) -> str:
    """计算一个数学表达式，例如 "2 + 3 * 4" 或 "(1 + 2) * 3"。参数是一个合法的算术表达式字符串。"""
    try:
        result = _eval(ast.parse(expression, mode="eval"))
        return str(result)
    except Exception as e:  # noqa: BLE001
        return f"计算出错: {e}"


@tool
def get_current_time() -> str:
    """获取当前日期和时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def get_weather(city: str) -> str:
    """查询某个城市的天气（演示用假数据）。参数是城市名，例如 "北京"。"""
    return f"{city}：今天晴，气温 15~25°C，空气质量良。"


tools = [calculator, get_current_time, get_weather]

# ---------- 3. 提示词 ----------
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一个乐于助人的助手，可以使用工具来回答问题。"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# ---------- 4. 组装 Agent ----------
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


def ask(question: str) -> str:
    return agent_executor.invoke({"input": question})["output"]


def main():
    examples = [
        "帮我算一下 (123 + 456) * 7 等于多少？",
        "现在几点了？",
        "北京今天天气怎么样？",
        "计算 3 的 8 次方，然后告诉我现在的时间。",
    ]
    for q in examples:
        print("=" * 60)
        print("问题：", q)
        print("回答：", ask(q))

    print("=" * 60)
    print("进入交互模式（输入 quit 退出）：")
    while True:
        try:
            q = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"quit", "exit", "q"}:
            break
        if q:
            print("回答：", ask(q))


if __name__ == "__main__":
    main()
