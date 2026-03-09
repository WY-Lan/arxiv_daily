"""
PDF screenshot tool for generating cover images from arxiv papers.

Downloads PDF from arxiv and captures the first page as an image.
"""
import asyncio
import hashlib
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from loguru import logger

from config.settings import settings


# Storage directory for cover images
COVERS_DIR = settings.STORAGE_DIR / "covers"
COVERS_DIR.mkdir(parents=True, exist_ok=True)


async def download_pdf(pdf_url: str, output_path: Path) -> bool:
    """
    Download PDF from URL.

    Args:
        pdf_url: URL to the PDF file
        output_path: Local path to save the PDF

    Returns:
        True if download successful, False otherwise
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        f.write(await response.read())
                    logger.info(f"Downloaded PDF: {output_path}")
                    return True
                else:
                    logger.error(f"Failed to download PDF: HTTP {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        return False


def screenshot_pdf_page(pdf_path: Path, output_path: Path, page_num: int = 0) -> bool:
    """
    Capture a page from PDF as an image.

    Args:
        pdf_path: Path to the PDF file
        output_path: Path to save the screenshot
        page_num: Page number to capture (0-indexed)

    Returns:
        True if screenshot successful, False otherwise
    """
    try:
        import fit  # PyMuPDF

        doc = fit.open(str(pdf_path))
        if page_num >= len(doc):
            logger.error(f"Page {page_num} not found in PDF")
            return False

        page = doc[page_num]

        # Use higher resolution for better quality
        zoom = 2.0
        mat = fit.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Save as PNG
        pix.save(str(output_path))
        doc.close()

        logger.info(f"Created screenshot: {output_path}")
        return True

    except ImportError:
        logger.warning("PyMuPDF not installed, trying pdf2image...")
        return _screenshot_with_pdf2image(pdf_path, output_path, page_num)
    except Exception as e:
        logger.error(f"Error creating screenshot: {e}")
        return False


def _screenshot_with_pdf2image(pdf_path: Path, output_path: Path, page_num: int = 0) -> bool:
    """
    Fallback: Capture PDF page using pdf2image library.
    """
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), first_page=page_num + 1, last_page=page_num + 1)
        if images:
            images[0].save(str(output_path), 'PNG')
            logger.info(f"Created screenshot with pdf2image: {output_path}")
            return True
        return False
    except ImportError:
        logger.error("Neither PyMuPDF nor pdf2image is installed. Run: pip install pymupdf")
        return False
    except Exception as e:
        logger.error(f"Error with pdf2image: {e}")
        return False


async def download_and_screenshot(
    pdf_url: str,
    arxiv_id: str,
    force: bool = False
) -> Optional[str]:
    """
    Download PDF and create screenshot of the first page.

    Args:
        pdf_url: URL to the arxiv PDF
        arxiv_id: arxiv paper ID (used for filename)
        force: If True, re-download even if file exists

    Returns:
        Path to the screenshot image, or None if failed
    """
    # Determine output paths
    safe_id = arxiv_id.replace("/", "_").replace("\\", "_")
    pdf_path = COVERS_DIR / f"{safe_id}.pdf"
    img_path = COVERS_DIR / f"{safe_id}.png"

    # Check if already exists
    if not force and img_path.exists():
        logger.info(f"Screenshot already exists: {img_path}")
        return str(img_path)

    # Download PDF
    if not pdf_path.exists() or force:
        success = await download_pdf(pdf_url, pdf_path)
        if not success:
            return None

    # Create screenshot
    success = screenshot_pdf_page(pdf_path, img_path)
    if success:
        return str(img_path)

    return None


async def batch_download_and_screenshot(
    papers: list[dict],
    max_concurrent: int = 3
) -> dict[str, str]:
    """
    Download and screenshot multiple papers concurrently.

    Args:
        papers: List of paper dicts with 'pdf_url' and 'arxiv_id' keys
        max_concurrent: Maximum concurrent downloads

    Returns:
        Dict mapping arxiv_id to screenshot path
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def process_paper(paper: dict) -> tuple[str, Optional[str]]:
        async with semaphore:
            arxiv_id = paper.get("arxiv_id", "")
            pdf_url = paper.get("pdf_url", "")

            if not pdf_url:
                logger.warning(f"No PDF URL for {arxiv_id}")
                return arxiv_id, None

            path = await download_and_screenshot(pdf_url, arxiv_id)
            return arxiv_id, path

    tasks = [process_paper(p) for p in papers]
    outcomes = await asyncio.gather(*tasks)

    for arxiv_id, path in outcomes:
        if path:
            results[arxiv_id] = path

    return results


def get_cover_path(arxiv_id: str) -> Optional[Path]:
    """
    Get the path to a cover image if it exists.

    Args:
        arxiv_id: arxiv paper ID

    Returns:
        Path to the cover image, or None if not found
    """
    safe_id = arxiv_id.replace("/", "_").replace("\\", "_")
    img_path = COVERS_DIR / f"{safe_id}.png"

    if img_path.exists():
        return img_path
    return None


def cleanup_old_covers(days: int = 30) -> int:
    """
    Remove cover images older than specified days.

    Args:
        days: Number of days to keep

    Returns:
        Number of files removed
    """
    import time

    removed = 0
    cutoff = time.time() - (days * 86400)

    for file in COVERS_DIR.glob("*.png"):
        if file.stat().st_mtime < cutoff:
            file.unlink()
            removed += 1

    # Also remove PDF files
    for file in COVERS_DIR.glob("*.pdf"):
        if file.stat().st_mtime < cutoff:
            file.unlink()

    if removed:
        logger.info(f"Cleaned up {removed} old cover images")

    return removed


if __name__ == "__main__":
    # Test the module
    import sys

    async def test():
        test_url = "https://arxiv.org/pdf/2401.00100.pdf"
        test_id = "2401.00100"

        print(f"Testing with {test_id}...")
        path = await download_and_screenshot(test_url, test_id)
        if path:
            print(f"Success! Screenshot saved to: {path}")
        else:
            print("Failed to create screenshot")

    asyncio.run(test())