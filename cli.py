"""DeepSeek 智能体命令行入口。"""
from __future__ import annotations

import argparse

from agent_core import build_agent, get_final_answer, thread_config


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek 智能体命令行助手")
    parser.add_argument("--thread", default="default", help="会话 ID，不同 ID 使用独立记忆")
    args = parser.parse_args()

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

        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )
        print(f"小助手：{get_final_answer(result)}\n")


if __name__ == "__main__":
    main()
