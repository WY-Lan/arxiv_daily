"""
Tools package for external API integrations.
"""
from .arxiv_api import ArxivClient
from .semantic_scholar import SemanticScholarClient
from .openalex import OpenAlexClient
from .papers_with_code import PapersWithCodeClient
from .feishu_webhook import FeishuWebhookClient, get_feishu_client
from .xhs_publisher import publish_to_xiaohongshu, format_paper_for_xhs, build_collection_content
from .wechat_publisher import (
    WeChatMPClient,
    create_cover_image,
    format_article_content,
    get_wechat_client,
)

__all__ = [
    "ArxivClient",
    "SemanticScholarClient",
    "OpenAlexClient",
    "PapersWithCodeClient",
    "FeishuWebhookClient",
    "get_feishu_client",
    "publish_to_xiaohongshu",
    "format_paper_for_xhs",
    "build_collection_content",
    "WeChatMPClient",
    "create_cover_image",
    "format_article_content",
    "get_wechat_client",
]