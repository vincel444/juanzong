# 开发A · 第1周端侧部署验证清单

> **路线更新（重要）**：应用代码已按 Ollama 后端重写完毕并冒烟通过，请改看
> `docs/backend-setup.md`。本清单中 A-2（模型下载）已完成（HF 原始权重在
> G:/私/科大讯飞/），其余 A-3~A-6 的验证目标不变，操作方式按 backend-setup.md。

目标：9/24 前跑通「1.7B + 4B 双模型在本机加载 → 单次问答」最小闭环，并拿到第一批性能数据。
每完成一项在 [ ] 里打 x，遇到问题记录在"备注"列。

## A-1 环境准备（Day 1）

- [ ] 确认机器配置：内存 ≥16GB、有无 NVIDIA 显卡（记下显存大小）____
- [ ] 安装 Python 3.10+（建议用 venv：`python -m venv .venv`）
- [ ] `pip install -r requirements.txt`（llama-cpp-python 若装不上，先装 CPU 版：`pip install llama-cpp-python`）
- [ ] 注册 HuggingFace，确认能访问 `https://huggingface.co/collections/XHToken/spark-x25`

## A-2 模型获取与量化（Day 1–2）

- [ ] 查看官方仓库 README：是否已提供 GGUF/量化版本（优先直接用官方量化，不要自己转）
- [ ] 下载 1.7B 量化版（Q4_K_M 优先）到 `juanzong/models/`
- [ ] 下载 4B 量化版到 `juanzong/models/`
- [ ] 若需自行转换：`transformers` 权重 → GGUF（用 llama.cpp 的 convert 脚本，记录转换命令）
- [ ] 更新 `src/config.py` 中的模型文件名

## A-3 推理栈接入（Day 2–3）

- [ ] 打开 `src/inference.py`，按 TODO(A-3) 启用 llama-cpp-python 加载代码
- [ ] 写一个 5 行测试脚本：加载 1.7B → 生成"你好" → 打印输出
- [ ] 1.7B 单测通过 [ ]；4B 单测通过 [ ]
- [ ] 官方若提供思考档位（thinking budget）API：查 README/源码，弄清档位如何传入（chat template 标记？生成参数？），记在这里：____

## A-4 档位与埋点（Day 3–4）

- [ ] 按 TODO(A-4) 在 generate() 中按 Tier 注入官方档位控制
- [ ] 确认 latency_ms / prompt_tokens 埋点正常返回
- [ ] 长上下文装载测试：把一份 5 万字文档整体塞进 prompt，记录：
  - [ ] 装载耗时 ____s；首 token 延迟 ____s；峰值内存/显存 ____GB
  - [ ] 再试 20 万字：是否可装载？参数需调整（n_ctx）吗？____

## A-5 消融基准初跑（Day 4–5）

- [ ] `python scripts/bench_thinking_tiers.py` 跑通，生成 `docs/bench_result.csv`
- [ ] 下载一个同尺寸对比模型（如 Qwen3-4B 的 GGUF Q4）重复 A-3/A-4，跑出对比数据
- [ ] 把两组数据交给成员C 填入消融实验表

## A-6 里程碑（Day 5）

- [ ] `python src/app.py` 打开 Gradio 界面，断网状态下完成一次"提问 → 带出处回答"
- [ ] 录一段 30 秒屏幕录像存到 `docs/`（决赛演示备份素材提前积累）

## 已知风险与对策

| 风险 | 对策 |
|---|---|
| 混合注意力架构 llama.cpp 不支持 | 第2天就要验证！若失败：查官方是否自带推理代码/ONNX 导出；仍不行立刻在比赛官方群求助，并准备 vLLM+大内存 PC 的降级路线 |
| 1M 上下文本机装不下 | 分级装载（整卷→章节），config 里 N_CTX 从 128K 起步逐级上调，如实记录数据 |
| 双模型同时驻留爆内存 | 代码已做懒加载：4B 用完可 `del` 释放，必要时只保 1.7B 常驻 |
