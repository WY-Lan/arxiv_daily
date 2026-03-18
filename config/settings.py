"""
Configuration settings for arxiv daily push system.
"""
import os
from pathlib import Path
from typing import Optional, Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMProviderConfig:
    """LLM provider configurations."""

    # Alibaba Bailian (阿里百炼)
    BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Model recommendations for different agents
    MODEL_RECOMMENDATIONS = {
        "selection": "qwen-max",      # 论文筛选 - 需要深度分析
        "summary": "qwen-max",        # 内容生成 - 需要高质量输出
        "publisher": "qwen-plus",     # 平台发布 - 平衡性能和速度
        "default": "qwen-plus",
    }

    # Available models
    AVAILABLE_MODELS = [
        "qwen-max",           # 最强能力，复杂任务
        "qwen-max-longcontext",  # 长上下文版本
        "qwen-plus",          # 平衡性能
        "qwen-turbo",         # 快速响应
        "qwen-long",          # 超长上下文
    ]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Project paths
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    STORAGE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "storage")
    PROMPTS_DIR: Path = Field(default_factory=lambda: Path(__file__).parent / "prompts")

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./storage/arxiv.db",
        description="SQLite database URL"
    )

    # LLM Provider Settings
    LLM_PROVIDER: str = Field(
        default="bailian",
        description="LLM provider: bailian (阿里百炼), anthropic, openai"
    )

    # Alibaba Bailian (阿里百炼) API
    BAILIAN_API_KEY: str = Field(
        default="",
        description="阿里百炼 API Key"
    )
    BAILIAN_BASE_URL: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="阿里百炼 API Base URL"
    )

    # Model selection for different agents
    MODEL_SELECTION: str = Field(
        default="qwen-max",
        description="论文筛选模型"
    )
    MODEL_SUMMARY: str = Field(
        default="qwen-max",
        description="内容生成模型"
    )
    MODEL_PUBLISHER: str = Field(
        default="qwen-plus",
        description="平台发布模型"
    )

    # Anthropic API (alternative)
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Anthropic API key for Claude"
    )

    # arXiv API settings
    ARXIV_BATCH_SIZE: int = Field(default=100, description="Number of papers to fetch per batch")
    ARXIV_DELAY_SECONDS: float = Field(default=3.0, description="Delay between arxiv API calls")

    # Paper selection settings
    DAILY_PAPER_COUNT: int = Field(default=5, description="Number of papers to select daily")

    # Dynamic weights based on paper age
    SELECTION_WEIGHTS_NEW: dict = Field(
        default={
            "citations": 0.05,           # Too new for citations
            "author_history": 0.20,      # Author track record
            "content_quality": 0.45,     # Full content analysis (most important)
            "community_heat": 0.10,      # Early social signals
            "novelty": 0.20              # True novelty assessment
        },
        description="Weights for papers < 30 days old"
    )

    SELECTION_WEIGHTS_MATURE: dict = Field(
        default={
            "citations": 0.20,           # Citation count is reliable now
            "citation_quality": 0.15,    # Quality of citations
            "author_history": 0.15,      # Author track record
            "content_quality": 0.30,     # Content quality still matters
            "community_heat": 0.10,      # Community engagement
            "novelty": 0.10              # Novelty (retrospective)
        },
        description="Weights for papers > 30 days old"
    )

    # Thresholds for paper age classification (days)
    PAPER_AGE_THRESHOLD_NEW: int = Field(default=30, description="Days to consider a paper 'new'")
    PAPER_AGE_THRESHOLD_MATURE: int = Field(default=365, description="Days to consider a paper 'mature'")

    # Content analysis settings
    ENABLE_FULL_PDF_ANALYSIS: bool = Field(default=True, description="Enable PDF content analysis")
    ENABLE_AUTHOR_HISTORY_ANALYSIS: bool = Field(default=True, description="Enable author history analysis")
    ENABLE_PAPER_COMPARISON: bool = Field(default=True, description="Enable comparison with existing papers")
    MAX_PAPERS_FOR_COMPARISON: int = Field(default=10, description="Max papers to compare against")

    # Legacy weights (for backward compatibility)
    SELECTION_WEIGHTS: dict = Field(
        default={
            "citations": 0.25,
            "author_influence": 0.25,
            "content_quality": 0.30,
            "community_heat": 0.20
        }
    )

    # Semantic Scholar API
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = Field(default=None)

    # Social Media Integration
    TWITTER_BEARER_TOKEN: str = Field(default="", description="Twitter API v2 Bearer Token")
    ENABLE_SOCIAL_MONITORING: bool = Field(default=True, description="Enable social media monitoring")
    SOCIAL_SIGNAL_WEIGHT: float = Field(default=0.15, description="Weight for social signals in scoring")
    MIN_SOCIAL_SCORE_FOR_BOOST: float = Field(default=0.5, description="Minimum social score to boost a paper")

    # China Social Media Integration (for domestic deployment)
    SOCIAL_MEDIA_REGION: str = Field(
        default="global",  # "global" or "china"
        description="Social media region: 'global' for international platforms, 'china' for domestic platforms"
    )
    ENABLE_CN_SOCIAL_MONITORING: bool = Field(default=True, description="Enable China social media monitoring")
    CN_SOCIAL_SIGNAL_WEIGHT: float = Field(default=0.15, description="Weight for China social signals")
    XIAOHONGSHU_COOKIE: str = Field(default="", description="Xiaohongshu cookie for monitoring")
    # WeChat Official Account Integration
    ENABLE_WECHAT_MONITORING: bool = Field(default=True, description="Enable WeChat article monitoring")
    WECHAT_MONITOR_SOURCE: str = Field(default="sogou", description="WeChat data source: sogou, xinbang, custom")
    XINBANG_API_KEY: str = Field(default="", description="Xinbang API key (if using xinbang source)")
    WECHAT_SIGNAL_WEIGHT: float = Field(default=0.15, description="Weight for WeChat signals in scoring")

    # Notion integration
    NOTION_API_KEY: str = Field(default="")
    NOTION_DATABASE_ID: str = Field(default="")
    NOTION_PARENT_PAGE_ID: str = Field(
        default="",
        description="Parent page ID for daily pages (knowledge base mode)"
    )

    # Feishu integration
    FEISHU_APP_ID: str = Field(default="")
    FEISHU_APP_SECRET: str = Field(default="")
    FEISHU_WEBHOOK_URL: str = Field(default="")

    # Xiaohongshu (third-party service)
    XHS_API_KEY: str = Field(default="")
    XHS_API_URL: str = Field(default="")

    # WeChat Official Account
    WECHAT_APP_ID: str = Field(default="")
    WECHAT_APP_SECRET: str = Field(default="")

    # Scheduling
    SCHEDULE_HOUR: int = Field(default=9, description="Hour to run daily task (24h format)")
    SCHEDULE_MINUTE: int = Field(default=0, description="Minute to run daily task")

    # Review server settings
    REVIEW_SERVER_HOST: str = Field(default="0.0.0.0", description="Review web server host")
    REVIEW_SERVER_PORT: int = Field(default=8080, description="Review web server port")
    REVIEW_LINK_EXPIRE_HOURS: int = Field(default=2, description="Review link expiration in hours")
    REVIEW_BASE_URL: str = Field(
        default="http://localhost:8080",
        description="Base URL for review page (change for production)"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()