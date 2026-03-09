"""
Feishu Webhook client for sending messages to Feishu groups.

Supports:
- Text messages
- Rich text (post) messages
- Interactive card messages
"""
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class FeishuCardAction:
    """Action button for Feishu card."""
    text: str
    url: str


class FeishuWebhookClient:
    """
    Client for sending messages via Feishu custom bot webhook.

    Usage:
        1. Add a custom bot to your Feishu group
        2. Get the webhook URL from bot settings
        3. Use this client to send messages

    Note: Webhook messages can only be sent to the group where the bot is added.
    """

    def __init__(self, webhook_url: str):
        """
        Initialize Feishu webhook client.

        Args:
            webhook_url: Webhook URL from Feishu custom bot settings
        """
        self.webhook_url = webhook_url
        self.timeout = 30.0

    async def send_text(self, text: str) -> Dict[str, Any]:
        """
        Send a simple text message.

        Args:
            text: Text content to send

        Returns:
            API response dict
        """
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        return await self._send_request(payload)

    async def send_post(
        self,
        title: str,
        content: List[List[Dict]],
        subtitle: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a rich text (post) message.

        Args:
            title: Post title
            content: Rich text content (list of paragraphs, each is a list of segments)
            subtitle: Optional subtitle

        Returns:
            API response dict

        Content segment format:
            {"tag": "text", "text": "plain text"}
            {"tag": "a", "text": "link text", "href": "https://..."}
            {"tag": "at", "user_id": "ou_xxx", "text": "@someone"}
        """
        post_content = {
            "zh_cn": {
                "title": title,
                "content": content
            }
        }
        if subtitle:
            post_content["zh_cn"]["subtitle"] = subtitle

        payload = {
            "msg_type": "post",
            "content": {
                "post": post_content
            }
        }
        return await self._send_request(payload)

    async def send_card(
        self,
        title: str,
        elements: List[Dict[str, Any]],
        subtitle: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an interactive card message.

        Args:
            title: Card title
            elements: List of card elements
            subtitle: Optional subtitle

        Returns:
            API response dict

        Element types:
            - {"tag": "div", "text": {"tag": "plain_text", "content": "..."}}
            - {"tag": "markdown", "content": "**bold** text"}
            - {"tag": "hr"}
            - {"tag": "action", "actions": [...]}
        """
        header = {
            "title": {
                "tag": "plain_text",
                "content": title
            },
            "template": "blue"
        }
        if subtitle:
            header["subtitle"] = {
                "tag": "plain_text",
                "content": subtitle
            }

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": header,
                "elements": elements
            }
        }
        return await self._send_request(payload)

    async def send_paper_digest(
        self,
        papers: List[Dict[str, Any]],
        digest_title: str = "📚 每日 AI Agent 论文精选"
    ) -> Dict[str, Any]:
        """
        Send a formatted paper digest card.

        Args:
            papers: List of paper dicts with title, summary, arxiv_id, etc.
            digest_title: Title for the digest

        Returns:
            API response dict
        """
        elements = []

        # Introduction
        elements.append({
            "tag": "markdown",
            "content": f"**{digest_title}**\n今日精选 {len(papers)} 篇论文"
        })
        elements.append({"tag": "hr"})

        # Each paper
        for i, paper in enumerate(papers, 1):
            title = paper.get("title", "Unknown Title")
            arxiv_id = paper.get("arxiv_id", "")
            authors = paper.get("authors", [])[:3]
            author_str = ", ".join(authors) if authors else "Unknown"
            summary = paper.get("summary", paper.get("abstract", ""))[:200]
            highlights = paper.get("highlights", [])
            arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
            code_url = paper.get("code_url", paper.get("github_url", ""))

            # Paper number and title
            elements.append({
                "tag": "markdown",
                "content": f"### {i}. {title[:50]}{'...' if len(title) > 50 else ''}"
            })

            # Authors and tags
            tags = paper.get("tags", [])
            tag_str = " | ".join(tags[:3]) if tags else ""
            elements.append({
                "tag": "markdown",
                "content": f"👥 {author_str}\n🏷️ {tag_str}" if tag_str else f"👥 {author_str}"
            })

            # Summary
            elements.append({
                "tag": "markdown",
                "content": f"💡 {summary}..."
            })

            # Highlights if available
            if highlights:
                highlight_text = "\n".join([f"• {h}" for h in highlights[:3]])
                elements.append({
                    "tag": "markdown",
                    "content": f"**亮点:**\n{highlight_text}"
                })

            # Links
            actions = [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看论文"},
                    "url": arxiv_url,
                    "type": "primary"
                }
            ]
            if code_url:
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "代码"},
                    "url": code_url,
                    "type": "default"
                })

            elements.append({
                "tag": "action",
                "actions": actions
            })

            elements.append({"tag": "hr"})

        # Footer
        elements.append({
            "tag": "markdown",
            "content": "🤖 由 Arxiv Daily Push 自动推送"
        })

        return await self.send_card(
            title=digest_title,
            elements=elements
        )

    async def send_custom_content(
        self,
        card_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a custom card from generated content.

        Args:
            card_content: Dict from feishu_style prompt with:
                - card_title: str
                - card_header: {title, subtitle}
                - elements: list of {type, content/actions}
                - summary_text: str

        Returns:
            API response dict
        """
        # Build card elements from generated content
        elements = []

        card_header = card_content.get("card_header", {})
        header_title = card_header.get("title", card_content.get("card_title", "论文推送"))
        header_subtitle = card_header.get("subtitle", "")

        # Process elements
        for elem in card_content.get("elements", []):
            elem_type = elem.get("type", "")

            if elem_type == "markdown":
                elements.append({
                    "tag": "markdown",
                    "content": elem.get("content", "")
                })
            elif elem_type == "divider":
                elements.append({"tag": "hr"})
            elif elem_type == "action":
                actions = []
                for action in elem.get("actions", []):
                    actions.append({
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": action.get("text", "")},
                        "url": action.get("url", ""),
                        "type": "primary" if action.get("primary", False) else "default"
                    })
                if actions:
                    elements.append({
                        "tag": "action",
                        "actions": actions
                    })

        return await self.send_card(
            title=header_title,
            elements=elements,
            subtitle=header_subtitle if header_subtitle else None
        )

    async def send_review_card(
        self,
        papers: List[Dict[str, Any]],
        review_url: str,
        expire_hours: int = 2
    ) -> Dict[str, Any]:
        """
        Send a review card to Feishu group.

        Args:
            papers: List of paper dicts to review
            review_url: URL to the review page
            expire_hours: Hours until the review link expires

        Returns:
            API response dict
        """
        elements = []

        # Header
        elements.append({
            "tag": "markdown",
            "content": f"**📋 论文发布审核请求**\n待审核 **{len(papers)}** 篇论文"
        })
        elements.append({"tag": "hr"})

        # Paper summaries
        for i, paper in enumerate(papers[:10], 1):  # Show max 10 papers
            title = paper.get("title", "Unknown")[:60]
            score = paper.get("total_score", 0)
            citations = paper.get("citation_count", 0)

            elements.append({
                "tag": "markdown",
                "content": f"**{i}. {title}**\n评分: {score:.1f} | 引用: {citations}"
            })

        if len(papers) > 10:
            elements.append({
                "tag": "markdown",
                "content": f"... 还有 {len(papers) - 10} 篇论文"
            })

        elements.append({"tag": "hr"})

        # Review button
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "🔍 点击审核"},
                    "url": review_url,
                    "type": "primary"
                }
            ]
        })

        # Expiry notice
        elements.append({
            "tag": "markdown",
            "content": f"⏰ 链接有效期: {expire_hours}小时"
        })

        return await self.send_card(
            title="论文发布审核",
            elements=elements
        )

    async def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send HTTP request to Feishu webhook.

        Args:
            payload: Request payload

        Returns:
            Response dict
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                result = response.json()

                if result.get("code") == 0 or result.get("StatusCode") == 0:
                    logger.info(f"Feishu message sent successfully")
                    return {"success": True, "response": result}
                else:
                    logger.error(f"Feishu API error: {result}")
                    return {"success": False, "error": str(result)}

        except httpx.TimeoutException:
            logger.error("Feishu webhook timeout")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            logger.error(f"Failed to send Feishu message: {e}")
            return {"success": False, "error": str(e)}


# Singleton client instance
_feishu_client: Optional[FeishuWebhookClient] = None


def get_feishu_client(webhook_url: Optional[str] = None) -> Optional[FeishuWebhookClient]:
    """
    Get or create Feishu webhook client.

    Args:
        webhook_url: Optional webhook URL (uses settings if not provided)

    Returns:
        FeishuWebhookClient or None if not configured
    """
    global _feishu_client

    if webhook_url:
        _feishu_client = FeishuWebhookClient(webhook_url)
        return _feishu_client

    if _feishu_client is not None:
        return _feishu_client

    from config.settings import settings
    if settings.FEISHU_WEBHOOK_URL:
        _feishu_client = FeishuWebhookClient(settings.FEISHU_WEBHOOK_URL)
        return _feishu_client

    return None


async def send_test_message(webhook_url: str) -> bool:
    """
    Send a test message to verify webhook configuration.

    Args:
        webhook_url: Feishu webhook URL

    Returns:
        True if successful, False otherwise
    """
    client = FeishuWebhookClient(webhook_url)
    result = await client.send_text("🎉 飞书机器人配置成功！\n\n这是来自 Arxiv Daily Push 的测试消息。")
    return result.get("success", False)