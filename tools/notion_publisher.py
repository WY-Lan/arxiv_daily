"""
Notion MCP integration for publishing papers.

This module provides a synchronous wrapper for Notion MCP tools
that can be called from async agent code.

Two publishing modes:
1. Daily Page Mode (recommended): Create one page per day with all papers
2. Database Mode (legacy): Add each paper as a database entry
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from loguru import logger


# =============================================================================
# Daily Page Mode (Recommended)
# =============================================================================

def format_daily_page_content(
    papers: List[Dict[str, Any]],
    summaries: List[Dict[str, Any]],
    date: Optional[str] = None
) -> str:
    """
    Format all papers as content for a daily Notion page.

    Args:
        papers: List of paper data dicts
        summaries: List of summary data dicts (parallel to papers)
        date: Optional date string (defaults to today)

    Returns:
        Markdown content string for Notion page
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    content_parts = []

    # Header
    content_parts.append(f"# 📚 {date} AI Agent 论文精选\n")
    content_parts.append(f"今日精选 **{len(papers)}** 篇论文，聚焦 Agent 领域前沿研究。\n")
    content_parts.append("---\n")

    # Each paper
    for i, (paper, summary) in enumerate(zip(papers, summaries), 1):
        paper_section = _format_paper_section(paper, summary, i)
        content_parts.append(paper_section)
        content_parts.append("---\n")

    # Footer
    content_parts.append("\n🤖 由 Arxiv Daily Push 自动生成")

    return "\n".join(content_parts)


def _format_paper_section(paper: Dict, summary: Dict, index: int) -> str:
    """Format a single paper section for the daily page."""
    parts = []

    # Title
    title = paper.get("title", "") or summary.get("title", "")
    parts.append(f"## 📄 论文 {index}: {title}\n")

    # Authors
    authors = paper.get("authors", [])
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
        except:
            authors = [authors]
    if authors:
        if len(authors) > 5:
            authors_display = ", ".join(authors[:5]) + " 等"
        else:
            authors_display = ", ".join(authors)
        parts.append(f"**👥 作者**: {authors_display}\n")

    # Links
    abs_url = paper.get("abs_url", "")
    pdf_url = paper.get("pdf_url", "")
    code_url = summary.get("code_link", "") or paper.get("github_url", "") or paper.get("code_url", "")

    links = []
    if abs_url:
        links.append(f"[arxiv]({abs_url})")
    if pdf_url:
        links.append(f"[PDF]({pdf_url})")
    if code_url:
        links.append(f"[代码]({code_url})")
    if links:
        parts.append(f"**🔗 链接**: {' | '.join(links)}\n")

    parts.append("\n")

    # Core contribution
    if summary.get("core_contribution"):
        cc = summary["core_contribution"]
        parts.append("### 💡 核心贡献\n")
        if isinstance(cc, dict):
            parts.append(cc.get("main", "") + "\n")
            if cc.get("details"):
                for detail in cc["details"]:
                    parts.append(f"- {detail}\n")
        else:
            parts.append(str(cc) + "\n")
        parts.append("\n")

    # Method overview
    if summary.get("method_overview"):
        mo = summary["method_overview"]
        parts.append("### 🔬 方法概述\n")
        if isinstance(mo, dict):
            parts.append(mo.get("approach", "") + "\n")
            if mo.get("key_innovation"):
                parts.append(f"\n**关键创新**: {mo['key_innovation']}\n")
        else:
            parts.append(str(mo) + "\n")
        parts.append("\n")

    # Key findings
    if summary.get("key_findings"):
        kf = summary["key_findings"]
        parts.append("### 📊 主要发现\n")
        if isinstance(kf, dict):
            if kf.get("main_results"):
                parts.append(kf["main_results"] + "\n")
            if kf.get("insights"):
                for insight in kf["insights"]:
                    parts.append(f"- {insight}\n")
        else:
            parts.append(str(kf) + "\n")
        parts.append("\n")

    # Practical implications
    if summary.get("practical_implications"):
        pi = summary["practical_implications"]
        if isinstance(pi, dict) and pi.get("applications"):
            parts.append("### 🚀 应用场景\n")
            for app in pi["applications"]:
                parts.append(f"- {app}\n")
            parts.append("\n")

    return "\n".join(parts)


def prepare_daily_page(
    papers: List[Dict[str, Any]],
    summaries: List[Dict[str, Any]],
    parent_page_id: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Prepare data for creating a daily Notion page.

    Args:
        papers: List of paper data dicts
        summaries: List of summary data dicts
        parent_page_id: Parent page ID for the daily page
        date: Optional date string (defaults to today)

    Returns:
        Dict with page creation parameters
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    title = f"{date} AI Agent 论文精选"
    content = format_daily_page_content(papers, summaries, date)

    return {
        "parent_page_id": parent_page_id,
        "title": title,
        "content": content,
        "date": date,
        "paper_count": len(papers)
    }


# =============================================================================
# Database Daily Entry Mode (Recommended)
# =============================================================================


def prepare_daily_database_entry(
    papers: List[Dict[str, Any]],
    summaries: List[Dict[str, Any]],
    database_id: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a daily entry in database with all papers in the page content.

    This combines the benefits of:
    - Database structure for easy management
    - Full paper content in the page body

    Args:
        papers: List of paper data dicts
        summaries: List of summary data dicts
        database_id: Notion database ID
        date: Optional date string (defaults to today)

    Returns:
        Dict with page creation parameters for MCP tool
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    title = f"{date} AI Agent 论文精选"
    content = format_daily_page_content(papers, summaries, date)

    # Build properties for database entry
    properties = {
        "论文标题": title,
        "状态": "待阅读",
    }

    # 发布日期
    properties["date:发布日期:start"] = date

    # 论文数量统计
    paper_count = len(papers)
    if paper_count > 0:
        # 添加一些统计信息
        total_score = sum(p.get("total_score", 0) for p in papers) / paper_count
        properties["评分"] = round(total_score * 100, 1)

    return {
        "database_id": database_id,
        "properties": properties,
        "content": content,
        "date": date,
        "paper_count": paper_count,
        "title": title
    }


# =============================================================================
# Database Mode (Legacy - Per Paper)
# =============================================================================


def publish_paper_to_notion(
    paper: Dict[str, Any],
    summary: Dict[str, Any],
    database_id: str
) -> Dict[str, Any]:
    """
    Publish a paper to Notion database.

    This is a sync function that should be called via asyncio.to_thread()
    from async code, or directly from the MCP tool context.

    Args:
        paper: Paper data dict
        summary: Summary data dict
        database_id: Notion database ID

    Returns:
        Result dict with status and URL
    """
    # Prepare properties for Notion database
    # Based on the schema we created:
    # 论文标题, 作者, 摘要, arxiv链接, PDF链接, 发布日期, 核心贡献, 推荐理由, 阅读难度, 标签, 引用数, 评分, 状态

    title = paper.get("title", "") or summary.get("title", "")
    authors = paper.get("authors", "")
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
            authors = ", ".join(authors[:5])  # 最多显示5个作者
        except:
            pass

    properties = {
        "论文标题": title,
        "作者": authors,
        "摘要": paper.get("abstract", "")[:2000] if paper.get("abstract") else "",  # Notion 有字符限制
        "arxiv链接": paper.get("abs_url", ""),
        "PDF链接": paper.get("pdf_url", ""),
        "核心贡献": summary.get("core_contribution", {}).get("main", "") if isinstance(summary.get("core_contribution"), dict) else str(summary.get("core_contribution", "")),
        "推荐理由": summary.get("recommendation", {}).get("reason", "") if isinstance(summary.get("recommendation"), dict) else str(summary.get("recommendation_reason", "")),
        "引用数": paper.get("citation_count", 0),
        "评分": round(paper.get("total_score", 0) * 100, 1),  # 转换为百分制
    }

    # 发布日期
    if paper.get("published_date"):
        if isinstance(paper["published_date"], datetime):
            properties["date:发布日期:start"] = paper["published_date"].strftime("%Y-%m-%d")
        elif isinstance(paper["published_date"], str):
            properties["date:发布日期:start"] = paper["published_date"][:10]

    # 阅读难度
    difficulty = summary.get("recommendation", {}).get("target_audience", "") if isinstance(summary.get("recommendation"), dict) else summary.get("difficulty_level", "")
    if "入门" in difficulty or "beginner" in difficulty.lower():
        properties["阅读难度"] = "入门"
    elif "进阶" in difficulty or "intermediate" in difficulty.lower():
        properties["阅读难度"] = "进阶"
    elif "前沿" in difficulty or "advanced" in difficulty.lower():
        properties["阅读难度"] = "前沿"

    # 标签
    tags = summary.get("tags", [])
    if isinstance(tags, list):
        # 只保留我们定义的标签
        valid_tags = ["Agent", "LLM", "Planning", "Reasoning", "Multi-Agent", "Tool Use"]
        filtered_tags = [t for t in tags if any(vt.lower() in t.lower() for vt in valid_tags)]
        if filtered_tags:
            properties["标签"] = json.dumps(filtered_tags[:5])

    # 状态
    properties["状态"] = "待阅读"

    return {
        "database_id": database_id,
        "properties": properties,
        "paper_id": paper.get("arxiv_id"),
    }


def format_notion_content(paper: Dict, summary: Dict) -> str:
    """
    Format paper content as Notion markdown.

    Args:
        paper: Paper data
        summary: Summary data

    Returns:
        Markdown string for Notion page content
    """
    content_parts = []

    # 核心贡献
    if summary.get("core_contribution"):
        cc = summary["core_contribution"]
        if isinstance(cc, dict):
            content_parts.append("## 核心贡献\n")
            content_parts.append(cc.get("main", ""))
            if cc.get("details"):
                for detail in cc["details"]:
                    content_parts.append(f"- {detail}")
        else:
            content_parts.append(f"## 核心贡献\n{cc}")

    # 方法概述
    if summary.get("method_overview"):
        mo = summary["method_overview"]
        if isinstance(mo, dict):
            content_parts.append("\n## 方法概述\n")
            content_parts.append(mo.get("approach", ""))
            if mo.get("key_innovation"):
                content_parts.append(f"\n**关键创新**: {mo['key_innovation']}")

    # 主要发现
    if summary.get("key_findings"):
        kf = summary["key_findings"]
        if isinstance(kf, dict):
            content_parts.append("\n## 主要发现\n")
            if kf.get("main_results"):
                content_parts.append(kf["main_results"])
            if kf.get("insights"):
                for insight in kf["insights"]:
                    content_parts.append(f"- {insight}")

    # 实际应用
    if summary.get("practical_implications"):
        pi = summary["practical_implications"]
        if isinstance(pi, dict):
            if pi.get("applications"):
                content_parts.append("\n## 应用场景\n")
                for app in pi["applications"]:
                    content_parts.append(f"- {app}")

    # 链接
    content_parts.append("\n## 链接\n")
    content_parts.append(f"- [论文原文]({paper.get('abs_url', '')})")
    content_parts.append(f"- [PDF]({paper.get('pdf_url', '')})")
    if summary.get("code_link"):
        content_parts.append(f"- [代码]({summary['code_link']})")

    return "\n".join(content_parts)