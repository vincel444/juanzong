"""消融基准脚本：2(模型) x 2(思考档位) 矩阵跑同一批问题，输出对比 CSV。

用法：先启动推理后端（Ollama），然后
    python scripts/bench_thinking_tiers.py
产出：docs/bench_result.csv（成员C直接填消融实验表）
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import LARGE_BASE_URL, LARGE_MODEL, SMALL_BASE_URL, SMALL_MODEL  # noqa: E402
from inference import Tier, chat  # noqa: E402

QUESTIONS = [
    "这份资料的用途是什么？请一句话概括。",
    "资料里提到了哪些时间节点或期限？",
    "对比资料中各方案的优缺点，并给出你的评估。",
    "找出资料中所有存在风险或表述模糊的条款，逐条分析。",
]

COMBOS = [
    ("1.7B+关思考", SMALL_MODEL, SMALL_BASE_URL, Tier.LOW),
    ("1.7B+开思考", SMALL_MODEL, SMALL_BASE_URL, Tier.MEDIUM),
    ("4B+关思考", LARGE_MODEL, LARGE_BASE_URL, Tier.LOW),
    ("4B+开思考", LARGE_MODEL, LARGE_BASE_URL, Tier.HIGH),
]

OUT = Path(__file__).resolve().parent.parent / "docs" / "bench_result.csv"


def main() -> None:
    rows = []
    for label, model, base_url, tier in COMBOS:
        for q in QUESTIONS:
            try:
                r = chat(model, base_url, [{"role": "user", "content": q}], tier,
                         max_tokens=1024)
                rows.append([label, q, r.latency_ms, r.prompt_tokens, r.eval_tokens,
                             len(r.text), len(r.thinking), r.text[:200]])
            except Exception as e:
                rows.append([label, q, "ERR", "", "", "", "", str(e)[:200]])
            print(f"  done: {label} | {q[:20]}...")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["组合", "问题", "时延ms", "输入tok", "输出tok", "回答字数", "思考字数", "回答摘录/错误"])
        w.writerows(rows)
    print(f"完成，结果写入 {OUT}")
    print("TODO(成员C): 补充回答质量人工评分列（1-5分），生成消融对比图表")


if __name__ == "__main__":
    main()
