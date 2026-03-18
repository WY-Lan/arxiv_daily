"""
Publish to Xiaohongshu with PDF cover images.
"""
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from tools.pdf_screenshot import create_xhs_cover
from storage.database import db


async def get_selected_papers(limit: int = 10) -> list[dict]:
    """Get selected papers from database."""
    rows = await db.get_selected_papers(limit=limit)

    papers = []
    for row in rows:
        # Handle both Row object and Paper model
        if hasattr(row, 'arxiv_id'):
            papers.append({
                "arxiv_id": row.arxiv_id,
                "title": row.title,
                "authors": row.authors,
                "abstract": row.abstract,
                "pdf_url": row.pdf_url
            })
        else:
            # Row tuple format
            papers.append({
                "arxiv_id": row[0] if len(row) > 0 else None,
                "title": row[1] if len(row) > 1 else None,
                "authors": row[2] if len(row) > 2 else None,
                "abstract": row[3] if len(row) > 3 else None,
                "pdf_url": row[4] if len(row) > 4 else None
            })
    return papers


async def main():
    """Main function to generate covers and prepare for publishing."""
    # Initialize database
    await db.init()

    try:
        logger.info("Fetching selected papers...")
        papers = await get_selected_papers(limit=5)  # Use 5 papers for XHS cover

        if not papers:
            logger.error("No selected papers found!")
            return

        logger.info(f"Found {len(papers)} papers")

        # Create merged cover image
        output_path = Path(__file__).parent.parent / "storage" / "xhs_cover.png"
        logger.info(f"Creating cover image at {output_path}...")

        result = await create_xhs_cover(
            papers=papers,
            output_path=str(output_path),
            title="AI Agent 论文精选",
            layout="grid"
        )

        if result:
            logger.success(f"Cover image created: {result}")
            print(f"\n✅ Cover image ready: {result}")
            print(f"   Papers included: {len(papers)}")
            for i, p in enumerate(papers, 1):
                title = p['title'][:50] if p.get('title') else 'N/A'
                print(f"   {i}. {p['arxiv_id']} - {title}...")
        else:
            logger.error("Failed to create cover image")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())