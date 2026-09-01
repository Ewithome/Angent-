"""RAG 检索效果评测：Hit@1/3/5 与 MRR，并输出评测报告。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge_base import retrieve  # noqa: E402


def _hit_at(rank: int, results: list[dict], expected: list[str]) -> bool:
    if rank > len(results):
        return False
    text = results[rank - 1]["text"]
    return any(keyword in text for keyword in expected)


def main() -> None:
    eval_file = Path("eval/questions.json")
    if not eval_file.exists():
        print("未找到 eval/questions.json")
        sys.exit(1)

    cases = json.loads(eval_file.read_text(encoding="utf-8"))
    hit1 = hit3 = hit5 = 0
    mrr_sum = 0.0
    details = []

    for case in cases:
        results = retrieve(case["query"], top_k=5)
        expected = case["expected"]
        reciprocal_rank = 0.0
        for rank, item in enumerate(results, start=1):
            if any(keyword in item["text"] for keyword in expected):
                reciprocal_rank = 1 / rank
                break

        h1 = _hit_at(1, results, expected)
        h3 = _hit_at(3, results, expected)
        h5 = _hit_at(5, results, expected)
        hit1 += int(h1)
        hit3 += int(h3)
        hit5 += int(h5)
        mrr_sum += reciprocal_rank
        details.append(
            {
                "query": case["query"],
                "hit_at_1": h1,
                "hit_at_3": h3,
                "hit_at_5": h5,
                "mrr": round(reciprocal_rank, 4),
                "top_source": results[0]["source"] if results else "",
            }
        )

    total = len(cases)
    report = {
        "total_questions": total,
        "hit_at_1": round(hit1 / total, 4),
        "hit_at_3": round(hit3 / total, 4),
        "hit_at_5": round(hit5 / total, 4),
        "mrr": round(mrr_sum / total, 4),
        "details": details,
    }

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    report_file = output_dir / "eval_report.json"
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"评测报告已保存：{report_file}")


if __name__ == "__main__":
    main()
