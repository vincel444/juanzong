# 推理后端搭建指南（llama.cpp 路线 · 当前方案）

> 结论先行：**必须用官方 GGUF + llama.cpp**。官方 HF 权重的 transformers 路线只有约 3.5 tok/s
> （1.7B）/ 1 tok/s（4B），因为官方 `modeling_spark.py` 只实现了 eager attention（手写 matmul +
> fp32 softmax），GPU 完全跑不出应有速度。换成 llama.cpp 后 **1.7B 达 122–146 tok/s、4B 达 63 tok/s，
> 提速约 35–60 倍**，双模型同驻仅占 5.5GB 显存。

## 一、组件与版本

| 组件 | 版本/说明 |
|---|---|
| llama.cpp 预编译包 | `llama-b11026-bin-win-cuda-13.4-x64.zip`（b10828+ 原生支持 spark2_5） |
| CUDA 运行时 | `cudart-llama-bin-win-cuda-13.4-x64.zip`（含 cudart64_13.dll / cublas64_13.dll） |
| GGUF 模型 | 官方 `XHToken/Spark-X2.5-1.7B-GGUF`、`XHToken/Spark-X2.5-4B-GGUF` 的 Q4_K_M |
| 显卡驱动 | 592.27（CUDA 13.x 需较新驱动；sm_120 需 CUDA 12.8+ 的工具链） |

本机已放置路径：
- llama.cpp：`C:/Users/54780/.workbuddy/bin/llama/llama-b11026-bin-win-cuda-13.4-x64/`
- GGUF：`juanzong/models/Spark-X2.5-{1.7B,4B}-Q4_K_M.gguf`

## 二、获取方式（网络受限环境）

GitHub 直连被拦截，以下两个镜像可用：
- `https://ghfast.top/<原GitHub链接>`
- `https://gh-proxy.com/<原GitHub链接>`

GGUF 模型从 HF 镜像下载：`https://hf-mirror.com/XHToken/Spark-X2.5-1.7B-GGUF/resolve/main/<文件名>`

> 不要尝试本地编译 llama-cpp-python：本机只有 MinGW GCC 8.1（std::filesystem 有 bug）且无 MSVC，
> 编译必然失败；PyPI 上也没有 Windows 预编译轮子。

## 三、启动（两条命令）

```bash
# 一键启动双模型服务（1.7B -> 11435，4B -> 11436，均为 GPU 全层卸载）
python scripts/start_llama_servers.py

# 另开终端启动应用界面
python src/app.py
```

手动启动（等价）：

```bash
cd C:/Users/54780/.workbuddy/bin/llama/llama-b11026-bin-win-cuda-13.4-x64
./llama-server.exe -m "G:/私/新建文件夹/星火ai应用/juanzong/models/Spark-X2.5-1.7B-Q4_K_M.gguf" \
  --port 11435 -ngl 99 -c 32768 -t 8 --jinja
```

关键参数说明：
- `-ngl 99`：全部层放 GPU（显存不足时调小，如 `-ngl 20`）
- `--jinja`：**必须加**，否则 `chat_template_kwargs`（思考档位开关）不生效
- `-c`：上下文长度；显存受限时先给 16K–32K，官方上限 1M
- 双模型同驻实测显存 5.5GB / 8GB，8GB 显卡可承受

## 四、思考档位（三档自适应的实现基础）

官方 chat template 只提供 `enable_thinking` 开/关两个状态，应用层据此组合出三档：

| 档位 | 模型 | enable_thinking | 实测时延 |
|---|---|---|---|
| 轻档 | 1.7B | false | 0.4–2.0 s |
| 中档 | 1.7B | true | 数秒～20 s（思考超限时自动降级为轻档重试） |
| 深档 | 4B | true | 30–50 s（深度审阅） |

调用方式（`src/inference.py` 已封装）：
```json
{"chat_template_kwargs": {"enable_thinking": true}}
```
llama-server 会把思考内容放在 `reasoning_content`，正式回答放在 `content`。

## 五、备用路线（网络恢复后可选）

- **Ollama**（>=0.34.1 原生支持）：`ollama pull SparkLLM/Spark-X2.5-4B`，把 `src/config.py` 的
  `BACKEND_STYLE` 改为 `"ollama"`、两个 BASE_URL 指向 11434
- **transformers 直跑**（`scripts/serve_transformers.py`）：需 `transformers==4.57.1`
  （更高版本与模型自定义 config 不兼容）、`generation_config.top_k` 需置 0；速度差，仅作兼容兜底
