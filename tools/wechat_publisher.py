"""
WeChat Official Account (微信公众号) publishing tool.

Provides utilities for publishing content to WeChat Official Account
via the WeChat MP API.
"""
import json
import random
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from config.settings import settings


class WeChatMPClient:
    """
    Client for WeChat Official Account API.

    Supports:
    - Access token management
    - Image upload
    - Draft creation
    - Article publishing
    """

    def __init__(self, app_id: str = None, app_secret: str = None):
        """
        Initialize WeChat MP client.

        Args:
            app_id: WeChat App ID (uses settings if not provided)
            app_secret: WeChat App Secret (uses settings if not provided)
        """
        self.app_id = app_id or settings.WECHAT_APP_ID
        self.app_secret = app_secret or settings.WECHAT_APP_SECRET
        self.timeout = 30.0
        self._access_token = None
        self._token_expires_at = None

    async def get_access_token(self) -> str:
        """
        Get WeChat access token.

        Returns:
            Access token string

        Raises:
            ValueError: If token retrieval fails
        """
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            result = response.json()

        if "access_token" in result:
            self._access_token = result["access_token"]
            # Token expires in 7200 seconds, refresh 5 minutes early
            expires_in = result.get("expires_in", 7200) - 300
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            logger.info("WeChat access token obtained")
            return self._access_token
        else:
            raise ValueError(f"Failed to get access token: {result}")

    async def upload_image(self, image_data: bytes, filename: str = "cover.jpg") -> str:
        """
        Upload image to WeChat material library.

        Args:
            image_data: Image binary data
            filename: Image filename

        Returns:
            Media ID of uploaded image

        Raises:
            ValueError: If upload fails
        """
        token = await self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
        params = {
            "access_token": token,
            "type": "thumb"
        }

        files = {
            "media": (filename, image_data, "image/jpeg")
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, params=params, files=files)
            result = response.json()

        if "media_id" in result:
            logger.info(f"Image uploaded: {result['media_id']}")
            return result["media_id"]
        else:
            raise ValueError(f"Failed to upload image: {result}")

    async def upload_image_from_path(self, image_path: str) -> str:
        """
        Upload image from local path.

        Args:
            image_path: Local image file path

        Returns:
            Media ID of uploaded image
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(path, "rb") as f:
            image_data = f.read()

        return await self.upload_image(image_data, path.name)

    async def create_draft(self, articles: List[Dict[str, Any]]) -> str:
        """
        Create a draft with one or more articles.

        Args:
            articles: List of article dicts with:
                - title: Article title
                - author: Author name
                - digest: Article summary
                - content: HTML content
                - thumb_media_id: Cover image media ID
                - content_source_url: Original URL (optional)

        Returns:
            Media ID of created draft

        Raises:
            ValueError: If draft creation fails
        """
        token = await self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/draft/add"
        params = {"access_token": token}

        data = {"articles": articles}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params=params, json=data)
            result = response.json()

        if "media_id" in result:
            logger.info(f"Draft created: {result['media_id']}")
            return result["media_id"]
        else:
            raise ValueError(f"Failed to create draft: {result}")

    async def publish_draft(self, media_id: str) -> str:
        """
        Publish a draft.

        Args:
            media_id: Draft media ID

        Returns:
            Publish ID

        Raises:
            ValueError: If publish fails
        """
        token = await self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
        params = {"access_token": token}

        data = {"media_id": media_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params=params, json=data)
            result = response.json()

        if "publish_id" in result:
            logger.info(f"Draft published: {result['publish_id']}")
            return result["publish_id"]
        else:
            raise ValueError(f"Failed to publish: {result}")

    async def get_draft_list(self, offset: int = 0, count: int = 10) -> List[Dict]:
        """
        Get list of drafts.

        Args:
            offset: Offset for pagination
            count: Number of drafts to retrieve (max 20)

        Returns:
            List of draft dicts
        """
        token = await self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/draft/getdraft"
        params = {"access_token": token}

        data = {"offset": offset, "count": min(count, 20)}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params=params, json=data)
            result = response.json()

        if "item" in result:
            return result["item"]
        else:
            logger.warning(f"Failed to get draft list: {result}")
            return []

    async def delete_draft(self, media_id: str) -> bool:
        """
        Delete a draft.

        Args:
            media_id: Draft media ID

        Returns:
            True if successful
        """
        token = await self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/draft/delete"
        params = {"access_token": token}

        data = {"media_id": media_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params=params, json=data)
            result = response.json()

        if result.get("errcode") == 0:
            logger.info(f"Draft deleted: {media_id}")
            return True
        else:
            logger.error(f"Failed to delete draft: {result}")
            return False

    async def get_publish_status(self, publish_id: str) -> Dict:
        """
        Get status of a publish task.

        Args:
            publish_id: Publish ID from publish_draft()

        Returns:
            Status dict with publish_status and article details
        """
        token = await self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/freepublish/get"
        params = {"access_token": token}

        data = {"publish_id": publish_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params=params, json=data)
            result = response.json()

        return result


def create_cover_image(
    title: str,
    subtitle: str = "每日精选高质量论文",
    output_path: str = None
) -> bytes:
    """
    Create a professional cover image for WeChat article.

    Args:
        title: Main title
        subtitle: Subtitle
        output_path: Optional path to save image

    Returns:
        Image binary data
    """
    width, height = 900, 500

    # Create gradient background
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    # Gradient from blue to darker blue
    color1 = (26, 115, 232)
    color2 = (13, 71, 161)

    for y in range(height):
        r = int(color1[0] + (color2[0] - color1[0]) * y / height)
        g = int(color1[1] + (color2[1] - color1[1]) * y / height)
        b = int(color1[2] + (color2[2] - color1[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Add network nodes decoration
    random.seed(42)
    nodes = []
    for _ in range(25):
        x = random.randint(50, width - 50)
        y = random.randint(50, height - 50)
        r = random.randint(3, 8)
        nodes.append((x, y, r))

        # Draw node glow
        for i in range(3):
            glow_r = r + i * 3
            draw.ellipse(
                [x - glow_r, y - glow_r, x + glow_r, y + glow_r],
                fill=(255, 255, 255)
            )

    # Draw connections
    for i, (x1, y1, _) in enumerate(nodes):
        for x2, y2, _ in nodes[i+1:]:
            if random.random() > 0.7:
                draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255), width=1)

    # Load fonts
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 56)
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 28)
        small_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 18)
    except:
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 56)
            subtitle_font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 28)
            small_font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 18)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = title_font
            small_font = title_font

    # Draw title background
    title_bg_height = 180
    draw.rectangle(
        [(0, height // 2 - title_bg_height // 2 - 20),
         (width, height // 2 + title_bg_height // 2 + 20)],
        fill=(0, 0, 0)
    )

    # Draw main title
    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = height // 2 - 70

    draw.text((text_x + 2, text_y + 2), title, fill=(0, 0, 0), font=title_font)
    draw.text((text_x, text_y), title, fill=(255, 255, 255), font=title_font)

    # Draw subtitle
    bbox2 = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    text_width2 = bbox2[2] - bbox2[0]
    text_x2 = (width - text_width2) // 2
    text_y2 = height // 2 + 30

    draw.text((text_x2, text_y2), subtitle, fill=(200, 230, 255), font=subtitle_font)

    # Add decorative elements
    draw.rectangle([(50, height // 2 - 90), (55, height // 2 + 70)], fill=(255, 255, 255))
    draw.rectangle([(width - 55, height // 2 - 90), (width - 50, height // 2 + 70)], fill=(255, 255, 255))

    # Bottom label
    bottom_text = "arXiv Daily · AI Agent Research"
    bbox3 = draw.textbbox((0, 0), bottom_text, font=small_font)
    text_width3 = bbox3[2] - bbox3[0]
    draw.text(
        ((width - text_width3) // 2, height - 35),
        bottom_text,
        fill=(180, 200, 220),
        font=small_font
    )

    # Save to buffer
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)
    image_data = buffer.getvalue()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)

    return image_data


def format_article_content(
    papers: List[Dict],
    summaries: List[Dict],
    title: str = "AI Agent 论文精选"
) -> str:
    """
    Format papers as WeChat article HTML content.

    Args:
        papers: List of paper dicts
        summaries: List of summary dicts
        title: Article title

    Returns:
        HTML content string
    """
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Build paper sections
    paper_sections = []
    for i, (paper, summary) in enumerate(zip(papers, summaries), 1):
        paper_title = paper.get("title", "Unknown Title")
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            authors = ", ".join(authors[:3])
        arxiv_url = paper.get("abs_url", f"https://arxiv.org/abs/{paper.get('arxiv_id', '')}")

        summary_text = summary.get("summary", paper.get("abstract", ""))[:300]
        highlights = summary.get("highlights", [])

        section = f"""
<div style="background: white; border-radius: 12px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
<h3 style="color: #1a73e8; margin: 0 0 15px 0; font-size: 20px;">
📝 论文 {i}: {paper_title[:60]}{'...' if len(paper_title) > 60 else ''}
</h3>
<p style="color: #666; font-size: 14px; margin: 0 0 15px 0;">
👥 {authors}
</p>
<p style="color: #333; font-size: 16px; line-height: 1.8; margin: 0 0 15px 0;">
{summary_text}...
</p>
"""
        if highlights:
            section += '<ul style="margin: 0; padding-left: 20px; color: #333; font-size: 14px;">'
            for h in highlights[:3]:
                section += f'<li style="margin-bottom: 8px;">{h}</li>'
            section += '</ul>'

        section += f"""
<p style="margin: 15px 0 0 0;">
<a href="{arxiv_url}" style="color: #1a73e8; text-decoration: none; font-size: 14px;">🔗 查看论文原文 →</a>
</p>
</div>
"""
        paper_sections.append(section)

    papers_html = "\n".join(paper_sections)

    html_content = f"""
<section style="padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa;">
<div style="max-width: 100%; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">

<!-- Header -->
<div style="background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%); padding: 30px; text-align: center;">
<h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600;">
🤖 {title}
</h1>
<p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">
每日精选 {len(papers)} 篇高质量论文
</p>
</div>

<!-- Content -->
<div style="padding: 30px;">
{papers_html}
</div>

<!-- Footer -->
<div style="background: #f5f5f5; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
<p style="color: #999; font-size: 14px; margin: 0;">
本文由 <strong style="color: #1a73e8;">AI Agent 论文推荐系统</strong> 自动生成
</p>
<p style="color: #bbb; font-size: 12px; margin: 8px 0 0 0;">
生成时间：{current_time}
</p>
</div>

</div>
</section>
"""
    return html_content


# Singleton client
_wechat_client: Optional[WeChatMPClient] = None


def get_wechat_client() -> Optional[WeChatMPClient]:
    """
    Get or create WeChat MP client.

    Returns:
        WeChatMPClient or None if not configured
    """
    global _wechat_client

    if _wechat_client is not None:
        return _wechat_client

    if settings.WECHAT_APP_ID and settings.WECHAT_APP_SECRET:
        _wechat_client = WeChatMPClient()
        return _wechat_client

    return None


__all__ = [
    "WeChatMPClient",
    "create_cover_image",
    "format_article_content",
    "get_wechat_client",
]