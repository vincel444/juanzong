# 给组员的测试上手指南（3 步跑起来）

> 前提：Windows 10/11 + NVIDIA 显卡（≥4GB 显存可只跑 1.7B；≥8GB 可双模型同驻）。
> 模型与推理引擎体积大，不入库，需按第 2 步单独下载（每项只下一次，之后可断网）。

## 1. 拉代码 + 装 Python 依赖（约 5 分钟）

```bash
git clone https://github.com/vincel444/juanzong.git
cd juanzong
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

注意：**不要**尝试 `pip install llama-cpp-python`（Windows 无预编译轮子、本地编译需 MSVC）。

## 2. 下载推理引擎与模型（约 15 分钟）

**① llama.cpp 预编译包**（CUDA 版，需 NVIDIA 驱动 ≥ 580）
直连 GitHub 失败时用镜像前缀 `https://ghfast.top/` 或 `https://gh-proxy.com/`：

- `llama-b11026-bin-win-cuda-13.4-x64.zip`（约 143MB）
- `cudart-llama-bin-win-cuda-13.4-x64.zip`（约 404MB）

两个包解压到**同一个目录**（例如 `C:/llama/`），确保 `llama-server.exe` 与 `cudart64_13.dll` 在同一层。

**② 官方 GGUF 量化模型**（HuggingFace 镜像）
- `https://hf-mirror.com/XHToken/Spark-X2.5-1.7B-GGUF/resolve/main/Spark-X2.5-1.7B-Q4_K_M.gguf`（1.1GB）
- `https://hf-mirror.com/XHToken/Spark-X2.5-4B-GGUF/resolve/main/Spark-X2.5-4B-Q4_K_M.gguf`（2.6GB）

放到 `juanzong/models/` 目录下。

## 3. 启动（两个终端）

```bash
# 终端1：启动双模型服务（若 llama.cpp 不在默认路径，加 --bin 参数）
python scripts/start_llama_servers.py --bin "C:/llama/llama-b11026-bin-win-cuda-13.4-x64"

# 终端2：启动应用界面
python src/app.py
```

浏览器打开终端2 提示的地址（默认 http://127.0.0.1:7860），点「检测模型服务」确认双模型可用，
然后把文档丢进 `data/` 目录即可提问。

## 常见问题

| 现象 | 处理 |
|---|---|
| 启动报找不到 llama-server.exe | `--bin` 路径要指到解压后的目录层级 |
| 显存不足 / CUDA out of memory | 改小 `-ngl`（如 20）或只启动 1.7B：`--only 17b` |
| 思考过程有内容但回答为空 | 已实现自动降级兜底；若仍出现，调大对应 max_tokens |
| 回答不引用出处 | 确认 `data/` 下有可解析文档（支持 pdf/docx/md/txt/代码） |
| 速度异常慢（几 tok/s） | 检查 `-ngl` 是否为 99；退到 CPU 会慢很多 |

## 性能参考（本机 RTX 5060 Laptop 8GB）

详见 `docs/speed-benchmark.md`：1.7B 122–146 tok/s、4B 63 tok/s、双驻 5.5GB 显存；
轻档问答 <1s，深档 30–50s。
