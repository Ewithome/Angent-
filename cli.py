"""DeepSeek 智能体命令行入口。"""
from __future__ import annotations

import argparse

from agent_core import build_agent, get_final_answer, thread_config


def main() -> None:
    # 命令行入口：支持 --thread 指定独立会话，方便测试多会话记忆
    parser = argparse.ArgumentParser(description="DeepSeek 智能体命令行助手")
    parser.add_argument("--thread", default="default", help="会话 ID，不同 ID 使用独立记忆")
    parser.add_argument(
        "--engine",
        choices=["langchain", "harness"],
        default="langchain",
        help="运行引擎：langchain 或 harness",
    )
    args = parser.parse_args()

    agent = build_agent() if args.engine == "langchain" else None
    config = thread_config(args.thread) if agent is not None else None
    print(f"会话 ID：{args.thread}，引擎：{args.engine}，输入 quit 退出\n")

    while True:
        try:
            question = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue

        if args.engine == "harness":
            from harness.agent import run_harness_chat

            reply = run_harness_chat(question, args.thread)
        else:
            # invoke 会把新消息和 SQLite 中的历史一起交给模型，实现多轮记忆
            result = agent.invoke(
                {"messages": [{"role": "user", "content": question}]},
                config=config,
            )
            reply = get_final_answer(result)
        print(f"小助手：{reply}\n")


if __name__ == "__main__":
    main()
