# 卷宗 — 隐私优先的本地长文档智能工作台

2026 iFLYTEK AI开发者大赛 · Spark-X2.5端侧模型创新挑战赛 参赛作品。

在本地设备上完全离线运行：整卷装载资料（利用 Spark-X2.5 原生 1M 上下文），
双模型协作（1.7B 常驻快答 + 4B 深度审阅），回答带出处溯源，数据不出设备。

## 目录结构

```
juanzong/
├─ src/
│  ├─ config.py      # 全局配置（模型路径、上下文长度、路由阈值）
│  ├─ inference.py   # 推理封装：双模型懒加载 + 思考档位 + 性能埋点   [开发A]
│  ├─ retrieval.py   # 资料解析与混合检索                            [开发B]
│  ├─ router.py      # 双模型路由 + 端到端问答                       [开发B]
│  └─ app.py         # Gradio 离线界面
├─ scripts/
│  └─ bench_thinking_tiers.py  # 思考档位消融基准（产出 CSV）        [开发A跑, 成员C用]
├─ docs/
│  ├─ week1-deploy-checklist.md # 开发A 第1周部署验证清单（先看这个！）
│  └─ bench_result.csv          # 基准数据输出
├─ data/             # 测试资料库（成员C放入案卷/文档）
└─ models/           # 量化模型权重（不入库）
```

## 快速开始

推理后端：Ollama（>= 0.34.1，原生支持 spark2_5）

```bash
# 1) 安装 Ollama：https://ollama.com/download 下载 OllamaSetup.exe 安装
# 2) 拉取量化模型（各一次，之后可断网运行）
ollama pull SparkLLM/Spark-X2.5-1.7B
ollama pull SparkLLM/Spark-X2.5-4B
# 3) 安装应用依赖
cd juanzong
C:/Users/54780/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install -r requirements.txt
# 4) 启动
python src/app.py
```

应用依赖已装好的环境（venv）：`C:/Users/54780/.workbuddy/binaries/python/envs/default`
启动应用：`C:/Users/54780/.workbuddy/binaries/python/envs/default/Scripts/python.exe src/app.py`

## 第一周分工速查

- 开发A：`docs/week1-deploy-checklist.md` 逐项打勾（Day5 里程碑 = 断网跑通 UI）
- 开发B：retrieval.py / router.py 中的 TODO(B-1)~(B-4)
- 成员C：往 `data/` 放测试案卷；等 A-5 数据出来填消融表
- 成员D：PPT 大纲 + Demo 视频脚本
- 成员E：2 位真实用户访谈；README/部署文档完善
