# 卷宗 — 隐私优先的本地长文档智能工作台

2026 iFLYTEK AI开发者大赛 · Spark-X2.5端侧模型创新挑战赛 参赛作品。

在本地设备上完全离线运行：整卷装载资料（利用 Spark-X2.5 原生 1M 上下文），
**三档自适应**（1.7B 快答 / 1.7B 推理 / 4B 深度审阅），回答带出处溯源，数据不出设备。

## 关键指标（RTX 5060 Laptop 8GB 实测）

| 指标 | 数值 |
|---|---|
| 1.7B 推理速度 | 122–146 tok/s（llama.cpp Q4_K_M，GPU 全层卸载） |
| 4B 推理速度 | 63 tok/s |
| 双模型同驻显存 | 5.5 GB / 8.1 GB |
| 轻档问答时延 | 0.4–2.0 s |
| 深档深度审阅 | 30–50 s（含 3000+ 字思考） |

> 相比官方 HF 权重的 transformers 直跑（1.7B 仅 3.5 tok/s），llama.cpp 路线提速 **35–60 倍**。
> 详见 `docs/speed-benchmark.md`。

## 目录结构

```
juanzong/
├─ src/
│  ├─ config.py      # 服务地址、模型名、路由阈值
│  ├─ inference.py   # 推理客户端：三档思考 + 性能埋点（OpenAI 兼容）
│  ├─ retrieval.py   # 资料解析（pdf/docx/md/代码）+ 整卷装载 + 检索兜底
│  ├─ router.py      # 三档自适应路由 + 智能降级兜底
│  └─ app.py         # Gradio 离线界面（显示档位/时延/出处/思考过程）
├─ scripts/
│  ├─ start_llama_servers.py   # 一键启动双模型服务（推荐）
│  ├─ bench_thinking_tiers.py  # 消融基准：{1.7B,4B} x {开/关思考} -> CSV
│  ├─ serve_transformers.py    # 备用：transformers 直跑服务
│  └─ serve_gguf.py            # 备用：llama-cpp-python 版服务
├─ docs/
│  ├─ onboarding.md            # 组员上手指南（先看这个）
│  ├─ backend-setup.md         # 推理后端搭建详解
│  ├─ speed-benchmark.md       # 性能实测与消融发现
│  └─ week1-deploy-checklist.md
├─ data/             # 测试资料库
└─ models/           # GGUF 量化模型（不入库）
```

## 快速开始

```bash
cd juanzong
pip install -r requirements.txt

# 终端1：启动双模型服务（需先下载 llama.cpp + GGUF，见 docs/onboarding.md）
python scripts/start_llama_servers.py --bin "C:/llama/llama-b11026-bin-win-cuda-13.4-x64"

# 终端2：启动应用
python src/app.py
```
