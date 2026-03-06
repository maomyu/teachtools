"""
应用配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量 - 指定.env文件路径
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_FILE)


class Settings:
    """应用配置类"""

    # 项目根目录
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # API配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # 数据库
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{BASE_DIR}/database/teaching.db"
    )

    # 文件路径
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "./data/raw"))
    PROCESSED_DIR: Path = Path(os.getenv("PROCESSED_DIR", "./data/processed"))
    RAW_PAPERS_DIR: Path = Path(os.getenv(
        "RAW_PAPERS_DIR",
        str(BASE_DIR / "2022-2025北京市各区各学校试题汇总")
    ))

    # 日志
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __post_init__(self):
        """确保目录存在"""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        (self.BASE_DIR / "database").mkdir(parents=True, exist_ok=True)
        (self.BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)


settings = Settings()
