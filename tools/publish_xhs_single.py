"""
Publish a single paper to Xiaohongshu.

This module provides functionality to publish a specific paper to XHS
by specifying its arxiv_id. It reuses existing functions from
publish_xhs_5plus1.py for content generation and publishing.
"""
import asyncio
import json
from pathlib import Path
from typing import Optional

from loguru import logger

from tools.arxiv_api import ArxivClient, ArxivPaper
from tools.llm_client import BailianClient
from tools.publish_xhs_5plus1 import (
    generate_single_paper_content,
    create_single_paper_images,
    publish_single_post,
)
from storage.database import db


async def get_paper_info(arxiv_id: str) -> dict:
    """
    Get paper information from multiple sources.

    Priority:
    1. Local database
    2. Local JSON file (selected_papers.json)
    3. Arxiv API

    Args:
        arxiv_id: Arxiv paper ID (e.g., "2603.26512")

    Returns:
        Paper dict with all required fields

    Raises:
        ValueError: If paper not found in any source
    """
    # Normalize arxiv_id (remove 'v' version suffix if present)
    normalized_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id

    # 1. Try local database
    try:
        await db.init()
        paper_row = await db.get_paper_by_arxiv_id(normalized_id)
        if paper_row:
            logger.info(f"Found paper {normalized_id} in database")
            # Convert Row to dict
            paper_dict = {
                'arxiv_id': paper_row.arxiv_id,
                'title': paper_row.title,
                'authors': json.loads(paper_row.authors) if paper_row.authors else [],
                'abstract': paper_row.abstract,
                'categories': json.loads(paper_row.categories) if paper_row.categories else [],
                'published_date': str(paper_row.published_date) if paper_row.published_date else None,
                'pdf_url': paper_row.pdf_url,
                'abs_url': paper_row.abs_url,
            }
            await db.close()
            return paper_dict
    except Exception as e:
        logger.warning(f"Database lookup failed: {e}")
        try:
            await db.close()
        except:
            pass

    # 2. Try selected_papers.json
    project_root = Path(__file__).parent.parent
    json_path = project_root / 'storage/selected_papers.json'
    if json_path.exists():
        with open(json_path, 'r') as f:
            papers = json.load(f)
        for p in papers:
            if p.get('arxiv_id') == normalized_id:
                logger.info(f"Found paper {normalized_id} in selected_papers.json")
                # Ensure pdf_url exists
                if not p.get('pdf_url'):
                    p['pdf_url'] = f"https://arxiv.org/pdf/{normalized_id}.pdf"
                return p

    # 3. Fetch from Arxiv API
    logger.info(f"Fetching paper {normalized_id} from Arxiv API...")
    client = ArxivClient()
    papers = await client.fetch_papers_by_ids([normalized_id])

    if papers:
        paper = papers[0]
        logger.info(f"Found paper {normalized_id} from Arxiv API")
        return arxiv_paper_to_dict(paper)

    raise ValueError(f"Paper {arxiv_id} not found in any source")


def arxiv_paper_to_dict(paper: ArxivPaper) -> dict:
    """
    Convert ArxivPaper to dict format.

    Args:
        paper: ArxivPaper instance

    Returns:
        Dict with paper info
    """
    return {
        'arxiv_id': paper.arxiv_id,
        'title': paper.title,
        'authors': paper.authors,
        'abstract': paper.abstract,
        'categories': paper.categories,
        'published_date': str(paper.published_date),
        'pdf_url': paper.pdf_url,
        'abs_url': paper.abs_url,
    }


async def publish_single_paper_to_xhs(arxiv_id: str) -> dict:
    """
    Publish a single paper to Xiaohongshu.

    Args:
        arxiv_id: Arxiv paper ID (e.g., "2603.26512")

    Returns:
        Dict with publish result (url, feed_id, xsec_token)
    """
    print("\n" + "=" * 60)
    print(f"XHS Single Paper Publishing: {arxiv_id}")
    print("=" * 60)

    # Get project root
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "storage/xhs_posts"
    output_dir.mkdir(exist_ok=True)

    # 1. Get paper info
    print(f"\n[1/4] Fetching paper info for {arxiv_id}...")
    paper = await get_paper_info(arxiv_id)
    print(f"  Title: {paper['title'][:50]}...")

    # 2. Generate XHS content
    print(f"\n[2/4] Generating XHS content...")
    llm_client = BailianClient()
    content = await generate_single_paper_content(paper, llm_client)

    if not content:
        print("  ❌ Failed to generate content")
        return {"success": False, "error": "Content generation failed"}

    print(f"  Title: {content.get('title', '')}")
    print(f"  Tags: {', '.join(content.get('tags', []))}")

    # 3. Create images
    print(f"\n[3/4] Extracting PDF pages as images...")
    images = await create_single_paper_images(paper, output_dir, max_pages=18)

    if not images:
        print("  ❌ Failed to create images")
        return {"success": False, "error": "Image creation failed"}

    print(f"  Images: {len(images)} pages")

    # 4. Publish to XHS
    print(f"\n[4/4] Publishing to XHS...")
    result = await publish_single_post(
        title=content.get('title', ''),
        content=content.get('content', ''),
        tags=content.get('tags', []),
        images=images
    )

    # Check for success (may not have URL due to MCP response format)
    is_success = result and (
        result.get('url') or
        "发布成功" in (result.get('raw_result', '') or '') or
        "发布完成" in (result.get('raw_result', '') or '')
    )

    if is_success:
        print(f"  ✅ Published successfully!")
        if result.get('url'):
            print(f"  URL: {result.get('url')}")

        # Save publish record
        record_path = output_dir / f"{arxiv_id}_publish.json"
        with open(record_path, 'w') as f:
            json.dump({
                'arxiv_id': arxiv_id,
                'paper_title': paper['title'],
                'xhs_title': content.get('title'),
                'url': result.get('url'),
                'feed_id': result.get('feed_id'),
                'xsec_token': result.get('xsec_token'),
            }, f, ensure_ascii=False, indent=2)
        print(f"  Record saved: {record_path}")

        return {
            "success": True,
            "url": result.get('url'),
            "feed_id": result.get('feed_id'),
            "xsec_token": result.get('xsec_token'),
        }
    else:
        print("  ⚠️ Published but no URL returned")
        return {"success": False, "error": "No URL returned"}

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


async def main():
    """Main entry point for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python tools/publish_xhs_single.py <arxiv_id>")
        print("Example: python tools/publish_xhs_single.py 2603.26512")
        return

    arxiv_id = sys.argv[1]
    result = await publish_single_paper_to_xhs(arxiv_id)

    if result.get('success'):
        print(f"\n✅ Success: {result.get('url')}")
    else:
        print(f"\n❌ Failed: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())