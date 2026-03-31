#!/usr/bin/env python
"""
Arxiv Daily Push System - Main Entry Point

A multi-agent system for daily AI Agent paper recommendations.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from scheduler.jobs import DailyPushScheduler, main_async
from storage.hybrid_storage import storage
from storage.database import db
from config.settings import settings


def setup_logging():
    """Configure logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
              "<level>{level: <8}</level> | "
              "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
              "<level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/arxiv_daily_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG"
    )


async def run_review(send_only: bool = False, check_status: bool = False):
    """
    Run the review workflow.

    Args:
        send_only: Only send review request without starting server
        check_status: Check review status only
    """
    from web.app import create_review_session, get_review_url, run_server_async
    from storage.database import db
    import json

    await db.init()

    try:
        if check_status:
            # Check review status
            session = await db.get_pending_review_session()
            if session:
                print(f"Pending review session: {session.session_id}")
                print(f"Status: {session.status}")
                print(f"Created: {session.created_at}")
                papers = json.loads(session.papers_data) if session.papers_data else []
                print(f"Papers: {len(papers)}")
            else:
                print("No pending review session found.")
            return

        # Get selected papers
        papers = await db.get_selected_papers()

        if not papers:
            print("No selected papers found. Run 'python main.py fetch' and 'python main.py select' first.")
            return

        # Convert to dict format
        papers_data = []
        for paper in papers:
            paper_dict = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": json.loads(paper.authors) if paper.authors else [],
                "abstract": paper.abstract,
                "total_score": paper.total_score,
                "citation_count": paper.citation_count,
                "influence_score": paper.influence_score,
                "quality_score": paper.quality_score,
                "published_date": str(paper.published_date) if paper.published_date else None,
                "categories": json.loads(paper.categories) if paper.categories else [],
            }
            papers_data.append(paper_dict)

        # Create review session
        session_id = await create_review_session(papers_data)
        review_url = get_review_url(session_id)

        print(f"Created review session: {session_id}")
        print(f"Review URL: {review_url}")
        print("\nNote: Review notification is now handled via WeChat MP.")

        if send_only:
            print("Review request created. Run 'python main.py review' to start the review server.")
            return

        # Start review server
        print(f"\nStarting review server on {settings.REVIEW_SERVER_HOST}:{settings.REVIEW_SERVER_PORT}")
        print("Press Ctrl+C to stop the server.\n")

        await run_server_async()

    finally:
        await db.close()


async def run_cli():
    """Run CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Arxiv Daily Push System - AI Agent Paper Recommendations"
    )

    parser.add_argument(
        "command",
        choices=["run", "schedule", "fetch", "select", "publish", "config", "review", "wechat"],
        help="Command to execute"
    )

    parser.add_argument(
        "--platform",
        choices=["notion", "xhs", "wechat", "all"],
        default="all",
        help="Platform to publish to"
    )

    parser.add_argument(
        "--count",
        type=int,
        default=settings.DAILY_PAPER_COUNT,
        help="Number of papers to select"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually publishing"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    # Review command options
    parser.add_argument(
        "--send-only",
        action="store_true",
        help="Only send review request without starting server"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Check review status"
    )

    # WeChat command options
    parser.add_argument(
        "--mode",
        choices=["single", "collection", "nplus1"],
        default="nplus1",
        help="WeChat publishing mode: single, collection, or nplus1 (default)"
    )

    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish drafts immediately (WeChat only)"
    )

    args = parser.parse_args()

    # Initialize storage (Notion + local)
    await storage.init()

    try:
        if args.command == "run":
            # Run full pipeline once
            scheduler = DailyPushScheduler()
            results = await scheduler.run_once()
            print_results(results)

        elif args.command == "schedule":
            # Start scheduler
            scheduler = DailyPushScheduler()
            scheduler.start()
            logger.info("Scheduler started. Press Ctrl+C to stop.")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                scheduler.stop()

        elif args.command == "fetch":
            # Only fetch papers
            from agents.paper_fetcher import PaperFetcherAgent
            from agents.base import AgentContext

            agent = PaperFetcherAgent()
            context = AgentContext(
                session_id=f"fetch_{asyncio.get_event_loop().time()}",
                timestamp=asyncio.get_event_loop().time()
            )
            results = await agent.run(context)
            print(f"Fetched {results['total_fetched']} papers")

        elif args.command == "select":
            # Only select papers
            from agents.paper_fetcher import SelectionAgent
            from agents.base import AgentContext

            agent = SelectionAgent()
            context = AgentContext(
                session_id=f"select_{asyncio.get_event_loop().time()}",
                timestamp=asyncio.get_event_loop().time()
            )
            results = await agent.run(context)
            print(f"Selected {results['selected_count']} papers")

        elif args.command == "review":
            # Review workflow
            await run_review(send_only=args.send_only, check_status=args.status)

        elif args.command == "publish":
            # Only publish
            print("Publish command - requires fetched and selected papers first")

        elif args.command == "wechat":
            # WeChat publishing
            if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
                print("❌ WeChat MP not configured. Set WECHAT_APP_ID and WECHAT_APP_SECRET.")
                return

            if args.mode == "nplus1":
                # n+1 mode: n detailed posts + 1 summary
                from tools.publish_wechat_nplus1 import main as wechat_nplus1_main
                await wechat_nplus1_main()
            elif args.mode == "collection":
                # Collection mode: single summary post
                from agents.publishers import WeChatMPPublisherAgent
                from agents.base import AgentContext
                import json

                # Load selected papers
                papers_path = Path('storage/selected_papers.json')
                if not papers_path.exists():
                    print("❌ No selected papers found. Run selection first.")
                    return

                with open(papers_path, 'r') as f:
                    papers = json.load(f)

                # Create context with papers
                summaries = [{"paper": p, "summary": {}} for p in papers]
                context = AgentContext(
                    session_id=f"wechat_{asyncio.get_event_loop().time()}",
                    timestamp=asyncio.get_event_loop().time()
                )
                context.set("summaries", summaries)

                # Run publisher
                agent = WeChatMPPublisherAgent()
                result = await agent.run(context)
                print(f"Published: {result.get('count', 0)} articles")

            elif args.mode == "single":
                # Single paper mode (requires --count for which paper)
                print("Single paper mode - use nplus1 mode for full publishing")

        elif args.command == "config":
            # Show configuration
            print("=" * 50)
            print("Current Configuration")
            print("=" * 50)
            print(f"LLM Provider: {settings.LLM_PROVIDER}")
            print(f"Selection Model: {settings.MODEL_SELECTION}")
            print(f"Summary Model: {settings.MODEL_SUMMARY}")
            print(f"Publisher Model: {settings.MODEL_PUBLISHER}")
            print(f"Daily Paper Count: {settings.DAILY_PAPER_COUNT}")
            print(f"Schedule: {settings.SCHEDULE_HOUR}:{settings.SCHEDULE_MINUTE:02d}")
            print("=" * 50)
            print("\nPlatform Configuration:")
            print(f"  Notion: {'Configured' if settings.NOTION_API_KEY else 'Not configured'}")
            print(f"  XHS: {'Configured' if settings.XHS_API_KEY else 'Not configured'}")
            print(f"  WeChat: {'Configured' if settings.WECHAT_APP_ID else 'Not configured'}")
            print("=" * 50)
            print("\nReview Server Configuration:")
            print(f"  Host: {settings.REVIEW_SERVER_HOST}")
            print(f"  Port: {settings.REVIEW_SERVER_PORT}")
            print(f"  Base URL: {settings.REVIEW_BASE_URL}")
            print(f"  Link Expiry: {settings.REVIEW_LINK_EXPIRE_HOURS} hours")

    finally:
        await storage.close()


def print_results(results: dict):
    """Print execution results in a formatted way."""
    print("\n" + "=" * 60)
    print("EXECUTION RESULTS")
    print("=" * 60)

    # Fetch results
    if "fetch" in results:
        fetch = results["fetch"]
        print(f"\n📥 Paper Fetch:")
        print(f"   Total fetched: {fetch.get('total_fetched', 0)}")
        print(f"   Saved to DB: {fetch.get('saved', 0)}")

    # Selection results
    if "selection" in results:
        sel = results["selection"]
        print(f"\n🎯 Paper Selection:")
        print(f"   Evaluated: {sel.get('total_evaluated', 0)}")
        print(f"   Selected: {sel.get('selected_count', 0)}")

    # Summary results
    if "summary" in results:
        summ = results["summary"]
        print(f"\n📝 Content Generation:")
        print(f"   Summaries created: {summ.get('count', 0)}")

    # Publish results
    if "publish" in results:
        pub = results["publish"]
        print(f"\n📤 Publishing Results:")
        for platform, result in pub.items():
            status = "✅" if "error" not in result else "❌"
            print(f"   {status} {platform}: {result.get('count', 0)} published")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    setup_logging()
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()