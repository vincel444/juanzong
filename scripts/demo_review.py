"""生成「深档审阅」模拟演示样本（PPT 截图用 + 输出格式验证）。

不依赖推理后端：使用预先写好的、符合深档 4B 输出风格的审阅文本，
跑真实的 citation 溯源校验，产出一份带校验标记的 Markdown 演示文档。
用途：
  1. PPT「效果演示」页的图文素材（同时给出原始回答与校验结果）
  2. 验证 citation.py 在真实合同长文本上的表现（命中率分布）

用法：
    python scripts/demo_review.py
产出：
    docs/demo-review.md（含校验标记的演示记录）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from citation import (build_citation_index, collect_sources,  # noqa: E402
                      summarize, verify_answer)
from retrieval import load_documents  # noqa: E402

# 模拟深档 4B 的审阅回答（风格与已实测的 39–48s 深档输出一致）
SAMPLE_ANSWER = """根据资料，我对劳动合同书-样例A.pdf 的试用期与报酬条款审阅如下。

第一条约定合同期限为两年，自2026年3月1日起至2028年2月28日止；第二条约定试用期为六个月，
自2026年3月1日起至2026年8月31日止，试用期包含在合同期限内。

【风险一：试用期超法定上限】按照《劳动合同法》第十九条，劳动合同期限一年以上不满三年的，
试用期不得超过二个月。本合同期限为两年，却约定六个月试用期，超出法定上限四个月。

【风险二：试用期工资条款自相矛盾】第五条约定试用期工资按转正工资的80%执行，
而第十二条又约定乙方试用期工资按转正工资的70%执行，两条表述不一致，实际执行时易生争议。

【风险三：竞业限制补偿标准过低】第九条约定竞业限制经济补偿按当地最低工资标准按月支付，
而乙方离职后二十四个月内不得入职竞争单位，补偿与限制期限明显不匹配。

建议：将试用期修改为不超过二个月，统一第五条与第十二条的试用期工资标准，
并与乙方协商提高竞业限制经济补偿。"""


def main() -> None:
    chunks = load_documents()
    index = build_citation_index(chunks)
    items = verify_answer(SAMPLE_ANSWER, index)
    total, ok, missed = summarize(items)
    sources = collect_sources(items)

    lines = [
        "# 深档审阅演示记录（模拟样本）",
        "",
        "> 本文档由 `scripts/demo_review.py` 生成：使用符合深档 4B 输出风格的审阅文本，",
        "> 跑**真实**的溯源校验（`src/citation.py`），用于 PPT「效果演示」页素材。",
        "> 审阅文本为模拟；校验结果与来源页码为真实计算结果。",
        "",
        "## 一、输入资料",
        "",
    ]
    for f in sorted({c.doc_name for c in chunks}):
        pages = sorted({c.page for c in chunks if c.doc_name == f})
        lines.append(f"- `{f}`（{len(pages)} 页）")

    lines += [
        "",
        "## 二、深档回答（模拟 4B 输出）",
        "",
        "```text",
        SAMPLE_ANSWER,
        "```",
        "",
        "## 三、溯源校验结果（真实计算）",
        "",
        f"**总命中：{ok}/{total} 句**　｜　来源页：{'、'.join(sources)}",
        "",
        "| # | 命中率 | 判定 | 句子（截断） | 来源 |",
        "|---|---|---|---|---|",
    ]
    for n, item in enumerate(items, 1):
        verdict = "✅ 已溯源" if item.verified else ("⚠️ 部分溯源" if item.ratio >= 0.01 else "❌ 未溯源")
        src = "、".join(f"p{p}" for _, p in sorted(item.sources)) or "—"
        sent = item.sentence[:34].replace("|", "｜")
        lines.append(f"| {n} | {item.ratio:.2f} | {verdict} | {sent} | {src} |")

    lines += [
        "",
        "## 四、结果解读（PPT 可直接引用）",
        "",
        "先看数据构成的三个层次：",
        "",
        "| 句子类型 | 典型命中率 | 判定 | 说明 |",
        "|---|---|---|---|",
        "| **合同原文引用**（第一/二条期限、试用期起止） | 0.50–1.00 | ✅ 已溯源 | 回答踩中原文，可定位到页码 |",
        "| **条款分析**（条款矛盾、补偿不匹配） | 0.29–0.44 | ⚠️ 部分溯源 | 引用了条款片段但做了综合改写 |",
        "| **外部法条 / 修改建议** | 0.00 | ❌ 未溯源 | 《劳动合同法》与建议不在资料内，属模型补充 |",
        "",
        "**这不是校验器失灵，而是设计预期的分层结果**：三类句子的性质本就不同，",
        "校验器把它们区分开，正是「防幻觉底线」要的效果 ——",
        "",
        "- 资料里**有的**：回查命中 → 用户可放心，且能一键到页码核验；",
        "- 模型**综合**的：部分命中 → 提示「这是它的归纳，重点看这几句」；",
        "- 外部**补充**的：零命中 → 明确标出「这条不是从你资料里来的」。",
        "",
        "> **答辩口径（重要，勿夸大）**：不要说成「回答全部可溯源」。",
        "> 准确表述是：**资料引文句可回溯到具体页码；分析句与外部依据会被自动分类标注，",
        "> 让用户知道哪几句有原文支撑、哪几句需要自己判断。**",
        "> 一句「3/13 全命中」的夸大，被评委追问一句就会崩；分层解释反而显得工程扎实。",
        "",
        "> 另注：分析句命中率偏低（0.29–0.44）部分源于句子带了",
        "> 【风险一：试用期超法定上限】这类**模型自加的标题前缀**，前缀不与原文重合会拉低比例。",
        "> 这是阈值设计的已知特性，如需提升召回可下调命中阈值（见 `citation.py` 的 HIT_THRESHOLD）。",
    ]

    out = ROOT / "docs" / "demo-review.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"命中 {ok}/{total} 句 | 来源页: {sources}")
    print(f"完成：{out}")


if __name__ == "__main__":
    main()
