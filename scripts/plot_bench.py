"""消融实验出图（P0-#4）：把实测基准数据画成 PPT 可直接引用的图表。

数据来源：docs/speed-benchmark.md（2026-09-18，RTX 5060 Laptop 8GB 实测）。
若重跑 scripts/bench_thinking_tiers.py 得到新的 docs/bench_result.csv，
可补充逐题数据；本图先使用实测汇总数据，保证随时可出图。

用法：
    python scripts/plot_bench.py
产出：
    docs/bench_chart.png   2x2 四宫格（速度对比 / 三档时延 / 消融证据 / 显存）
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "bench_chart.png"

# Windows 中文黑体（存在性在运行时校验，缺失时退回英文标签）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ---- 实测汇总数据（docs/speed-benchmark.md）----
ROUTES = ["transformers\n(bf16 原始权重)", "llama.cpp\n(Q4_K_M 量化)"]
SPEED_17B = [3.5, 134]   # tok/s，122-146 取中值
SPEED_4B = [1.0, 63]     # tok/s，transformers 4B 部分层 offload 约 1

TIERS = ["轻档 1.7B\n关思考", "中档 1.7B\n开思考(降级后)", "深档 4B\n开思考"]
TIER_LATENCY = [0.4, 2.0, 43.5]
TIER_ERR = [0, 0, 4.5]   # 深档 39-48s 取中值 ±4.5

ABLATE_LABELS = ["1.7B 开思考", "4B 开思考"]
THINK_CHARS = [5027, 3073]
ANSWER_CHARS = [0, 1311]

MEM_LABELS = ["transformers\n1.7B 单模型", "llama.cpp\n双模型同驻"]
MEM_GB = [3.7, 5.5]
VRAM_TOTAL = 8.0

C_BLUE, C_RED, C_GREEN, C_GRAY = "#2563eb", "#dc2626", "#16a34a", "#9ca3af"


def _style(ax, title):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)


def plot_summary() -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle("Spark-X2.5 端侧推理 · 消融与性能实测（RTX 5060 Laptop 8GB，2026-09-18）",
                 fontsize=13, fontweight="bold")

    # ① 两条技术路线：量化带来的速度提升（35-60 倍）
    ax = axes[0][0]
    x = range(len(ROUTES))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], SPEED_17B, w, label="1.7B", color=C_BLUE)
    b2 = ax.bar([i + w / 2 for i in x], SPEED_4B, w, label="4B", color=C_RED)
    ax.set_yscale("log")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():g}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x), ROUTES)
    ax.set_ylabel("生成速度 tok/s（对数轴）")
    ax.legend(frameon=False)
    _style(ax, "① 技术路线：GGUF 量化提速 35–60 倍")

    # ② 三档自适应实测时延
    ax = axes[0][1]
    colors = [C_GREEN, C_BLUE, C_RED]
    bars = ax.bar(TIERS, TIER_LATENCY, yerr=TIER_ERR, capsize=4,
                  color=colors, alpha=0.85)
    for b, v in zip(bars, TIER_LATENCY):
        ax.annotate(f"{v:g}s", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("端到端时延 s")
    ax.set_ylim(0, 52)
    _style(ax, "② 三档自适应：快问 <1s，深审 ~40s")

    # ③ 消融证据：1.7B 思考档"过度思考"
    ax = axes[1][0]
    x = range(len(ABLATE_LABELS))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], THINK_CHARS, w, label="思考消耗(字)", color=C_GRAY)
    b2 = ax.bar([i + w / 2 for i in x], ANSWER_CHARS, w, label="正式回答(字)", color=C_GREEN)
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{int(b.get_height())}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x), ABLATE_LABELS)
    ax.set_ylabel("字数")
    ax.legend(frameon=False)
    _style(ax, "③ 消融证据：1.7B 思考档想不停 → 深档必须 4B")

    # ④ 显存占用：双模型同驻消费级显卡
    ax = axes[1][1]
    bars = ax.bar(MEM_LABELS, MEM_GB, color=[C_BLUE, C_GREEN], alpha=0.85, width=0.5)
    ax.axhline(VRAM_TOTAL, color=C_RED, linestyle="--", linewidth=1.2)
    ax.annotate("8GB 显存上限", (0.02, VRAM_TOTAL), xycoords=("axes fraction", "data"),
                va="bottom", color=C_RED, fontsize=9)
    for b, v in zip(bars, MEM_GB):
        ax.annotate(f"{v}GB", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("显存 GB")
    ax.set_ylim(0, 9)
    _style(ax, "④ 显存：1.7B+4B 同驻仅 5.5GB，消费级 8GB 可跑")

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)
    plt.close(fig)
    return OUT


if __name__ == "__main__":
    fonts_ok = any(
        (Path("C:/Windows/Fonts") / f).exists()
        for f in ("msyh.ttc", "simhei.ttf")
    )
    if not fonts_ok:
        print("提示：未找到微软雅黑/黑体，中文可能显示为方框")
    path = plot_summary()
    print(f"完成：{path}")
    sys.exit(0)
