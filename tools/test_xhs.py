#!/usr/bin/env python
"""
Xiaohongshu (小红书) MCP Publisher Test Script

This script tests the XHS publishing functionality using MCP tools.

Usage:
    python tools/test_xhs.py status     # Check login status
    python tools/test_xhs.py feeds      # List recent feeds
    python tools/test_xhs.py publish    # Test publishing
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config.settings import settings


def create_test_content():
    """Create test content for XHS publishing."""
    return {
        "title": "AI Agent论文精选",
        "content": """今天整理了2篇AI Agent领域的最新论文，每篇都有独特的创新点 👇

📌 Tree of Thoughts: Deliberate Problem Solving
核心内容：提出思维树框架，通过多路径探索提升LLM推理能力

📌 ReAct: Synergizing Reasoning and Acting
核心内容：结合推理与行动，实现更可靠的Agent决策

你最期待哪篇论文的落地应用？评论区聊聊～

关注我，每天分享AI前沿论文""",
        "tags": ["AI", "Agent", "论文", "人工智能"]
    }


async def test_xhs_status():
    """Test XHS MCP connection status."""
    print("=" * 60)
    print("Xiaohongshu MCP Status Check")
    print("=" * 60)

    # In MCP runtime, call:
    # result = await mcp__xiaohongshu-mcp__check_login_status()

    print("\n📋 To check login status in Claude Code, run:")
    print("   mcp__xiaohongshu-mcp__check_login_status()")

    return True


async def test_xhs_feeds():
    """Test listing XHS feeds."""
    print("\n" + "=" * 60)
    print("Xiaohongshu Feeds")
    print("=" * 60)

    # In MCP runtime, call:
    # result = await mcp__xiaohongshu-mcp__list_feeds()

    print("\n📋 To list feeds in Claude Code, run:")
    print("   mcp__xiaohongshu-mcp__list_feeds()")

    return True


async def test_xhs_publish():
    """Test publishing to XHS."""
    print("\n" + "=" * 60)
    print("Xiaohongshu Publishing Test")
    print("=" * 60)

    content = create_test_content()

    print("\n📝 Content to publish:")
    print(f"   Title: {content['title']}")
    print(f"   Content: {len(content['content'])} chars")
    print(f"   Tags: {content['tags']}")

    # Check for cover images
    cover_path = settings.STORAGE_DIR / "cover.jpg"
    fallback_path = settings.STORAGE_DIR / "cover_fallback.jpg"

    images = []
    if cover_path.exists():
        images.append(str(cover_path))
        print(f"\n📷 Using cover image: {cover_path}")
    elif fallback_path.exists():
        images.append(str(fallback_path))
        print(f"\n📷 Using fallback image: {fallback_path}")
    else:
        # Use a test image URL
        images.append("https://picsum.photos/800/1000")
        print(f"\n📷 Using network image: https://picsum.photos/800/1000")

    # Prepare MCP call parameters
    mcp_params = {
        "title": content["title"],
        "content": content["content"],
        "images": images,
        "tags": content["tags"],
        "is_original": False
    }

    print("\n📋 MCP Call Parameters:")
    print(json.dumps(mcp_params, indent=2, ensure_ascii=False))

    print("\n🚀 To publish in Claude Code, run:")
    print("   mcp__xiaohongshu-mcp__publish_content(")
    print(f"       title=\"{content['title']}\",")
    print(f"       content=\"{content['content'][:50]}...\",")
    print(f"       images={images},")
    print(f"       tags={content['tags']},")
    print("       is_original=False")
    print("   )")

    return mcp_params


async def test_agent():
    """Test the XHSPublisherAgent."""
    from agents.publishers import XHSPublisherAgent
    from agents.base import AgentContext

    print("\n" + "=" * 60)
    print("Testing XHSPublisherAgent")
    print("=" * 60)

    # Create sample data
    paper = {
        "arxiv_id": "2401.12345",
        "title": "A Novel Multi-Agent Framework for Autonomous Task Planning",
        "authors": ["Zhang Wei", "Li Ming", "Wang Fang"],
        "abstract": "We present a novel multi-agent framework that enables autonomous task planning.",
        "abs_url": "https://arxiv.org/abs/2401.12345",
        "pdf_url": "https://arxiv.org/pdf/2401.12345.pdf",
        "total_score": 0.85,
    }

    summary = {
        "summary": "提出了一个结合大语言模型和符号规划的多智能体协作框架",
        "highlights": [
            "多智能体协作框架",
            "符号推理与神经网络结合",
            "SOTA结果"
        ],
        "tags": ["Agent", "Multi-Agent", "Planning"]
    }

    # Create agent and context
    agent = XHSPublisherAgent()
    context = AgentContext(
        session_id="test_xhs",
        timestamp=datetime.now().isoformat(),
        shared_data={
            "summaries": [
                {"paper": paper, "summary": summary}
            ]
        }
    )

    # Test content generation
    print("\n📝 Testing collection content generation...")

    try:
        collection = await agent._generate_collection_content([paper], [summary])
        if collection:
            print("✅ Collection content generated:")
            print(json.dumps(collection, indent=2, ensure_ascii=False))
        else:
            print("⚠️ No collection content generated (LLM may not be configured)")
    except Exception as e:
        print(f"❌ Error: {e}")

    return True


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Xiaohongshu Publisher Test Tools")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "feeds", "publish", "agent", "all"],
        help="Command to run"
    )

    args = parser.parse_args()

    if args.command == "status":
        await test_xhs_status()
    elif args.command == "feeds":
        await test_xhs_feeds()
    elif args.command == "publish":
        await test_xhs_publish()
    elif args.command == "agent":
        await test_agent()
    elif args.command == "all":
        await test_xhs_status()
        await test_xhs_feeds()
        await test_xhs_publish()


if __name__ == "__main__":
    asyncio.run(main())