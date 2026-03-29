"""
Test script for WeChat n+1 publishing functionality.

Usage:
    python tools/test_wechat_nplus1.py --mode nplus1
    python tools/test_wechat_nplus1.py --mode collection
    python tools/test_wechat_nplus1.py --mode single --arxiv-id 2401.00100
"""
import asyncio
import argparse
import json
from pathlib import Path

from loguru import logger
from config.settings import settings
from tools.wechat_publisher import get_wechat_client
from tools.llm_client import BailianClient


async def test_wechat_connection():
    """Test WeChat API connection."""
    print("\n" + "=" * 50)
    print("Testing WeChat MP Connection")
    print("=" * 50)

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        print("❌ WeChat MP not configured.")
        print("   Set WECHAT_APP_ID and WECHAT_APP_SECRET in .env")
        return False

    client = get_wechat_client()
    if not client:
        print("❌ Failed to create WeChat client")
        return False

    try:
        token = await client.get_access_token()
        print(f"✅ Access token obtained: {token[:20]}...")
        return True
    except Exception as e:
        print(f"❌ Failed to get access token: {e}")
        return False


async def test_draft_operations():
    """Test draft creation, listing, and deletion."""
    print("\n" + "=" * 50)
    print("Testing Draft Operations")
    print("=" * 50)

    client = get_wechat_client()
    if not client:
        print("❌ WeChat client not available")
        return

    # List existing drafts
    print("\n1. Listing existing drafts...")
    drafts = await client.get_draft_list()
    print(f"   Found {len(drafts)} drafts")

    # Create a test draft
    print("\n2. Creating test draft...")

    # Create a simple test cover
    from PIL import Image
    import io

    img = Image.new('RGB', (900, 500), color=(52, 73, 94))
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)
    cover_data = buffer.getvalue()

    try:
        thumb_media_id = await client.upload_image(cover_data, "test_cover.jpg")
        print(f"   ✅ Cover uploaded: {thumb_media_id}")

        article = {
            "title": "Test Draft - Please Delete",
            "author": "arxiv_daily",
            "digest": "This is a test draft",
            "content": "<p>This is a test draft for verification.</p>",
            "thumb_media_id": thumb_media_id,
        }

        draft_media_id = await client.create_draft([article])
        print(f"   ✅ Draft created: {draft_media_id}")

        # List drafts again
        print("\n3. Verifying draft creation...")
        drafts = await client.get_draft_list()
        print(f"   Now have {len(drafts)} drafts")

        # Delete test draft
        print("\n4. Deleting test draft...")
        success = await client.delete_draft(draft_media_id)
        if success:
            print("   ✅ Draft deleted")
        else:
            print("   ⚠️ Could not delete draft - please delete manually")

    except Exception as e:
        print(f"   ❌ Error: {e}")


async def test_nplus1_mode(dry_run: bool = True):
    """Test n+1 publishing mode."""
    print("\n" + "=" * 50)
    print(f"Testing n+1 Mode (dry_run={dry_run})")
    print("=" * 50)

    # Check for selected papers
    papers_path = Path('storage/selected_papers.json')
    if not papers_path.exists():
        print("❌ No selected papers found. Run selection first.")
        return

    with open(papers_path, 'r') as f:
        papers = json.load(f)

    n = len(papers)
    print(f"\nFound {n} selected papers")

    if n == 0:
        print("❌ No papers to publish")
        return

    if dry_run:
        print("\n[DRY RUN] Would create:")
        print(f"  - {n} detailed article drafts")
        print(f"  - 1 summary article draft")
        print("\nTo actually publish, run with --no-dry-run")
    else:
        from tools.publish_wechat_nplus1 import main as wechat_main
        await wechat_main()


async def test_content_generation():
    """Test content generation with LLM."""
    print("\n" + "=" * 50)
    print("Testing Content Generation")
    print("=" * 50)

    papers_path = Path('storage/selected_papers.json')
    if not papers_path.exists():
        print("❌ No selected papers found.")
        return

    with open(papers_path, 'r') as f:
        papers = json.load(f)

    if not papers:
        print("❌ No papers to test")
        return

    paper = papers[0]
    print(f"\nGenerating content for: {paper.get('arxiv_id')}")
    print(f"Title: {paper.get('title', '')[:50]}...")

    if not settings.BAILIAN_API_KEY:
        print("❌ LLM not configured. Set BAILIAN_API_KEY.")
        return

    llm_client = BailianClient()

    try:
        from tools.publish_wechat_nplus1 import generate_single_paper_content
        content = await generate_single_paper_content(paper, llm_client)

        print("\n✅ Content generated:")
        print(f"   Title: {content.get('title', '')[:30]}...")
        print(f"   Digest: {content.get('digest', '')[:50]}...")
        print(f"   Content length: {len(content.get('content', ''))} chars")

    except Exception as e:
        print(f"❌ Failed to generate content: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Test WeChat n+1 publishing")
    parser.add_argument(
        "--mode",
        choices=["connection", "draft", "content", "nplus1", "all"],
        default="all",
        help="Test mode to run"
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually create drafts (default is dry run)"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("WeChat n+1 Publishing Test Suite")
    print("=" * 60)

    if args.mode in ["connection", "all"]:
        await test_wechat_connection()

    if args.mode in ["draft", "all"]:
        await test_draft_operations()

    if args.mode in ["content", "all"]:
        await test_content_generation()

    if args.mode in ["nplus1", "all"]:
        await test_nplus1_mode(dry_run=not args.no_dry_run)

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())