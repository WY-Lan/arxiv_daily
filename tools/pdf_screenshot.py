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
        import pymupdf  # PyMuPDF v1.24.0+

        doc = pymupdf.open(str(pdf_path))
        if page_num >= len(doc):
            logger.error(f"Page {page_num} not found in PDF")
            return False

        page = doc[page_num]

        # Use higher resolution for better quality
        zoom = 2.0
        mat = pymupdf.Matrix(zoom, zoom)
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


# ============================================================================
# Cover Image Merging for XHS Collection Posts
# ============================================================================

def merge_cover_images(
    image_paths: list[str],
    output_path: str,
    layout: str = "grid",
    title: str = "",
    subtitle: str = ""
) -> str:
    """
    Merge multiple cover images into a single collage image.

    Creates a visually appealing cover image by combining paper covers
    with optional title overlay. Supports different layouts.

    Args:
        image_paths: List of paths to individual cover images
        output_path: Path to save the merged image
        layout: Layout style - "grid", "horizontal", "vertical", "mosaic"
        title: Optional title to overlay
        subtitle: Optional subtitle

    Returns:
        Path to the merged image
    """
    from PIL import Image, ImageDraw, ImageFont

    if not image_paths:
        raise ValueError("No images provided")

    # Load and validate images
    valid_images = []
    for path in image_paths:
        try:
            img = Image.open(path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            valid_images.append(img)
        except Exception as e:
            logger.warning(f"Failed to load image {path}: {e}")

    if not valid_images:
        raise ValueError("No valid images to merge")

    # Calculate output dimensions based on layout
    num_images = len(valid_images)

    if layout == "grid":
        # Create a grid layout
        cols, rows = _calculate_grid_size(num_images)
        cell_width = 400
        cell_height = 520  # A4 ratio

        # Resize all images to cell size
        resized_images = []
        for img in valid_images:
            resized = img.resize((cell_width, cell_height), Image.Resampling.LANCZOS)
            resized_images.append(resized)

        # Create output canvas
        total_width = cols * cell_width
        total_height = rows * cell_height + 120  # Extra space for title

        output = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(output)

        # Paste images in grid
        for idx, img in enumerate(resized_images):
            row = idx // cols
            col = idx % cols
            x = col * cell_width
            y = row * cell_height + 120  # Offset for title area
            output.paste(img, (x, y))

        # Draw title area
        if title:
            _draw_title(draw, title, subtitle, total_width, 100)

    elif layout == "horizontal":
        # Horizontal strip
        cell_width = 300
        cell_height = 400

        resized_images = [img.resize((cell_width, cell_height), Image.Resampling.LANCZOS) for img in valid_images]
        total_width = len(resized_images) * cell_width
        total_height = cell_height + 100

        output = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(output)

        for idx, img in enumerate(resized_images):
            output.paste(img, (idx * cell_width, 100))

        if title:
            _draw_title(draw, title, subtitle, total_width, 80)

    elif layout == "mosaic":
        # Mosaic style with overlapping effect
        width = 800
        height = 1000

        output = Image.new('RGB', (width, height), (245, 245, 250))
        draw = ImageDraw.Draw(output)

        # Position images in a visually appealing mosaic
        positions = _calculate_mosaic_positions(num_images, width, height - 120)

        for idx, (img, pos) in enumerate(zip(valid_images[:num_images], positions)):
            x, y, w, h = pos
            resized = img.resize((w, h), Image.Resampling.LANCZOS)
            output.paste(resized, (x, y + 120))

        if title:
            _draw_title(draw, title, subtitle, width, 100)

    else:  # vertical or default
        # Vertical stack
        cell_width = 600
        cell_height = 200

        resized_images = [img.resize((cell_width, cell_height), Image.Resampling.LANCZOS) for img in valid_images[:5]]
        total_height = len(resized_images) * cell_height + 120

        output = Image.new('RGB', (cell_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(output)

        for idx, img in enumerate(resized_images):
            output.paste(img, (0, idx * cell_height + 120))

        if title:
            _draw_title(draw, title, subtitle, cell_width, 100)

    # Save output
    output.save(output_path, quality=95)
    logger.info(f"Created merged cover: {output_path}")

    return output_path


def _calculate_grid_size(n: int) -> tuple[int, int]:
    """Calculate optimal grid dimensions for n images."""
    if n <= 1:
        return 1, 1
    elif n <= 2:
        return 2, 1
    elif n <= 4:
        return 2, 2
    elif n <= 6:
        return 3, 2
    elif n <= 9:
        return 3, 3
    else:
        return 4, 3


def _calculate_mosaic_positions(n: int, canvas_width: int, canvas_height: int) -> list[tuple[int, int, int, int]]:
    """Calculate positions for mosaic layout."""
    positions = []

    if n == 1:
        positions = [(100, 0, canvas_width - 200, canvas_height)]
    elif n == 2:
        positions = [
            (50, 0, canvas_width // 2 - 60, canvas_height),
            (canvas_width // 2 + 10, 0, canvas_width // 2 - 60, canvas_height)
        ]
    elif n == 3:
        positions = [
            (0, 0, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (canvas_width // 2 + 20, 0, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (canvas_width // 4, canvas_height // 2 + 20, canvas_width // 2, canvas_height // 2 - 20)
        ]
    elif n == 4:
        positions = [
            (0, 0, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (canvas_width // 2 + 20, 0, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (0, canvas_height // 2 + 20, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (canvas_width // 2 + 20, canvas_height // 2 + 20, canvas_width // 2 - 20, canvas_height // 2 - 20)
        ]
    elif n == 5:
        # 2 on top, 3 on bottom
        positions = [
            (0, 0, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (canvas_width // 2 + 20, 0, canvas_width // 2 - 20, canvas_height // 2 - 20),
            (0, canvas_height // 2 + 20, canvas_width // 3 - 20, canvas_height // 2 - 20),
            (canvas_width // 3 + 10, canvas_height // 2 + 20, canvas_width // 3 - 20, canvas_height // 2 - 20),
            (2 * canvas_width // 3 + 20, canvas_height // 2 + 20, canvas_width // 3 - 40, canvas_height // 2 - 20)
        ]
    else:
        # Default grid for 6+ images
        cell_w = canvas_width // 3 - 20
        cell_h = canvas_height // 3 - 20
        for i in range(min(n, 9)):
            row = i // 3
            col = i % 3
            x = col * (cell_w + 20)
            y = row * (cell_h + 20)
            positions.append((x, y, cell_w, cell_h))

    return positions


def _draw_title(draw, title: str, subtitle: str, width: int, height: int):
    """Draw title and subtitle on the image."""
    from PIL import ImageFont

    try:
        # Try to use a nice font, fallback to default
        font_large = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 32)
        font_small = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
    except:
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

    # Draw background rectangle
    draw.rectangle([(0, 0), (width, height)], fill=(52, 73, 94))

    # Draw title centered
    title_bbox = draw.textbbox((0, 0), title, font=font_large)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 25), title, fill=(255, 255, 255), font=font_large)

    # Draw subtitle
    if subtitle:
        sub_bbox = draw.textbbox((0, 0), subtitle, font=font_small)
        sub_width = sub_bbox[2] - sub_bbox[0]
        sub_x = (width - sub_width) // 2
        draw.text((sub_x, 70), subtitle, fill=(189, 195, 199), font=font_small)


async def create_xhs_cover(
    papers: list[dict],
    output_path: str,
    title: str = "AI Agent 论文精选",
    layout: str = "grid"
) -> Optional[str]:
    """
    Create a merged cover image for XHS collection post.

    Downloads PDF screenshots if needed and merges them into one image.

    Args:
        papers: List of paper dicts with 'arxiv_id' and 'pdf_url' keys
        output_path: Path to save the merged image
        title: Title to display on the cover
        layout: Layout style

    Returns:
        Path to the created cover image, or None if failed
    """
    # Download screenshots if not already cached
    screenshot_paths = await batch_download_and_screenshot(papers, max_concurrent=3)

    if not screenshot_paths:
        logger.warning("No screenshots available for cover creation")
        return None

    # Get paths in order
    image_paths = []
    for paper in papers:
        arxiv_id = paper.get("arxiv_id")
        if arxiv_id and arxiv_id in screenshot_paths:
            image_paths.append(screenshot_paths[arxiv_id])

    if not image_paths:
        logger.warning("No valid image paths for cover")
        return None

    # Create merged cover
    subtitle = f"今日精选 {len(image_paths)} 篇"
    try:
        result = merge_cover_images(
            image_paths=image_paths,
            output_path=output_path,
            layout=layout,
            title=title,
            subtitle=subtitle
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create merged cover: {e}")
        return None


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