"""
Douyin cover generator for creating vertical (1080x1920) cover images.

Creates eye-catching covers with large fonts and prominent recommendation tags
suitable for Douyin's mobile-first platform.
"""
import asyncio
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from config.settings import settings
from tools.pdf_screenshot import batch_download_and_screenshot, get_cover_path


# Output directory for Douyin covers
DOUYIN_COVERS_DIR = settings.STORAGE_DIR / "douyin_covers"
DOUYIN_COVERS_DIR.mkdir(parents=True, exist_ok=True)

# Douyin cover dimensions (vertical/portrait)
DOUYIN_COVER_WIDTH = 1080
DOUYIN_COVER_HEIGHT = 1920


def create_douyin_cover(
    title: str,
    subtitle: str = "",
    paper_count: int = 0,
    output_path: Optional[str] = None,
    bg_color: tuple = (25, 25, 35),  # Dark background
    accent_color: tuple = (255, 87, 87),  # Red accent
) -> str:
    """
    Create a vertical cover image for Douyin with large title.

    Args:
        title: Main title text (will be truncated to fit)
        subtitle: Subtitle text
        paper_count: Number of papers (shown in badge)
        output_path: Path to save the image
        bg_color: Background color (R, G, B)
        accent_color: Accent color for highlights

    Returns:
        Path to the created cover image
    """
    if output_path is None:
        import time
        output_path = str(DOUYIN_COVERS_DIR / f"douyin_cover_{int(time.time())}.png")

    # Create canvas
    img = Image.new('RGB', (DOUYIN_COVER_WIDTH, DOUYIN_COVER_HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)

    # Load fonts
    font_title, font_subtitle, font_badge, font_tag = _load_fonts()

    # Draw gradient overlay at bottom
    for i in range(400):
        alpha = int(255 * (1 - i / 400) * 0.3)
        draw.line(
            [(0, DOUYIN_COVER_HEIGHT - 400 + i), (DOUYIN_COVER_WIDTH, DOUYIN_COVER_HEIGHT - 400 + i)],
            fill=(0, 0, 0, alpha)
        )

    # Draw recommendation badge at top
    _draw_recommendation_badge(draw, paper_count, font_badge, accent_color)

    # Draw main title (large, centered, wrapped)
    y_offset = 600
    title_lines = _wrap_text(title, font_title, DOUYIN_COVER_WIDTH - 100)
    for line in title_lines[:3]:  # Max 3 lines
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_width = bbox[2] - bbox[0]
        x = (DOUYIN_COVER_WIDTH - line_width) // 2
        draw.text((x, y_offset), line, fill=(255, 255, 255), font=font_title)
        y_offset += 100

    # Draw subtitle
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
        sub_width = bbox[2] - bbox[0]
        x = (DOUYIN_COVER_WIDTH - sub_width) // 2
        draw.text((x, y_offset + 50), subtitle, fill=(180, 180, 180), font=font_subtitle)

    # Draw bottom tag
    tag_text = "关注我 获取更多AI论文"
    bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
    tag_width = bbox[2] - bbox[0]
    x = (DOUYIN_COVER_WIDTH - tag_width) // 2
    draw.text((x, DOUYIN_COVER_HEIGHT - 150), tag_text, fill=(150, 150, 150), font=font_tag)

    # Save
    img.save(output_path, quality=95)
    logger.info(f"Created Douyin cover: {output_path}")

    return output_path


def create_douyin_cover_with_papers(
    papers: list[dict],
    title: str = "AI Agent 论文精选",
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Create a Douyin cover with paper thumbnails in a grid layout.

    Args:
        papers: List of paper dicts with 'arxiv_id' key
        title: Cover title
        output_path: Path to save the image

    Returns:
        Path to created cover, or None if failed
    """
    if output_path is None:
        import time
        output_path = str(DOUYIN_COVERS_DIR / f"douyin_cover_{int(time.time())}.png")

    # Create canvas
    img = Image.new('RGB', (DOUYIN_COVER_WIDTH, DOUYIN_COVER_HEIGHT), (25, 25, 35))
    draw = ImageDraw.Draw(img)

    font_title, font_subtitle, font_badge, font_tag = _load_fonts()

    # Draw header area
    draw.rectangle([(0, 0), (DOUYIN_COVER_WIDTH, 350)], fill=(35, 35, 50))

    # Draw recommendation badge
    _draw_recommendation_badge(draw, len(papers), font_badge, (255, 87, 87))

    # Draw title
    title_lines = _wrap_text(title, font_title, DOUYIN_COVER_WIDTH - 100)
    y = 180
    for line in title_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_width = bbox[2] - bbox[0]
        x = (DOUYIN_COVER_WIDTH - line_width) // 2
        draw.text((x, y), line, fill=(255, 255, 255), font=font_title)
        y += 80

    # Load paper covers
    cover_images = []
    for paper in papers[:9]:  # Max 9 papers
        arxiv_id = paper.get('arxiv_id')
        if arxiv_id:
            path = get_cover_path(arxiv_id)
            if path:
                try:
                    img_p = Image.open(path)
                    if img_p.mode != 'RGB':
                        img_p = img_p.convert('RGB')
                    cover_images.append(img_p)
                except Exception as e:
                    logger.warning(f"Failed to load cover for {arxiv_id}: {e}")

    # Draw paper covers in grid
    if cover_images:
        grid_start_y = 380
        cell_width = 340
        cell_height = 440
        padding = 15

        cols, rows = _calculate_grid(len(cover_images))

        for idx, cover_img in enumerate(cover_images[:cols * rows]):
            row = idx // cols
            col = idx % cols

            # Calculate position
            total_grid_width = cols * cell_width + (cols - 1) * padding
            start_x = (DOUYIN_COVER_WIDTH - total_grid_width) // 2

            x = start_x + col * (cell_width + padding)
            y = grid_start_y + row * (cell_height + padding)

            # Resize and paste
            resized = cover_img.resize((cell_width, cell_height), Image.Resampling.LANCZOS)

            # Add rounded corners effect
            mask = Image.new('L', (cell_width, cell_height), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (cell_width, cell_height)], radius=15, fill=255)

            img.paste(resized, (x, y), mask)

    # Draw bottom tag
    tag_text = "关注我 每日推送AI前沿论文"
    bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
    tag_width = bbox[2] - bbox[0]
    x = (DOUYIN_COVER_WIDTH - tag_width) // 2
    draw.text((x, DOUYIN_COVER_HEIGHT - 100), tag_text, fill=(150, 150, 150), font=font_tag)

    # Save
    img.save(output_path, quality=95)
    logger.info(f"Created Douyin cover with papers: {output_path}")

    return output_path


def _load_fonts():
    """Load fonts for Douyin cover."""
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 72)
        font_subtitle = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 36)
        font_badge = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 32)
        font_tag = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 28)
    except:
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
            font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            font_tag = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
            font_badge = ImageFont.load_default()
            font_tag = ImageFont.load_default()

    return font_title, font_subtitle, font_badge, font_tag


def _draw_recommendation_badge(draw, count: int, font, accent_color: tuple):
    """Draw the recommendation badge at top center."""
    badge_text = f"🔥 今日推荐 {count} 篇"

    # Badge dimensions
    badge_width = 400
    badge_height = 60
    badge_x = (DOUYIN_COVER_WIDTH - badge_width) // 2
    badge_y = 60

    # Draw badge background
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
        radius=30,
        fill=accent_color
    )

    # Draw badge text
    bbox = draw.textbbox((0, 0), badge_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = badge_x + (badge_width - text_width) // 2
    text_y = badge_y + (badge_height - (bbox[3] - bbox[1])) // 2

    draw.text((text_x, text_y), badge_text, fill=(255, 255, 255), font=font)


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    """Wrap text to fit within max_width."""
    lines = []
    words = list(text)  # Chinese: each char is a "word"

    current_line = ""
    for char in words:
        test_line = current_line + char
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char

    if current_line:
        lines.append(current_line)

    return lines


def _calculate_grid(n: int) -> tuple[int, int]:
    """Calculate grid dimensions for n items."""
    if n <= 1:
        return 1, 1
    elif n <= 2:
        return 2, 1
    elif n <= 4:
        return 2, 2
    elif n <= 6:
        return 2, 3
    else:
        return 3, 3


async def create_douyin_cover_async(
    papers: list[dict],
    title: str = "AI Agent 论文精选",
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Create a Douyin cover, downloading paper covers if needed.

    Args:
        papers: List of paper dicts
        title: Cover title
        output_path: Output path

    Returns:
        Path to created cover
    """
    # Ensure paper covers are downloaded
    papers_to_download = []
    for paper in papers:
        arxiv_id = paper.get('arxiv_id')
        if arxiv_id and not get_cover_path(arxiv_id):
            if paper.get('pdf_url'):
                papers_to_download.append(paper)

    if papers_to_download:
        logger.info(f"Downloading {len(papers_to_download)} paper covers...")
        await batch_download_and_screenshot(papers_to_download)

    return create_douyin_cover_with_papers(papers, title, output_path)


if __name__ == "__main__":
    # Test
    test_papers = [
        {"arxiv_id": "2401.00100", "pdf_url": "https://arxiv.org/pdf/2401.00100.pdf"},
        {"arxiv_id": "2401.00101", "pdf_url": "https://arxiv.org/pdf/2401.00101.pdf"},
    ]

    async def test():
        path = await create_douyin_cover_async(test_papers, "AI Agent 论文精选")
        print(f"Created: {path}")

    asyncio.run(test())