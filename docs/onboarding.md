# 给组员的测试上手指南（3 步跑起来）

> 前提：Windows 10/11 + NVIDIA 显卡（显存 ≥4GB 即可先跑 1.7B；4B 建议 ≥8GB）。
> 模型权重不入库，需单独下载（见第 2 步）。

## 1. 装环境（约 10 分钟）

```bash
git clone https://github.com/<ACCOUNT>/juanzong.git
cd juanzong

# 用任意 Python 3.10+，或直接用现成 venv
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install "transformers==4.57.1" accelerate fastapi uvicorn
```

注意：**transformers 必须是 4.57.1**（更高版本与模型自定义代码不兼容）。

## 2. 下载模型权重（联网一次，约 11GB）

从 HuggingFace 下载两个模型仓库到本地任意目录（如 `D:/models/`）：
- https://huggingface.co/XHToken/Spark-X2.5-1.7B
- https://huggingface.co/XHToken/Spark-X2.5-4B

需要下载的文件：全部 `model-*.safetensors` + `config.json`、`tokenizer.json`、
`tokenizer_config.json`、`vocab.json`、`merges.txt`、`chat_template.jinja`、
`generation_config.json`、`configuration_spark.py`、`modeling_spark.py`、`special_tokens_map.json`。

国内加速：`HF_ENDPOINT=https://hf-mirror.com huggingface-cli download XHToken/Spark-X2.5-1.7B`

## 3. 启动（两个推理服务 + 一个界面）

```bash
# 终端1：1.7B 常驻服务
python scripts/serve_transformers.py --model "D:/models/Spark-X2.5-1.7B" --port 11435

# 终端2：4B 深度服务（可后启动）
python scripts/serve_transformers.py --model "D:/models/Spark-X2.5-4B" --port 11436

# 终端3：应用界面
python src/app.py
```

浏览器打开 http://127.0.0.1:11435 对应服务健康检查；应用界面地址见终端输出（默认 7860）。
点击界面"检测模型服务"确认双模型可用，然后往 `data/` 丢文档即可提问。

## 常见问题

| 现象 | 处理 |
|---|---|
| 启动报 rope_parameters 相关错误 | transformers 版本不是 4.57.1 |
| 请求报 top_k -1 错误 | 拉取最新代码（已修复） |
| 4B 很慢 | 显存不足触发 CPU offload，属预期；可等 GGUF 量化版 |
| 显存不够 8GB | 只跑 1.7B 服务，应用仍可用（4B 档会提示未启动） |

## 项目结构

见 [README.md](README.md)；分工与开发规范见 `docs/`。
