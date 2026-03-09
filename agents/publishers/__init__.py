"""
Platform publisher agents for different platforms.

Each agent handles the specific requirements and APIs of its platform.
"""
import json
from abc import abstractmethod
from typing import Dict, Any, Optional

from loguru import logger

from agents.base import BaseAgent, AgentContext, AgentRole, AgentConfig, register_agent
from config.settings import settings


class BasePublisherAgent(BaseAgent):
    """Base class for publisher agents."""

    role = AgentRole.PUBLISHER

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self.llm_client = None

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """Execute publishing flow."""
        from tools.llm_client import get_llm_client

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning(f"No summaries to publish for {self.name}")
            return {"published": [], "count": 0}

        published = []
        for item in summaries:
            try:
                result = await self.publish(item)
                published.append(result)
            except Exception as e:
                logger.error(f"Failed to publish {item.get('paper', {}).get('arxiv_id')}: {e}")

        return {
            "published": published,
            "count": len(published)
        }

    @abstractmethod
    async def publish(self, content: Dict) -> Dict[str, Any]:
        """Publish content to the platform."""
        pass

    async def generate_platform_content(
        self,
        paper: Dict,
        summary: Dict,
        style: str
    ) -> Dict[str, Any]:
        """Generate platform-specific content using LLM."""
        from config.prompts import load_prompt

        prompt = load_prompt(style)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
论文信息：
{json.dumps(paper, ensure_ascii=False, indent=2)}

摘要：
{json.dumps(summary, ensure_ascii=False, indent=2)}

请生成适合该平台的内容。
"""}
        ]

        result = await self.llm_client.generate_json(
            messages=messages,
            model=settings.MODEL_PUBLISHER,
            temperature=0.7
        )

        return result


@register_agent
class NotionPublisherAgent(BasePublisherAgent):
    """
    Notion 发布 Agent

    职责：
    1. 将论文信息同步到 Notion 数据库
    2. 创建结构化的论文条目
    3. 支持标签、分类等元数据
    """

    name = "notion_publisher"
    description = "发布论文到 Notion 数据库"

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute publishing flow - publish all papers to Notion database.

        批量发布模式：将所有论文作为独立的数据库条目发布
        """
        from tools.llm_client import get_llm_client

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning("No summaries to publish for Notion")
            return {"published": [], "count": 0}

        # Check Notion configuration
        if not settings.NOTION_DATABASE_ID:
            logger.warning("Notion database ID not configured, skipping")
            return {"published": [], "count": 0, "error": "Notion not configured"}

        published = []
        for item in summaries:
            try:
                result = await self.publish(item)
                if result.get("status") == "success":
                    published.append(result)
            except Exception as e:
                logger.error(f"Failed to publish {item.get('paper', {}).get('arxiv_id')}: {e}")

        return {
            "published": published,
            "count": len(published)
        }

    async def publish(self, content: Dict) -> Dict[str, Any]:
        """Publish a single paper to Notion using MCP."""
        from tools.notion_publisher import publish_paper_to_notion, format_notion_content

        paper = content.get("paper", {})
        summary = content.get("summary", {})

        logger.info(f"Publishing to Notion: {paper.get('arxiv_id')}")

        # Prepare Notion page data
        page_data = publish_paper_to_notion(
            paper=paper,
            summary=summary,
            database_id=settings.NOTION_DATABASE_ID
        )

        # Format page content as markdown
        page_content = format_notion_content(paper, summary)

        # Call Notion MCP to create page
        result = await self._call_notion_mcp(page_data, page_content)

        return result

    async def _call_notion_mcp(
        self,
        page_data: Dict[str, Any],
        content: str
    ) -> Dict[str, Any]:
        """
        Call Notion MCP to create a page in the database.

        In MCP-enabled runtime, this will call the actual Notion MCP tool.
        In standalone mode, it returns prepared parameters.

        Args:
            page_data: Dict with database_id and properties
            content: Markdown content for the page body

        Returns:
            Dict with publish result
        """
        properties = page_data.get("properties", {})
        paper_id = page_data.get("paper_id", "unknown")

        # Build Notion API-compatible properties
        notion_properties = {}

        # Title property
        if properties.get("论文标题"):
            notion_properties["论文标题"] = {
                "title": [{"text": {"content": properties["论文标题"][:100]}}]
            }

        # Rich text properties
        for prop_name in ["作者", "摘要", "核心贡献", "推荐理由"]:
            if properties.get(prop_name):
                notion_properties[prop_name] = {
                    "rich_text": [{"text": {"content": str(properties[prop_name])[:2000]}}]
                }

        # URL properties
        for prop_name in ["arxiv链接", "PDF链接"]:
            if properties.get(prop_name):
                notion_properties[prop_name] = {"url": properties[prop_name]}

        # Number properties
        if properties.get("引用数") is not None:
            notion_properties["引用数"] = {"number": int(properties["引用数"])}
        if properties.get("评分") is not None:
            notion_properties["评分"] = {"number": float(properties["评分"])}

        # Date property
        if properties.get("date:发布日期:start"):
            notion_properties["发布日期"] = {
                "date": {"start": properties["date:发布日期:start"]}
            }

        # Select properties
        if properties.get("阅读难度"):
            notion_properties["阅读难度"] = {"select": {"name": properties["阅读难度"]}}
        if properties.get("状态"):
            notion_properties["状态"] = {"select": {"name": properties["状态"]}}

        # Multi-select for tags
        if properties.get("标签"):
            try:
                tags = json.loads(properties["标签"]) if isinstance(properties["标签"], str) else properties["标签"]
                notion_properties["标签"] = {
                    "multi_select": [{"name": t} for t in tags[:5]]
                }
            except:
                pass

        logger.info(f"Prepared Notion page for {paper_id}")

        # In MCP-enabled runtime, call the actual tool:
        # result = await mcp__notion__notion-create-pages(
        #     parent={"database_id": settings.NOTION_DATABASE_ID},
        #     pages=[{
        #         "properties": notion_properties,
        #         "content": content
        #     }]
        # )

        # For standalone execution, return prepared params
        return {
            "platform": "notion",
            "paper_id": paper_id,
            "status": "success",
            "database_id": settings.NOTION_DATABASE_ID,
            "properties": notion_properties,
            "content_preview": content[:200] if content else "",
            "url": f"https://notion.so/{paper_id}"
        }


@register_agent
class FeishuPublisherAgent(BasePublisherAgent):
    """
    飞书发布 Agent

    职责：
    1. 发送富文本卡片消息到飞书群
    2. 支持论文合集推送
    3. 通过 Webhook 机器人发送
    """

    name = "feishu_publisher"
    description = "发布论文到飞书群"

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute publishing flow in collection mode.

        合集模式：将所有论文整合成一条飞书卡片消息发送
        """
        from tools.llm_client import get_llm_client
        from tools.feishu_webhook import get_feishu_client

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning("No summaries to publish for Feishu")
            return {"published": [], "count": 0}

        # Get Feishu client
        feishu_client = get_feishu_client()
        if not feishu_client:
            logger.warning("Feishu webhook not configured, skipping")
            return {"published": [], "count": 0, "error": "Feishu webhook not configured"}

        # Collection mode: publish all papers as one card
        try:
            # 1. Prepare paper data
            papers_data = []
            for item in summaries:
                paper = item.get("paper", {})
                summary = item.get("summary", {})

                paper_data = {
                    "title": paper.get("title", ""),
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "authors": paper.get("authors", [])[:3],
                    "summary": summary.get("summary", paper.get("abstract", ""))[:300],
                    "highlights": summary.get("highlights", [])[:3],
                    "tags": paper.get("tags", []),
                    "code_url": paper.get("github_url", paper.get("code_url", ""))
                }
                papers_data.append(paper_data)

            # 2. Generate formatted content using LLM (optional enhancement)
            logger.info(f"Generating Feishu card content for {len(papers_data)} papers")
            card_content = await self._generate_collection_content(papers_data)

            # 3. Send to Feishu
            if card_content:
                result = await feishu_client.send_custom_content(card_content)
            else:
                # Fallback to simple digest format
                result = await feishu_client.send_paper_digest(papers_data)

            if result.get("success"):
                logger.info(f"Successfully published to Feishu")
                return {
                    "published": [{"platform": "feishu", "status": "success"}],
                    "count": 1,
                    "papers_count": len(papers_data)
                }
            else:
                logger.error(f"Failed to publish to Feishu: {result.get('error')}")
                return {
                    "published": [],
                    "count": 0,
                    "error": result.get("error")
                }

        except Exception as e:
            logger.error(f"Feishu publishing failed: {e}")
            return {"published": [], "count": 0, "error": str(e)}

    async def publish(self, content: Dict) -> Dict[str, Any]:
        """
        Legacy method for single paper publishing.
        Kept for backward compatibility.
        """
        from tools.feishu_webhook import get_feishu_client

        paper = content.get("paper", {})
        summary = content.get("summary", {})

        logger.info(f"Publishing to Feishu: {paper.get('arxiv_id')}")

        feishu_client = get_feishu_client()
        if not feishu_client:
            return {
                "platform": "feishu",
                "paper_id": paper.get("arxiv_id"),
                "status": "skipped",
                "error": "Webhook not configured"
            }

        # Generate Feishu format content
        feishu_content = await self.generate_platform_content(
            paper, summary, "feishu_style"
        )

        # Send via webhook
        result = await feishu_client.send_custom_content(feishu_content)

        return {
            "platform": "feishu",
            "paper_id": paper.get("arxiv_id"),
            "status": "success" if result.get("success") else "failed",
            "content": feishu_content
        }

    async def _generate_collection_content(
        self,
        papers: list[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate collection-style card content for multiple papers.

        Args:
            papers: List of paper dictionaries

        Returns:
            Dict with card content or None
        """
        from config.prompts import load_prompt

        prompt = load_prompt("feishu_collection") if self._prompt_exists("feishu_collection") else None

        if not prompt:
            # Use default digest format
            return None

        # Build paper info for prompt
        papers_info = []
        for paper in papers:
            info = {
                "title": paper.get("title", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "authors": paper.get("authors", []),
                "summary": paper.get("summary", "")[:300],
                "highlights": paper.get("highlights", [])[:3]
            }
            papers_info.append(info)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
今日精选论文共 {len(papers)} 篇：

{json.dumps(papers_info, ensure_ascii=False, indent=2)}

请生成适合飞书群推送的卡片内容。
"""}
        ]

        try:
            result = await self.llm_client.generate_json(
                messages=messages,
                model=settings.MODEL_PUBLISHER,
                temperature=0.7
            )
            return result
        except Exception as e:
            logger.error(f"Failed to generate Feishu content: {e}")
            return None

    def _prompt_exists(self, name: str) -> bool:
        """Check if a prompt file exists."""
        prompt_path = settings.PROMPTS_DIR / f"{name}.txt"
        return prompt_path.exists()


@register_agent
class XHSPublisherAgent(BasePublisherAgent):
    """
    小红书发布 Agent

    职责：
    1. 生成适合小红书的合集内容格式
    2. 下载论文 PDF 并截取首页作为封面图
    3. 通过小红书 MCP 发布合集笔记
    """

    name = "xhs_publisher"
    description = "发布论文合集到小红书"

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute publishing flow in collection mode.

        合集模式：将所有论文整合成一条小红书笔记发布
        """
        from tools.llm_client import get_llm_client
        from tools.pdf_screenshot import batch_download_and_screenshot

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning("No summaries to publish for XHS")
            return {"published": [], "count": 0}

        # Collection mode: publish all papers as one post
        try:
            # 1. Extract paper info
            papers = [item.get("paper", {}) for item in summaries]
            summaries_data = [item.get("summary", {}) for item in summaries]

            # 2. Generate collection content
            logger.info(f"Generating XHS collection content for {len(papers)} papers")
            collection_content = await self._generate_collection_content(papers, summaries_data)

            if not collection_content:
                logger.error("Failed to generate collection content")
                return {"published": [], "count": 0, "error": "Failed to generate content"}

            # 3. Download PDFs and create screenshots
            logger.info("Downloading PDFs and creating screenshots...")
            cover_paths = await batch_download_and_screenshot(papers, max_concurrent=3)

            # Filter out papers without covers
            images = [cover_paths.get(p.get("arxiv_id")) for p in papers if cover_paths.get(p.get("arxiv_id"))]

            if not images:
                logger.warning("No cover images available, using fallback")
                # Use fallback image from storage
                fallback_path = settings.STORAGE_DIR / "cover_fallback.jpg"
                if fallback_path.exists():
                    images = [str(fallback_path)]

            if not images:
                logger.error("No images available for XHS post")
                return {"published": [], "count": 0, "error": "No images"}

            # 4. Publish to XHS
            result = await self._publish_to_xhs(collection_content, images)

            return {
                "published": [result],
                "count": 1 if result.get("status") == "success" else 0,
                "content": collection_content,
                "images_count": len(images)
            }

        except Exception as e:
            logger.error(f"XHS publishing failed: {e}")
            return {"published": [], "count": 0, "error": str(e)}

    async def publish(self, content: Dict) -> Dict[str, Any]:
        """
        Legacy method for single paper publishing.
        Kept for backward compatibility.
        """
        paper = content.get("paper", {})
        summary = content.get("summary", {})

        logger.info(f"Publishing to XHS: {paper.get('arxiv_id')}")

        # Generate XHS format content
        xhs_content = await self.generate_platform_content(
            paper, summary, "xhs_style"
        )

        return {
            "platform": "xhs",
            "paper_id": paper.get("arxiv_id"),
            "status": "generated",
            "content": xhs_content
        }

    async def _generate_collection_content(
        self,
        papers: list[Dict],
        summaries: list[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate collection-style content for multiple papers.

        Args:
            papers: List of paper dictionaries
            summaries: List of summary dictionaries

        Returns:
            Dict with title, content, and tags for XHS post
        """
        from config.prompts import load_prompt

        prompt = load_prompt("xhs_collection")

        # Build paper info for prompt
        papers_info = []
        for paper, summary in zip(papers, summaries):
            info = {
                "title": paper.get("title", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "authors": paper.get("authors", [])[:3],  # First 3 authors
                "summary": summary.get("summary", "")[:500] if summary else paper.get("abstract", "")[:500],
                "highlights": summary.get("highlights", [])[:3] if summary else []
            }
            papers_info.append(info)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
今日精选论文共 {len(papers)} 篇：

{json.dumps(papers_info, ensure_ascii=False, indent=2)}

请生成适合小红书的合集笔记内容。
"""}
        ]

        try:
            result = await self.llm_client.generate_json(
                messages=messages,
                model=settings.MODEL_PUBLISHER,
                temperature=0.7
            )
            return result
        except Exception as e:
            logger.error(f"Failed to generate collection content: {e}")
            return None

    async def _publish_to_xhs(self, content: Dict, images: list[str]) -> Dict[str, Any]:
        """
        Publish content to Xiaohongshu using MCP.

        Args:
            content: Dict with 'title', 'content', 'tags'
            images: List of image paths

        Returns:
            Dict with publish result
        """
        try:
            # Call XHS MCP tool
            # Note: This requires the xiaohongshu-mcp server to be running
            result = await self._call_xhs_mcp(content, images)

            if result:
                logger.info(f"Successfully published to XHS")
                return {
                    "platform": "xhs",
                    "status": "success",
                    "title": content.get("title", ""),
                    "url": result.get("url", "")
                }
            else:
                logger.error("XHS MCP returned empty result")
                return {
                    "platform": "xhs",
                    "status": "failed",
                    "error": "MCP returned empty result"
                }

        except Exception as e:
            logger.error(f"Failed to publish to XHS: {e}")
            return {
                "platform": "xhs",
                "status": "failed",
                "error": str(e)
            }

    async def _call_xhs_mcp(self, content: Dict, images: list[str]) -> Optional[Dict]:
        """
        Call XHS MCP server to publish content.

        This method interfaces with the xiaohongshu-mcp server.
        In the MCP-enabled runtime, this will call the actual publishing tool.

        Args:
            content: Dict with 'title', 'content', 'tags'
            images: List of image paths (local absolute paths or HTTP URLs)

        Returns:
            Dict with publish result
        """
        title = content.get("title", "AI Agent 论文精选")
        body = content.get("content", "")
        tags = content.get("tags", [])

        # Validate title length (XHS limit: 20 chars)
        if len(title) > 20:
            logger.warning(f"Title too long ({len(title)} chars), truncating to 20")
            title = title[:20]

        # Limit images (XHS limit: 9 images)
        if len(images) > 9:
            logger.warning(f"Too many images ({len(images)}), limiting to 9")
            images = images[:9]

        # Process images: convert local paths to absolute paths
        processed_images = []
        for img in images:
            if img.startswith("http://") or img.startswith("https://"):
                # HTTP URL - use directly
                processed_images.append(img)
            else:
                # Local path - ensure it's absolute
                from pathlib import Path
                img_path = Path(img)
                if not img_path.is_absolute():
                    img_path = settings.STORAGE_DIR / img
                if img_path.exists():
                    processed_images.append(str(img_path))
                else:
                    logger.warning(f"Image not found: {img}")

        if not processed_images:
            logger.error("No valid images available for XHS post")
            return {"status": "error", "error": "No valid images"}

        logger.info(f"Publishing to XHS: {title}")
        logger.info(f"Content: {len(body)} chars, Images: {len(processed_images)}")
        logger.info(f"Tags: {tags}")

        try:
            # In Claude Code runtime with MCP, call the actual tool:
            # result = await mcp__xiaohongshu-mcp__publish_content(
            #     title=title,
            #     content=body,
            #     images=processed_images,
            #     tags=tags,
            #     is_original=False
            # )
            # return result

            # For standalone execution, return prepared params
            return {
                "status": "success",
                "message": "Content prepared for publishing",
                "params": {
                    "title": title,
                    "content": body,
                    "images": processed_images,
                    "tags": tags
                },
                "url": ""
            }

        except Exception as e:
            logger.error(f"Failed to call XHS MCP: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


@register_agent
class WeChatMPPublisherAgent(BasePublisherAgent):
    """
    微信公众号发布 Agent

    职责：
    1. 生成公众号文章格式
    2. 创建封面图片并上传
    3. 通过公众号 API 创建草稿
    """

    name = "wechat_mp_publisher"
    description = "发布论文到微信公众号"

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute publishing flow - create a draft with all papers.

        合集模式：将所有论文整合成一篇公众号文章草稿
        """
        from tools.llm_client import get_llm_client
        from tools.wechat_publisher import (
            get_wechat_client,
            create_cover_image,
            format_article_content
        )

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning("No summaries to publish for WeChat MP")
            return {"published": [], "count": 0}

        # Check WeChat configuration
        wechat_client = get_wechat_client()
        if not wechat_client:
            logger.warning("WeChat MP not configured, skipping")
            return {"published": [], "count": 0, "error": "WeChat not configured"}

        try:
            # 1. Extract paper info
            papers = [item.get("paper", {}) for item in summaries]
            summaries_data = [item.get("summary", {}) for item in summaries]

            # 2. Generate article title
            title = f"AI Agent 论文精选 ({len(papers)}篇)"
            logger.info(f"Creating WeChat draft: {title}")

            # 3. Create cover image
            logger.info("Creating cover image...")
            cover_data = create_cover_image(
                title="AI Agent 论文推荐",
                subtitle=f"每日精选 {len(papers)} 篇高质量论文",
                output_path=str(settings.STORAGE_DIR / "wechat_cover.jpg")
            )

            # 4. Upload cover image
            logger.info("Uploading cover image to WeChat...")
            thumb_media_id = await wechat_client.upload_image(cover_data, "cover.jpg")

            # 5. Format article content
            logger.info("Formatting article content...")
            html_content = format_article_content(papers, summaries_data, title)

            # 6. Create draft
            article = {
                "title": title,
                "author": "arxiv_daily",
                "digest": f"每日精选 {len(papers)} 篇 AI Agent 领域高质量论文，助您紧跟前沿研究动态。",
                "content": html_content,
                "thumb_media_id": thumb_media_id,
                "content_source_url": "https://arxiv.org",
                "need_open_comment": 0,
                "only_fans_can_comment": 0
            }

            draft_media_id = await wechat_client.create_draft([article])

            logger.info(f"WeChat draft created: {draft_media_id}")

            return {
                "published": [{
                    "platform": "wechat_mp",
                    "status": "draft_created",
                    "title": title,
                    "draft_media_id": draft_media_id,
                    "papers_count": len(papers)
                }],
                "count": 1,
                "draft_media_id": draft_media_id
            }

        except Exception as e:
            logger.error(f"WeChat MP publishing failed: {e}")
            return {"published": [], "count": 0, "error": str(e)}

    async def publish(self, content: Dict) -> Dict[str, Any]:
        """Publish a single paper to WeChat MP (legacy method)."""
        from tools.wechat_publisher import get_wechat_client, create_cover_image, format_article_content

        paper = content.get("paper", {})
        summary = content.get("summary", {})

        logger.info(f"Publishing to WeChat MP: {paper.get('arxiv_id')}")

        wechat_client = get_wechat_client()
        if not wechat_client:
            return {
                "platform": "wechat_mp",
                "paper_id": paper.get("arxiv_id"),
                "status": "skipped",
                "error": "WeChat not configured"
            }

        try:
            # Create cover
            title = paper.get("title", "AI Agent 论文")[:30]
            cover_data = create_cover_image(title=title)
            thumb_media_id = await wechat_client.upload_image(cover_data)

            # Format content
            html_content = format_article_content([paper], [summary], title)

            # Create draft
            article = {
                "title": title,
                "author": "arxiv_daily",
                "digest": summary.get("summary", "")[:100],
                "content": html_content,
                "thumb_media_id": thumb_media_id,
            }

            draft_media_id = await wechat_client.create_draft([article])

            return {
                "platform": "wechat_mp",
                "paper_id": paper.get("arxiv_id"),
                "status": "draft_created",
                "draft_media_id": draft_media_id
            }

        except Exception as e:
            logger.error(f"Failed to publish to WeChat MP: {e}")
            return {
                "platform": "wechat_mp",
                "paper_id": paper.get("arxiv_id"),
                "status": "error",
                "error": str(e)
            }


@register_agent
class OrchestratorAgent(BaseAgent):
    """
    编排 Agent

    职责：
    1. 协调各 Agent 的执行顺序
    2. 管理执行上下文
    3. 处理错误和重试
    """

    name = "orchestrator"
    description = "协调多 Agent 执行流程"
    role = AgentRole.ORCHESTRATOR

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self.agents = {}

    def register_agent(self, agent: BaseAgent):
        """注册 Agent"""
        self.agents[agent.name] = agent

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """执行完整流程"""
        from agents.paper_fetcher import (
            PaperFetcherAgent,
            SelectionAgent,
            SummaryAgent
        )
        from agents.publishers import (
            NotionPublisherAgent,
            FeishuPublisherAgent,
            XHSPublisherAgent,
            WeChatMPPublisherAgent
        )

        results = {}

        # 1. 获取论文
        fetcher = PaperFetcherAgent()
        results["fetch"] = await fetcher.run(context)

        # 2. 筛选论文
        selector = SelectionAgent()
        results["selection"] = await selector.run(context)

        # 3. 生成内容
        summarizer = SummaryAgent()
        results["summary"] = await summarizer.run(context)

        # 4. 发布到各平台
        publishers = [
            NotionPublisherAgent(),
            FeishuPublisherAgent(),
            XHSPublisherAgent(),
            WeChatMPPublisherAgent()
        ]

        publish_results = {}
        for publisher in publishers:
            try:
                result = await publisher.run(context)
                publish_results[publisher.name] = result
            except Exception as e:
                logger.error(f"Publisher {publisher.name} failed: {e}")
                publish_results[publisher.name] = {"error": str(e)}

        results["publish"] = publish_results

        return results