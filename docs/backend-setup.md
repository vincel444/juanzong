# 推理后端搭建指南

> 现状（2026-09-18）：本机网络代理拦截 Ollama 官网/GitHub/winget 下载，但 PyPI 可用，
> 且官方 HF 权重已下载到本地。因此**当前主路线 = transformers 直跑本地权重（路线B）**；
> Ollama（路线A）作为后续可选优化。

## 路线B（当前可用）：transformers 自建服务

模型自定义架构（`modeling_spark.py`），需 `transformers>=4.57.1` + `trust_remote_code`。

1. **安装依赖**（已执行，如重装环境时使用）
   ```
   C:/Users/54780/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install -r requirements.txt
   C:/Users/54780/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
   C:/Users/54780/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install "transformers>=4.57.1" accelerate fastapi uvicorn
   ```

2. **启动双模型服务**（两个终端）
   ```
   python scripts/serve_transformers.py --model "G:/私/科大讯飞/Spark-X2.5-1.7B" --port 11435
   python scripts/serve_transformers.py --model "G:/私/科大讯飞/Spark-X2.5-4B" --port 11436
   ```

3. **启动应用**
   ```
   python src/app.py
   ```

### 显存说明（RTX 5060 Laptop 8GB）

- 1.7B bf16 ≈ 3.4GB：可整卡运行，响应快
- 4B bf16 ≈ 8GB：`device_map="auto"` 会把部分层 offload 到内存，速度较慢——**属预期，
  消融数据如实记录**。优化路径：llama.cpp `convert_hf_to_gguf.py` 转 Q4 量化
  （llama.cpp b10828+ 原生支持 spark2_5），量化后 4B≈2.5GB 可整卡运行
- 网络允许后可换 Ollama（>=0.34.1 原生 spark2_5）：`ollama pull SparkLLM/Spark-X2.5-1.7B`、
  `SparkLLM/Spark-X2.5-4B`，然后把 `src/config.py` 的 `BACKEND_STYLE` 改为 `"ollama"`
  并将两个 BASE_URL 指向 11434

## 思考档位机制（消融实验核心开关）

- Spark-X2.5 chat template 默认开启 thinking
- OpenAI 兼容后端：请求体 `chat_template_kwargs.enable_thinking`（src/inference.py 已封装）
- Ollama 后端：请求体 `think: true/false`
- 消融矩阵 {1.7B,4B} x {关思考,开思考}：`scripts/bench_thinking_tiers.py` 一键跑完
