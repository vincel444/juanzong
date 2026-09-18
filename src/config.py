"""全局配置：后端服务、模型名、性能与路由参数。

后端采用 Ollama（原生 spark2_5 支持需 Ollama >= 0.34.1）。
量化版模型通过以下命令获取（一次即可，之后断网可跑）：
    ollama pull SparkLLM/Spark-X2.5-1.7B
    ollama pull SparkLLM/Spark-X2.5-4B
如改用 llama-server / vLLM / SGLang，只需修改 BASE_URL 与模型名。
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---- 后端服务 ----
# 路线A（推荐，待网络允许）：Ollama >= 0.34.1 原生 spark2_5，两模型共用 11434
# 路线B（当前可用）：scripts/serve_transformers.py 自建服务，直接加载本地 HF 权重
#   1.7B 服务 -> 127.0.0.1:11435    4B 服务 -> 127.0.0.1:11436
SMALL_BASE_URL = "http://127.0.0.1:11435"
LARGE_BASE_URL = "http://127.0.0.1:11436"

SMALL_MODEL = "Spark-X2.5-1.7B"     # 常驻：快速应答
LARGE_MODEL = "Spark-X2.5-4B"       # 按需：跨文档深度推理

BACKEND_STYLE = "openai"            # "openai"（自建服务）| "ollama"（Ollama 原生 /api/chat）

# 官方推荐采样参数（见模型 README Benchmarks 一节）
GEN_KWARGS = {"temperature": 1.0, "top_p": 0.95}

# 请求超时：4B 高档思考可能较慢
TIMEOUT_SECONDS = 300

# ---- 本地已下载的 HF 原始权重（备用路线：转 GGUF 或 transformers 直跑）----
HF_4B_DIR = Path(r"G:/私/科大讯飞/Spark-X2.5-4B")
HF_17B_DIR = Path(r"G:/私/科大讯飞/Spark-X2.5-1.7B")

# ---- 本地资料库 ----
DATA_DIR = PROJECT_ROOT / "data"             # 测试案卷目录（成员C维护）
INDEX_PATH = PROJECT_ROOT / "data" / "index.sqlite"

# ---- 路由阈值：问题包含关键词或超长时走 4B 高档 ----
DEEP_KEYWORDS = ["对比", "审阅", "风险", "跨文档", "全部", "总结所有", "代码审查", "调用链"]
DEEP_MIN_CHARS = 60
