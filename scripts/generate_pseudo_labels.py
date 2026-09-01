"""使用 DeepSeek 从知识库文档生成伪标签问答对，用于后续检索调优。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from knowledge_base import list_chunks  # noqa: E402

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成伪标签问答对")
    parser.add_argument("--limit", type=int, default=5, help="最多处理的分块数")
    args = parser.parse_args()

    chunks = list_chunks()
    if not chunks:
        print("知识库为空，请先把文档放入 knowledge/ 目录")
        sys.exit(1)

    llm = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key=__import__("os").getenv("DEEPSEEK_API_KEY"),
        temperature=0.2,
    )

    output_dir = Path("eval")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "pseudo_labels.jsonl"
    count = 0

    with output_file.open("a", encoding="utf-8") as fh:
        for chunk in chunks[: args.limit]:
            text = chunk["text"][:800]
            prompt = (
                "根据下面的企业内部文档片段，生成 1 个员工可能会问的问题，"
                "只输出 JSON：{\"question\": \"...\"}，不要输出其他内容。\n\n"
                f"文档片段：\n{text}"
            )
            response = llm.invoke(prompt)
            try:
                question = json.loads(response.content)["question"]
            except Exception:  # noqa: BLE001
                continue
            record = {
                "source": chunk["source"],
                "question": question,
                "answer": text,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"已生成 {count} 条伪标签，保存到 {output_file}")


if __name__ == "__main__":
    main()
