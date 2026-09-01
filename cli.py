"""DeepSeek 智能体命令行入口。"""
from __future__ import annotations

import argparse

from agent_core import build_agent, get_final_answer, thread_config


def main() -> None:
    # 命令行入口：支持 --thread 指定独立会话，方便测试多会话记忆
    parser = argparse.ArgumentParser(description="DeepSeek 智能体命令行助手")
    parser.add_argument("--thread", default="default", help="会话 ID，不同 ID 使用独立记忆")
    args = parser.parse_args()

    # 构建智能体并进入 REPL 循环
    agent = build_agent()
    config = thread_config(args.thread)
    print(f"会话 ID：{args.thread}，输入 quit 退出\n")

    while True:
        try:
            question = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue

        # invoke 会把新消息和 SQLite 中的历史一起交给模型，实现多轮记忆
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )
        print(f"小助手：{get_final_answer(result)}\n")


if __name__ == "__main__":
    main()
