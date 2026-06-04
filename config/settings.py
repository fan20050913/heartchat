"""
配置管理模块
从 .env 文件加载所有 API Key 和配置项，提供全局单例 Settings。
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env：打包后从 exe 所在目录加载，开发模式从项目根目录加载
if getattr(sys, "frozen", False):
    env_path = Path(sys.executable).parent / ".env"
    template_path = Path(sys._MEIPASS) / ".env.template"
    # 首次运行：自动从模板生成 .env（key 为空，用户自行填写）
    if not env_path.exists() and template_path.exists():
        import shutil
        shutil.copy2(template_path, env_path)
    load_dotenv(env_path)
else:
    load_dotenv()


class Settings:
    """应用全局配置，所有值从环境变量 / .env 文件读取。"""

    # ── DeepSeek ──
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # ── 阿里云百炼（统一平台：ASR + TTS + Embedding） ──
    ALIYUN_API_KEY: str = os.getenv("ALIYUN_API_KEY", "")
    ALIYUN_BASE_URL: str = os.getenv("ALIYUN_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")

    # ── ASR（Phase 4） ──
    ASR_MODEL: str = os.getenv("ASR_MODEL", "paraformer-realtime-v2")

    # ── TTS（Phase 2） ──
    TTS_MODEL: str = os.getenv("TTS_MODEL", "cosyvoice-v2")
    TTS_VOICE: str = os.getenv("TTS_VOICE", "longxiaochun_v2")

    # ── 文本模型选择 ──
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-flash")

    MODEL_PRESETS = {
        "deepseek-flash": {
            "display": "DeepSeek V4 Flash + CosyVoice V2",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
        },
        "qwen3.5-flash": {
            "display": "Qwen 3.5 Flash + CosyVoice V2",
            "api_key_env": "ALIYUN_API_KEY",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3.5-flash",
        },
    }

    # ── 角色 ──
    CURRENT_CHARACTER: str = os.getenv("CURRENT_CHARACTER", "sakuya")

    # ── Embedding（Phase 3） ──
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")

    # ── 本地路径 ──
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
    XLSX_PATH: str = os.getenv("XLSX_PATH", "./data/source/zhubihua/朱比华知识库.xlsx")

    @classmethod
    def validate(cls) -> None:
        """启动时校验必要配置是否存在，缺少则抛 ValueError。"""
        missing = []
        if not cls.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY（DeepSeek API Key）")
        if not cls.ALIYUN_API_KEY:
            missing.append("ALIYUN_API_KEY（阿里云百炼 API Key）")
        if missing:
            hint = ""
            if getattr(sys, "frozen", False):
                hint = f"\n请在 {Path(sys.executable).parent / '.env'} 中填入你的 Key，或通过设置对话框配置。"
            else:
                hint = "\n请在项目根目录 .env 文件中填入你的 Key。"
            raise ValueError(
                ".env 缺少必要配置：\n  - " + "\n  - ".join(missing) + hint
            )


# 全局单例
settings = Settings()

# 打包后：资源路径与数据路径分不同基准
if getattr(sys, "frozen", False):
    from utils.resource_helper import base_dir, data_dir
    # XLSX 是打包在 _internal/ 中的只读资源
    settings.XLSX_PATH = str(base_dir() / Path(settings.XLSX_PATH))
    # VectorStore 是运行时创建的持久数据，放 exe 同级目录
    settings.VECTOR_STORE_PATH = str(data_dir() / Path(settings.VECTOR_STORE_PATH))
