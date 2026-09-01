# RAG 评测与伪标签

本目录用于企业知识库问答的检索效果评测：

- `questions.json`：评测问题集，`expected` 为答案中应出现的关键词
- `pseudo_labels.jsonl`：由 `scripts/generate_pseudo_labels.py` 生成的伪标签问答对

运行评测：

```bash
python scripts/evaluate_rag.py
```

生成伪标签：

```bash
python scripts/generate_pseudo_labels.py --limit 5
```
