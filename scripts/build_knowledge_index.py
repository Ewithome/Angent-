"""构建知识库索引并输出统计信息。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge_base import build_knowledge_index  # noqa: E402


def main() -> None:
    file_count, chunk_count = build_knowledge_index()
    print(f"知识库文档数：{file_count}")
    print(f"语义分块数：{chunk_count}")
    print("索引构建完成")


if __name__ == "__main__":
    main()
