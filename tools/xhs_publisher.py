"""
Xiaohongshu (小红书) publishing tool.

Provides utilities for publishing content to Xiaohongshu platform
via MCP (Model Context Protocol).
"""
import json
from typing import Dict, Any, Optional, List

from loguru import logger


async def publish_to_xiaohongshu(
    title: str,
    content: str,
    images: List[str],
    tags: Optional[List[str]] = None,
    is_original: bool = False
) -> Dict[str, Any]:
    """
    Publish content to Xiaohongshu via MCP.

    This function wraps the MCP call for publishing to XHS.
    In the MCP-enabled runtime, this will call the actual tool.

    Args:
        title: Post title (max 20 Chinese characters)
        content: Post body content (500-800 chars recommended)
        images: List of image paths (1-9 images, local absolute paths)
        tags: List of hashtags (without # prefix)
        is_original: Whether to mark as original content

    Returns:
        Dict with publish result including status and URL

    Note:
        In Claude Code runtime with MCP, you can call the MCP tool directly:
        ```
        result = await mcp__xiaohongshu-mcp__publish_content(
            title=title,
            content=content,
            images=images,
            tags=tags,
            is_original=is_original
        )
        ```
    """
    # Validate inputs
    if len(title) > 20:
        logger.warning(f"Title too long ({len(title)} chars), truncating to 20")
        title = title[:20]

    if not images:
        return {
            "status": "error",
            "error": "At least one image is required"
        }

    if len(images) > 9:
        logger.warning(f"Too many images ({len(images)}), limiting to 9")
        images = images[:9]

    # Prepare the publish parameters
    publish_params = {
        "title": title,
        "content": content,
        "images": images,
        "tags": tags or [],
        "is_original": is_original
    }

    logger.info(f"Publishing to XHS: {title}")
    logger.info(f"Content length: {len(content)} chars, Images: {len(images)}")

    # Return the parameters for actual MCP call
    # The caller should use these params with mcp__xiaohongshu-mcp__publish_content
    return {
        "status": "ready",
        "params": publish_params,
        "message": "Parameters prepared for MCP publishing"
    }


def format_paper_for_xhs(paper: Dict, summary: Optional[Dict] = None) -> str:
    """
    Format a single paper for XHS display.

    Args:
        paper: Paper dictionary
        summary: Optional summary dictionary

    Returns:
        Formatted string for XHS post
    """
    title = paper.get("title", "Unknown Title")
    arxiv_id = paper.get("arxiv_id", "")

    # Get summary text
    if summary and summary.get("summary"):
        text = summary["summary"][:150]
    else:
        text = paper.get("abstract", "")[:150]

    # Get highlights
    highlights = []
    if summary and summary.get("highlights"):
        highlights = summary["highlights"][:3]

    lines = [
        f"📌 {title}",
        f"ID: {arxiv_id}",
        "",
        f"核心内容：{text}...",
    ]

    if highlights:
        lines.append("")
        lines.append("亮点：")
        for h in highlights:
            lines.append(f"• {h}")

    return "\n".join(lines)


def build_collection_content(
    papers: List[Dict],
    summaries: Optional[List[Dict]] = None
) -> str:
    """
    Build collection content from multiple papers.

    Args:
        papers: List of paper dictionaries
        summaries: Optional list of summary dictionaries

    Returns:
        Formatted content string
    """
    count = len(papers)

    # Opening
    lines = [
        f"今天整理了{count}篇AI Agent领域的最新论文，每篇都有独特的创新点 👇",
        ""
    ]

    # Paper summaries
    for i, paper in enumerate(papers, 1):
        summary = summaries[i-1] if summaries and i <= len(summaries) else None
        paper_content = format_paper_for_xhs(paper, summary)
        lines.append(paper_content)
        lines.append("---")
        lines.append("")

    # Closing
    lines.extend([
        "你最期待哪篇论文的落地应用？评论区聊聊～",
        "",
        "关注我，每天分享AI前沿论文"
    ])

    return "\n".join(lines)


class XHSPublishResult:
    """Result of a XHS publish operation."""

    def __init__(self, status: str, **kwargs):
        self.status = status
        self.url = kwargs.get("url", "")
        self.error = kwargs.get("error", "")
        self.data = kwargs

    def is_success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "url": self.url,
            "error": self.error,
            **self.data
        }


# Export for use in agents
__all__ = [
    "publish_to_xiaohongshu",
    "format_paper_for_xhs",
    "build_collection_content",
    "XHSPublishResult",
]