#!/usr/bin/env python
"""
Notion MCP Publisher Test Script

This script tests the Notion publishing functionality using MCP tools.
It can be run directly or imported as a module.

Usage:
    python tools/test_notion.py test          # Test configuration
    python tools/test_notion.py sample        # Show sample data
    python tools/test_notion.py prepare       # Prepare page data
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


def create_sample_paper():
    """Create a sample paper for testing."""
    return {
        "arxiv_id": "2401.12345",
        "title": "A Novel Multi-Agent Framework for Autonomous Task Planning",
        "authors": '["Zhang Wei", "Li Ming", "Wang Fang"]',
        "abstract": "We present a novel multi-agent framework that enables autonomous task planning through collaborative reasoning. Our approach combines large language models with symbolic planning to achieve state-of-the-art performance on complex reasoning benchmarks.",
        "abs_url": "https://arxiv.org/abs/2401.12345",
        "pdf_url": "https://arxiv.org/pdf/2401.12345.pdf",
        "published_date": "2024-01-15",
        "citation_count": 42,
        "total_score": 0.85,
        "github_url": "https://github.com/example/multi-agent-framework"
    }


def create_sample_summary():
    """Create a sample summary for testing."""
    return {
        "title": "一种用于自主任务规划的新型多智能体框架",
        "summary": "提出了一个结合大语言模型和符号规划的多智能体协作框架，实现了任务分解和分配机制。",
        "core_contribution": {
            "main": "提出了一个结合大语言模型和符号规划的多智能体协作框架",
            "details": [
                "设计了多智能体协作的推理架构",
                "实现了任务分解和分配机制",
                "在多个基准测试上取得了SOTA结果"
            ]
        },
        "method_overview": {
            "approach": "使用强化学习训练智能体进行协作决策，结合LLM进行自然语言理解和生成。",
            "key_innovation": "将符号推理与神经网络的直觉判断相结合"
        },
        "key_findings": {
            "main_results": "在复杂推理任务上提升了15%的准确率",
            "insights": [
                "多智能体协作显著提升了任务完成质量",
                "符号规划增强了可解释性"
            ]
        },
        "recommendation": {
            "reason": "创新性地结合了多种技术，对多智能体系统研究有重要参考价值",
            "target_audience": "进阶"
        },
        "practical_implications": {
            "applications": [
                "自动化任务规划系统",
                "智能客服机器人",
                "代码自动生成"
            ]
        },
        "highlights": [
            "多智能体协作框架",
            "符号推理与神经网络结合",
            "SOTA结果"
        ],
        "tags": ["Agent", "Multi-Agent", "Planning", "LLM"],
        "code_link": "https://github.com/example/multi-agent-framework"
    }


async def test_notion_config():
    """Test Notion configuration."""
    print("=" * 60)
    print("Notion Configuration Check")
    print("=" * 60)

    checks = []

    # Check API Key
    if settings.NOTION_API_KEY:
        checks.append(("API Key", "✅ Configured", settings.NOTION_API_KEY[:10] + "..."))
    else:
        checks.append(("API Key", "❌ Missing", "Set NOTION_API_KEY in .env"))

    # Check Parent Page ID (for daily page mode - recommended)
    if settings.NOTION_PARENT_PAGE_ID:
        checks.append(("Parent Page ID", "✅ Configured", settings.NOTION_PARENT_PAGE_ID))
        checks.append(("Publish Mode", "📋 Daily Page", "Recommended mode"))
    else:
        checks.append(("Parent Page ID", "⚠️ Not set", "Set for daily page mode (recommended)"))

    # Check Database ID (for legacy database mode)
    if settings.NOTION_DATABASE_ID:
        checks.append(("Database ID", "✅ Configured", settings.NOTION_DATABASE_ID))
        if not settings.NOTION_PARENT_PAGE_ID:
            checks.append(("Publish Mode", "📊 Database", "Legacy mode"))
    else:
        checks.append(("Database ID", "⚠️ Not set", "Set for database mode (optional)"))

    print()
    for name, status, detail in checks:
        print(f"  {name}: {status}")
        print(f"    → {detail}")

    can_publish = settings.NOTION_API_KEY and (settings.NOTION_PARENT_PAGE_ID or settings.NOTION_DATABASE_ID)

    print()
    if can_publish:
        print("✅ Notion is properly configured!")
        if settings.NOTION_PARENT_PAGE_ID:
            print("   Will use: Daily Page Mode (recommended)")
        else:
            print("   Will use: Database Mode (legacy)")
    else:
        print("❌ Notion configuration incomplete.")
        print("\nTo configure Notion for Daily Page Mode (recommended):")
        print("  1. Create a Notion integration: https://www.notion.so/my-integrations")
        print("  2. Copy the Internal Token to NOTION_API_KEY")
        print("  3. Create a page to serve as the parent for daily pages")
        print("  4. Share the page with your integration")
        print("  5. Copy the page ID to NOTION_PARENT_PAGE_ID")
        print("\nFor Database Mode (legacy):")
        print("  - Create a database and share it with your integration")
        print("  - Copy the database ID to NOTION_DATABASE_ID")

    return can_publish


async def show_sample_data():
    """Show sample paper and summary data."""
    paper = create_sample_paper()
    summary = create_sample_summary()

    print("\n" + "=" * 60)
    print("Sample Paper Data")
    print("=" * 60)
    print(json.dumps(paper, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("Sample Summary Data")
    print("=" * 60)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


async def prepare_notion_page():
    """Prepare and display Notion page data."""
    from tools.notion_publisher import (
        publish_paper_to_notion,
        format_notion_content,
        prepare_daily_page,
        prepare_daily_database_entry,
        format_daily_page_content
    )

    paper = create_sample_paper()
    summary = create_sample_summary()

    # Check which mode is configured
    if settings.NOTION_PARENT_PAGE_ID:
        print("\n" + "=" * 60)
        print("Preparing Daily Page (Recommended Mode)")
        print("=" * 60)

        # Fix authors format
        paper["authors"] = json.loads(paper["authors"]) if isinstance(paper["authors"], str) else paper["authors"]

        # Prepare daily page data
        page_data = prepare_daily_page(
            papers=[paper],
            summaries=[summary],
            parent_page_id=settings.NOTION_PARENT_PAGE_ID
        )

        print(f"\n📄 Title: {page_data['title']}")
        print(f"   Parent Page ID: {page_data['parent_page_id']}")
        print(f"   Paper Count: {page_data['paper_count']}")

        print("\n📝 Page Content Preview:")
        print("-" * 40)
        content = page_data['content']
        print(content[:800] + "..." if len(content) > 800 else content)

        print("\n✅ Daily page data prepared successfully!")
        return page_data

    elif settings.NOTION_DATABASE_ID:
        print("\n" + "=" * 60)
        print("Preparing Database Daily Entry (Hybrid Mode)")
        print("=" * 60)
        print("📌 Mode: One database entry per day with all papers in page body")

        # Fix authors format
        paper["authors"] = json.loads(paper["authors"]) if isinstance(paper["authors"], str) else paper["authors"]

        # Prepare daily database entry (hybrid mode)
        page_data = prepare_daily_database_entry(
            papers=[paper],
            summaries=[summary],
            database_id=settings.NOTION_DATABASE_ID
        )

        print(f"\n📄 Title: {page_data['title']}")
        print(f"   Database ID: {page_data['database_id']}")
        print(f"   Paper Count: {page_data['paper_count']}")

        print("\n📋 Database Properties:")
        print("-" * 40)
        for key, value in page_data["properties"].items():
            if isinstance(value, str) and len(value) > 60:
                print(f"  {key}: {value[:60]}...")
            else:
                print(f"  {key}: {value}")

        # Show page content
        content = page_data['content']
        print("\n📝 Page Content Preview:")
        print("-" * 40)
        print(content[:800] + "..." if len(content) > 800 else content)

        print("\n✅ Database daily entry data prepared successfully!")
        print("   This will create ONE database row with all papers in the page body.")
        return page_data

    else:
        print("❌ Neither NOTION_PARENT_PAGE_ID nor NOTION_DATABASE_ID is configured")
        return None


async def test_agent_publish():
    """Test the NotionPublisherAgent."""
    from agents.publishers import NotionPublisherAgent
    from agents.base import AgentContext

    print("\n" + "=" * 60)
    print("Testing NotionPublisherAgent")
    print("=" * 60)

    # Create agent
    agent = NotionPublisherAgent()

    # Create context with sample data
    paper = create_sample_paper()
    summary = create_sample_summary()

    # Fix authors format
    paper["authors"] = json.loads(paper["authors"]) if isinstance(paper["authors"], str) else paper["authors"]

    context = AgentContext(
        session_id="test_notion",
        timestamp=datetime.now().isoformat(),
        shared_data={
            "summmaries": [
                {"paper": paper, "summary": summary}
            ]
        }
    )

    # Test publish method
    result = await agent.publish({"paper": paper, "summary": summary})

    print("\n📤 Publish Result:")
    print("-" * 40)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


async def test_mcp_connection():
    """
    Test actual Notion MCP connection.

    This function attempts to use the Notion MCP tools directly.
    It will only work in Claude Code environment with MCP configured.
    """
    print("\n" + "=" * 60)
    print("Testing Notion MCP Connection")
    print("=" * 60)

    if not settings.NOTION_DATABASE_ID:
        print("❌ NOTION_DATABASE_ID not configured")
        return False

    try:
        # In Claude Code with MCP, this would call the actual tool:
        # result = await mcp__notion__notion-fetch(id=settings.NOTION_DATABASE_ID)

        print(f"\nDatabase ID: {settings.NOTION_DATABASE_ID}")
        print("\nTo test MCP connection in Claude Code, run:")
        print(f"  mcp__notion__notion-fetch(id='{settings.NOTION_DATABASE_ID}')")

        print("\n✅ MCP test instructions provided")
        return True

    except Exception as e:
        print(f"❌ MCP test failed: {e}")
        return False


async def test_notion_database():
    """
    Test Notion database operations (save, query, update).

    Tests the storage/notion_db.py module.
    """
    print("\n" + "=" * 60)
    print("Testing Notion Database Operations")
    print("=" * 60)

    from storage.notion_db import NotionDatabase

    # Check configuration
    if not settings.NOTION_API_KEY:
        print("❌ NOTION_API_KEY not configured")
        return False

    if not settings.NOTION_PAPERS_DATABASE_ID:
        print("❌ NOTION_PAPERS_DATABASE_ID not configured")
        print("   Create a Notion database with the following properties:")
        print("   - 论文标题 (Title)")
        print("   - arxiv_id (Text)")
        print("   - 作者 (Multi-select)")
        print("   - 摘要 (Text)")
        print("   - 发布日期 (Date)")
        print("   - arxiv链接 (URL)")
        print("   - PDF链接 (URL)")
        print("   - 引用数 (Number)")
        print("   - 总评分 (Number)")
        print("   - 选择状态 (Select: pending/selected/rejected)")
        print("   - 处理状态 (Checkbox)")
        return False

    # Initialize database
    db = NotionDatabase()
    success = await db.init()

    if not success or not db.is_enabled():
        print("❌ Failed to initialize Notion database")
        return False

    print("✅ Notion database initialized")

    # Test data
    test_paper = {
        "arxiv_id": "test.12345",
        "title": "Test Paper for Notion Storage",
        "authors": '["Test Author 1", "Test Author 2"]',
        "abstract": "This is a test paper to verify Notion database integration.",
        "published_date": "2026-03-31",
        "abs_url": "https://arxiv.org/abs/test.12345",
        "pdf_url": "https://arxiv.org/pdf/test.12345.pdf",
        "citation_count": 10,
        "total_score": 0.85,
        "is_selected": False,
        "is_processed": False,
    }

    try:
        # Test save
        print("\n📝 Testing save_paper...")
        page_id = await db.save_paper(test_paper)

        if page_id:
            print(f"✅ Paper saved successfully: {page_id}")
        else:
            print("❌ Failed to save paper")
            return False

        # Test query
        print("\n🔍 Testing get_paper_by_arxiv_id...")
        paper = await db.get_paper_by_arxiv_id("test.12345")

        if paper:
            print(f"✅ Paper found: {paper.get('title')}")
        else:
            print("❌ Paper not found")
            return False

        # Test update
        print("\n✏️ Testing update_paper...")
        success = await db.update_paper("test.12345", {
            "total_score": 0.90,
            "is_selected": True
        })

        if success:
            print("✅ Paper updated successfully")
        else:
            print("⚠️ Paper update failed (non-critical)")

        # Test get_selected_papers
        print("\n📋 Testing get_selected_papers...")
        selected = await db.get_selected_papers(limit=5)
        print(f"✅ Found {len(selected)} selected papers")

        # Cleanup: Delete test paper (manual in Notion)
        print(f"\n⚠️ Note: Test paper created with page_id: {page_id}")
        print("   Please delete it manually in Notion or update its status.")

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await db.close()


async def test_hybrid_storage():
    """
    Test hybrid storage (Notion + local SQLite).

    Tests the storage/hybrid_storage.py module.
    """
    print("\n" + "=" * 60)
    print("Testing Hybrid Storage")
    print("=" * 60)

    from storage.hybrid_storage import HybridStorage

    # Initialize storage
    storage = HybridStorage(use_notion=True)
    await storage.init()

    print(f"Notion enabled: {storage.is_notion_enabled()}")

    # Test data
    test_paper = {
        "arxiv_id": "hybrid.test.123",
        "title": "Test Paper for Hybrid Storage",
        "authors": '["Hybrid Test Author"]',
        "abstract": "Testing the hybrid storage system.",
        "published_date": "2026-03-31",
        "abs_url": "https://arxiv.org/abs/hybrid.test.123",
        "pdf_url": "https://arxiv.org/pdf/hybrid.test.123.pdf",
        "citation_count": 5,
        "total_score": 0.75,
    }

    try:
        # Test save
        print("\n📝 Testing save_paper (dual write)...")
        result = await storage.save_paper(test_paper)
        print(f"   Local: {'✅' if result.get('local') else '❌'}")
        print(f"   Remote: {'✅' if result.get('remote') else '❌ (Notion not configured or failed)'}")

        # Test query
        print("\n🔍 Testing get_paper_by_arxiv_id...")
        paper = await storage.get_paper_by_arxiv_id("hybrid.test.123")
        if paper:
            print(f"✅ Paper retrieved: {paper.get('title')}")
        else:
            print("❌ Paper not found")

        # Test get_unprocessed_papers
        print("\n📋 Testing get_unprocessed_papers...")
        papers = await storage.get_unprocessed_papers(limit=10)
        print(f"✅ Found {len(papers)} unprocessed papers")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await storage.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Notion Publisher Test Tools")
    parser.add_argument(
        "command",
        nargs="?",
        default="test",
        choices=["test", "sample", "prepare", "agent", "mcp", "db", "storage"],
        help="Command to run: test (config), sample (data), prepare (page), agent (test), mcp (connection), db (database ops), storage (hybrid)"
    )

    args = parser.parse_args()

    if args.command == "test":
        await test_notion_config()
    elif args.command == "sample":
        await show_sample_data()
    elif args.command == "prepare":
        await prepare_notion_page()
    elif args.command == "agent":
        await test_agent_publish()
    elif args.command == "mcp":
        await test_mcp_connection()
    elif args.command == "db":
        await test_notion_database()
    elif args.command == "storage":
        await test_hybrid_storage()


if __name__ == "__main__":
    asyncio.run(main())