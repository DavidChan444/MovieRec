"""
应用配置
"""
from pydantic_settings import BaseSettings
from typing import List
import os

# Compute project root relative to this file (app/core/config.py -> project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    # 基础配置
    APP_NAME: str = "AI电影推荐系统"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = f"sqlite:///{_PROJECT_ROOT}/movie_recommender.db"

    # OpenAI配置
    OPENAI_API_KEY: str = "sk-Tte95be6d2d6a048fa7b71ed2bc48c9ea2aca85e687q1q8p"
    OPENAI_BASE_URL: str = "https://api.gptsapi.net/v1"
    OPENAI_MODEL: str = "gpt-3.5-turbo"

    # JWT配置
    SECRET_KEY: str = "123456"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 * 24 * 60  # 30天

    # Chroma向量数据库配置
    CHROMA_PERSIST_DIRECTORY: str = os.path.join(_PROJECT_ROOT, "chroma_db")

    # 用户行为分析配置
    MIN_INTERACTIONS_FOR_LEARNING: int = 5  # 最少交互次数开始学习
    PREFERENCE_DECAY_DAYS: int = 30  # 偏好衰减天数
    BEHAVIOR_WEIGHT_CONFIG: dict = {
        "view": 1.0,
        "cancel_view": -1.0,
        "like": 3.0,
        "cancel_like": -3.0,
        "dislike": -2.0,
        "cancel_dislike": 2.0,
        "share": 2.0,
        "search": 1.5,
        "click": 0.5
    }

    # 推荐配置
    RECOMMENDATION_MODELS: List[str] = ["collaborative", "content_based", "hybrid", "langchain"]
    DEFAULT_RECOMMENDATION_MODEL: str = "hybrid"

    class Config:
        env_file = os.path.join(_PROJECT_ROOT, ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()