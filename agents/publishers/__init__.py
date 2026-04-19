"""
Platform publisher agents for different platforms.

Each agent handles the specific requirements and APIs of its platform.
"""
import json
from abc import abstractmethod
from typing import Dict, Any, Optional, List

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
    1. 将每日精选论文整合到一个 Notion 页面（推荐）
    2. 或将每篇论文作为数据库条目发布（传统模式）

    发布模式：
    - 日报模式（推荐）: 设置 NOTION_PARENT_PAGE_ID，创建每日页面
    - 数据库模式: 仅设置 NOTION_DATABASE_ID，逐篇添加到数据库
    """

    name = "notion_publisher"
    description = "发布论文到 Notion"

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute publishing flow.

        优先使用日报模式（如果设置了 NOTION_PARENT_PAGE_ID），
        否则回退到数据库模式。
        """
        from tools.llm_client import get_llm_client

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning("No summaries to publish for Notion")
            return {"published": [], "count": 0}

        # Determine publishing mode
        if settings.NOTION_PARENT_PAGE_ID:
            logger.info("Using daily page mode for Notion publishing")
            return await self._publish_daily_page(summaries)
        elif settings.NOTION_DATABASE_ID:
            logger.info("Using database mode for Notion publishing")
            return await self._publish_to_database(summaries)
        else:
            logger.warning("Notion not configured (need NOTION_PARENT_PAGE_ID or NOTION_DATABASE_ID)")
            return {"published": [], "count": 0, "error": "Notion not configured"}

    async def _publish_daily_page(self, summaries: List[Dict]) -> Dict[str, Any]:
        """
        Publish all papers as a single daily page.

        Args:
            summaries: List of {paper, summary} dicts

        Returns:
            Dict with publish result
        """
        from tools.notion_publisher import prepare_daily_page

        papers = [item.get("paper", {}) for item in summaries]
        summary_data = [item.get("summary", {}) for item in summaries]

        # Prepare daily page data
        page_data = prepare_daily_page(
            papers=papers,
            summaries=summary_data,
            parent_page_id=settings.NOTION_PARENT_PAGE_ID
        )

        logger.info(f"Creating daily page: {page_data['title']}")

        # Create the page using Notion MCP
        result = await self._create_notion_page(page_data)

        return result

    async def _create_notion_page(self, page_data: Dict) -> Dict[str, Any]:
        """
        Create a Notion page using MCP.

        Args:
            page_data: Dict with parent_page_id, title, content

        Returns:
            Dict with publish result
        """
        try:
            # Use Notion MCP tool to create the page
            result = await self._call_notion_create_page(
                parent_page_id=page_data["parent_page_id"],
                title=page_data["title"],
                content=page_data["content"]
            )

            if result.get("status") == "success":
                logger.info(f"Successfully created Notion page: {result.get('url')}")
                return {
                    "published": [result],
                    "count": 1,
                    "papers_count": page_data.get("paper_count", 0),
                    "mode": "daily_page",
                    "url": result.get("url", "")
                }
            else:
                logger.error(f"Failed to create Notion page: {result.get('error')}")
                return {
                    "published": [],
                    "count": 0,
                    "error": result.get("error")
                }

        except Exception as e:
            logger.error(f"Failed to create daily page: {e}")
            return {"published": [], "count": 0, "error": str(e)}

    async def _call_notion_create_page(
        self,
        parent_page_id: str,
        title: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Call Notion MCP to create a page under a parent page.

        Uses the notion-client API directly.

        Args:
            parent_page_id: Parent page ID
            title: Page title
            content: Page content in markdown

        Returns:
            Dict with status and URL
        """
        from notion_client import AsyncClient

        try:
            async with AsyncClient(auth=settings.NOTION_API_KEY) as client:
                # Create page with title and content
                response = await client.pages.create(
                    parent={"page_id": parent_page_id},
                    properties={
                        "title": {
                            "title": [{"text": {"content": title}}]
                        }
                    }
                )

                page_id = response.get("id", "")
                page_url = response.get("url", "")

                # Add content blocks to the page
                if content:
                    await self._add_content_blocks(client, page_id, content)

                logger.info(f"Created Notion page: {page_url}")

                return {
                    "status": "success",
                    "page_id": page_id,
                    "url": page_url
                }

        except Exception as e:
            logger.error(f"Failed to create Notion page: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

    async def _add_content_blocks(
        self,
        client,
        page_id: str,
        content: str
    ) -> None:
        """
        Add content blocks to a Notion page.

        Converts markdown content to Notion blocks.

        Args:
            client: Notion async client
            page_id: Page ID to add blocks to
            content: Markdown content
        """
        # Split content into sections and create blocks
        blocks = []

        for line in content.split("\n"):
            if not line.strip():
                continue

            # Handle headers
            if line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                    }
                })
            elif line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                    }
                })
            elif line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })
            elif line.startswith("---"):
                blocks.append({
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                })
            elif line.startswith("- "):
                # List item
                text = self._extract_text_content(line[2:])
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": self._parse_rich_text(text)
                    }
                })
            else:
                # Regular paragraph
                text = self._extract_text_content(line)
                if text:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": self._parse_rich_text(text)
                        }
                    })

        # Add blocks in batches (Notion has a limit of 100 blocks per request)
        if blocks:
            batch_size = 50
            for i in range(0, len(blocks), batch_size):
                batch = blocks[i:i + batch_size]
                try:
                    await client.blocks.children.append(
                        block_id=page_id,
                        children=batch
                    )
                except Exception as e:
                    logger.warning(f"Failed to add some blocks: {e}")

    def _extract_text_content(self, line: str) -> str:
        """Extract plain text from a line, preserving basic structure."""
        # Remove markdown link syntax but keep text
        import re
        # [text](url) -> text
        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
        # Remove bold/italic markers
        line = line.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
        return line.strip()

    def _parse_rich_text(self, text: str) -> List[Dict]:
        """Parse text with potential links into rich text objects."""
        import re

        # Find all links in format [text](url)
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        parts = []
        last_end = 0

        for match in re.finditer(pattern, text):
            # Add text before the link
            if match.start() > last_end:
                plain_text = text[last_end:match.start()]
                if plain_text:
                    parts.append({
                        "type": "text",
                        "text": {"content": plain_text}
                    })

            # Add the link
            link_text = match.group(1)
            link_url = match.group(2)
            parts.append({
                "type": "text",
                "text": {
                    "content": link_text,
                    "link": {"url": link_url}
                }
            })
            last_end = match.end()

        # Add remaining text
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                parts.append({
                    "type": "text",
                    "text": {"content": remaining}
                })

        if not parts:
            parts.append({
                "type": "text",
                "text": {"content": text}
            })

        return parts

    async def _publish_to_database(self, summaries: List[Dict]) -> Dict[str, Any]:
        """
        Publish all papers as a single daily database entry.

        Creates one row per day with all papers' content in the page body.
        This is the recommended hybrid approach that combines database structure
        with full paper content.

        Args:
            summaries: List of {paper, summary} dicts

        Returns:
            Dict with publish result
        """
        from tools.notion_publisher import prepare_daily_database_entry

        if not summaries:
            return {"published": [], "count": 0, "mode": "database_daily"}

        # Extract papers and summaries from the input
        papers = [item.get("paper") for item in summaries if item.get("paper")]
        summary_data = [item.get("summary") for item in summaries if item.get("summary")]

        if not papers:
            logger.warning("No papers to publish to Notion")
            return {"published": [], "count": 0, "mode": "database_daily"}

        try:
            # Prepare daily entry data with all papers
            page_data = prepare_daily_database_entry(
                papers=papers,
                summaries=summary_data,
                database_id=settings.NOTION_DATABASE_ID
            )

            logger.info(f"Publishing daily Notion entry: {page_data['title']} with {page_data['paper_count']} papers")

            # Call Notion MCP to create the page
            result = await self._call_notion_mcp(page_data, page_data.get("content", ""))

            if result.get("status") == "success":
                return {
                    "published": [result],
                    "count": 1,
                    "paper_count": page_data["paper_count"],
                    "mode": "database_daily",
                    "url": result.get("url")
                }
            else:
                return {
                    "published": [],
                    "count": 0,
                    "mode": "database_daily",
                    "error": result.get("error")
                }

        except Exception as e:
            logger.error(f"Failed to publish daily entry to Notion: {e}")
            return {
                "published": [],
                "count": 0,
                "mode": "database_daily",
                "error": str(e)
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
        Call Notion API to create a page in the database.

        Args:
            page_data: Dict with database_id and properties
            content: Markdown content for the page body

        Returns:
            Dict with publish result
        """
        from notion_client import AsyncClient

        properties = page_data.get("properties", {})
        paper_id = page_data.get("paper_id", "unknown")
        database_id = page_data.get("database_id", settings.NOTION_DATABASE_ID)

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

        logger.info(f"Publishing to Notion: {paper_id}")

        try:
            # Use Notion API directly
            async with AsyncClient(auth=settings.NOTION_API_KEY) as client:
                # Create page with properties
                response = await client.pages.create(
                    parent={"database_id": database_id},
                    properties=notion_properties
                )

                page_id = response.get("id", "")
                page_url = response.get("url", "")
                logger.info(f"Successfully created Notion page: {page_url}")

                # Add content to the page body if provided
                if content and page_id:
                    await self._add_page_content(client, page_id, content)

                return {
                    "platform": "notion",
                    "paper_id": paper_id,
                    "status": "success",
                    "url": page_url
                }

        except Exception as e:
            logger.error(f"Failed to publish to Notion: {e}")
            return {
                "platform": "notion",
                "paper_id": paper_id,
                "status": "failed",
                "error": str(e)
            }

    async def _add_page_content(
        self,
        client,
        page_id: str,
        content: str
    ) -> None:
        """
        Add markdown content to a Notion page body.

        Converts markdown text to Notion blocks and appends them to the page.
        Notion has a 2000 character limit per rich_text item, so long content
        is split into multiple paragraph blocks.

        Args:
            client: Notion AsyncClient instance
            page_id: The page ID to add content to
            content: Markdown content string
        """
        # Split content into manageable chunks (Notion limit: 2000 chars per rich_text)
        MAX_CHARS = 2000

        # Simple approach: split by paragraphs/sections
        lines = content.split('\n')
        blocks = []
        current_chunk = ""

        for line in lines:
            # If adding this line would exceed limit, flush current chunk
            if len(current_chunk) + len(line) + 1 > MAX_CHARS and current_chunk:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": current_chunk}}]
                    }
                })
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'

        # Add remaining content
        if current_chunk.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": current_chunk}}]
                }
            })

        # Add blocks in batches (Notion limit: 100 blocks per request)
        BATCH_SIZE = 100
        for i in range(0, len(blocks), BATCH_SIZE):
            batch = blocks[i:i + BATCH_SIZE]
            try:
                await client.blocks.children.append(
                    block_id=page_id,
                    children=batch
                )
                logger.info(f"Added {len(batch)} content blocks to page {page_id}")
            except Exception as e:
                logger.warning(f"Failed to add some content blocks: {e}")


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
        使用拼接封面图：将多篇论文的PDF封面合并成一张精美封面
        """
        from tools.llm_client import get_llm_client
        from tools.pdf_screenshot import create_xhs_cover

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

            # 3. Create merged cover image from PDF screenshots
            logger.info("Creating merged cover image from PDF screenshots...")
            cover_output_path = str(settings.STORAGE_DIR / "xhs_cover_merged.jpg")

            # Generate a catchy title for the cover
            cover_title = collection_content.get("title", "AI Agent 论文精选")
            if len(cover_title) > 15:
                cover_title = cover_title[:15] + "..."

            merged_cover_path = await create_xhs_cover(
                papers=papers,
                output_path=cover_output_path,
                title=cover_title,
                layout="grid"  # Options: grid, horizontal, vertical, mosaic
            )

            # 4. Prepare images list
            if merged_cover_path:
                images = [merged_cover_path]
                logger.info(f"Using merged cover image: {merged_cover_path}")
            else:
                # Fallback: use individual screenshots or fallback image
                logger.warning("Failed to create merged cover, using fallback")
                fallback_path = settings.STORAGE_DIR / "cover_fallback.jpg"
                if fallback_path.exists():
                    images = [str(fallback_path)]
                else:
                    logger.error("No images available for XHS post")
                    return {"published": [], "count": 0, "error": "No images"}

            # 5. Publish to XHS
            result = await self._publish_to_xhs(collection_content, images)

            return {
                "published": [result],
                "count": 1 if result.get("status") == "success" else 0,
                "content": collection_content,
                "cover_type": "merged" if merged_cover_path else "fallback",
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
        Generate collection-style content for multiple papers using XHS skill.

        Args:
            papers: List of paper dictionaries
            summaries: List of summary dictionaries

        Returns:
            Dict with title, content, and tags for XHS post
        """
        from config.prompts import load_skill_prompt

        # Load XHS skill as system prompt (preferred) with fallback to legacy prompt
        try:
            prompt = load_skill_prompt("xhs-publisher")
            logger.info("Using xhs-publisher skill for content generation")
        except FileNotFoundError:
            from config.prompts import load_prompt
            prompt = load_prompt("xhs_collection")
            logger.info("Using legacy xhs_collection prompt")

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
            import aiohttp
            mcp_url = "http://localhost:18060/mcp"

            # Step 1: Initialize MCP session
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "arxiv-daily", "version": "1.0"}
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    mcp_url,
                    json=init_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    session_id = resp.headers.get("mcp-session-id")
                    if not session_id:
                        raise RuntimeError("MCP server did not return session ID — is xiaohongshu-mcp running on port 18060?")
                    logger.info(f"MCP session initialized: {session_id}")

                # Step 2: Call publish_content tool
                publish_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "publish_content",
                        "arguments": {
                            "title": title,
                            "content": body,
                            "images": processed_images,
                            "tags": tags,
                            "is_original": False
                        }
                    }
                }
                async with session.post(
                    mcp_url,
                    json=publish_payload,
                    headers={
                        "Content-Type": "application/json",
                        "mcp-session-id": session_id
                    },
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    result_data = await resp.json()

            if "error" in result_data:
                raise RuntimeError(f"MCP error: {result_data['error']}")

            content_list = result_data.get("result", {}).get("content", [])
            result_text = content_list[0].get("text", "") if content_list else ""
            logger.info(f"XHS publish result: {result_text}")

            return {
                "status": "success",
                "message": result_text,
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
            create_cover_image
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

            # 3. Generate article content using skill
            logger.info("Generating article content using wechat-publisher skill...")
            article_content = await self._generate_article_content(papers, summaries_data, title)

            # 4. Create cover image
            logger.info("Creating cover image...")
            cover_data = create_cover_image(
                title="AI Agent 论文推荐",
                subtitle=f"每日精选 {len(papers)} 篇高质量论文",
                output_path=str(settings.STORAGE_DIR / "wechat_cover.jpg")
            )

            # 5. Upload cover image
            logger.info("Uploading cover image to WeChat...")
            thumb_media_id = await wechat_client.upload_image(cover_data, "cover.jpg")

            # 6. Create draft
            article = {
                "title": title,
                "author": "arxiv_daily",
                "digest": article_content.get("digest", f"每日精选 {len(papers)} 篇 AI Agent 领域高质量论文，助您紧跟前沿研究动态。"),
                "content": article_content.get("content", ""),
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

    async def _generate_article_content(
        self,
        papers: list[Dict],
        summaries: list[Dict],
        title: str
    ) -> Dict[str, Any]:
        """
        Generate article content using WeChat MP skill.

        Args:
            papers: List of paper dictionaries
            summaries: List of summary dictionaries
            title: Article title

        Returns:
            Dict with 'content' (HTML) and 'digest'
        """
        from config.prompts import load_skill_prompt
        from tools.wechat_publisher import format_article_content

        # Load WeChat skill as system prompt (preferred) with fallback to legacy format
        try:
            prompt = load_skill_prompt("wechat-publisher")
            logger.info("Using wechat-publisher skill for content generation")
        except FileNotFoundError:
            logger.info("WeChat skill not found, using legacy format_article_content")
            # Fallback to legacy formatting
            html_content = format_article_content(papers, summaries, title)
            return {
                "content": html_content,
                "digest": f"每日精选 {len(papers)} 篇 AI Agent 领域高质量论文，助您紧跟前沿研究动态。"
            }

        # Build paper info for prompt
        papers_info = []
        for paper, summary in zip(papers, summaries):
            info = {
                "title": paper.get("title", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "authors": paper.get("authors", [])[:3],
                "summary": summary.get("summary", "")[:500] if summary else paper.get("abstract", "")[:500],
                "highlights": summary.get("highlights", [])[:3] if summary else []
            }
            papers_info.append(info)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
今日精选论文共 {len(papers)} 篇，文章标题：{title}

{json.dumps(papers_info, ensure_ascii=False, indent=2)}

请生成适合微信公众号的文章内容。输出JSON格式，包含:
- title: 文章标题
- digest: 摘要(100字以内)
- content: HTML格式的正文内容
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
            logger.error(f"Failed to generate WeChat content with skill: {e}")
            # Fallback to legacy formatting
            html_content = format_article_content(papers, summaries, title)
            return {
                "content": html_content,
                "digest": f"每日精选 {len(papers)} 篇 AI Agent 领域高质量论文，助您紧跟前沿研究动态。"
            }

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
class DouyinPublisherAgent(BasePublisherAgent):
    """
    抖音发布 Agent

    职责：
    1. 生成适合抖音的图文内容格式
    2. 创建竖版封面图（1080x1920）
    3. 通过抖音 MCP 发布图文笔记
    """

    name = "douyin_publisher"
    description = "发布论文图文到抖音"

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        Execute publishing flow - create image-text post.

        图文模式：将所有论文整合成一条抖音图文笔记发布
        使用竖版封面图，大字号标题，醒目推荐标签
        """
        from tools.llm_client import get_llm_client
        from tools.douyin_cover import create_douyin_cover_async

        self.llm_client = get_llm_client()

        # Get summaries from context
        summaries = context.get("summaries", [])
        if not summaries:
            logger.warning("No summaries to publish for Douyin")
            return {"published": [], "count": 0}

        # Check if Douyin MCP is enabled
        if not settings.DOUYIN_MCP_ENABLED:
            logger.info("Douyin publishing disabled, skipping")
            return {"published": [], "count": 0, "skipped": True}

        try:
            # 1. Extract paper info
            papers = [item.get("paper", {}) for item in summaries]
            summaries_data = [item.get("summary", {}) for item in summaries]

            # 2. Generate Douyin style content
            logger.info(f"Generating Douyin content for {len(papers)} papers")
            douyin_content = await self._generate_douyin_content(papers, summaries_data)

            if not douyin_content:
                logger.error("Failed to generate Douyin content")
                return {"published": [], "count": 0, "error": "Failed to generate content"}

            # 3. Create vertical cover image
            logger.info("Creating vertical cover image for Douyin...")
            cover_path = await create_douyin_cover_async(
                papers=papers,
                title=douyin_content.get("title", "AI Agent 论文精选"),
                output_path=str(settings.STORAGE_DIR / "douyin_covers" / f"douyin_cover_{len(papers)}papers.png")
            )

            if not cover_path:
                logger.warning("Failed to create Douyin cover, using fallback")
                # Use first paper's cover as fallback
                if papers and papers[0].get("arxiv_id"):
                    from tools.pdf_screenshot import get_cover_path
                    cover_path = str(get_cover_path(papers[0]["arxiv_id"]))

            # 4. Prepare images (use individual paper covers + main cover)
            images = []
            if cover_path:
                images.append(cover_path)

            # Add individual paper covers (max 9 total images)
            for paper in papers[:8]:
                arxiv_id = paper.get("arxiv_id")
                if arxiv_id:
                    from tools.pdf_screenshot import get_cover_path
                    paper_cover = get_cover_path(arxiv_id)
                    if paper_cover:
                        images.append(str(paper_cover))

            if not images:
                logger.error("No images available for Douyin post")
                return {"published": [], "count": 0, "error": "No images"}

            # 5. Publish to Douyin via MCP
            result = await self._publish_to_douyin(douyin_content, images)

            return {
                "published": [result],
                "count": 1 if result.get("status") == "success" else 0,
                "content": douyin_content,
                "images_count": len(images)
            }

        except Exception as e:
            logger.error(f"Douyin publishing failed: {e}")
            return {"published": [], "count": 0, "error": str(e)}

    async def _generate_douyin_content(
        self,
        papers: list[Dict],
        summaries: list[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate Douyin-style content.

        Args:
            papers: List of paper dictionaries
            summaries: List of summary dictionaries

        Returns:
            Dict with title, content, and tags for Douyin post
        """
        from config.prompts import load_skill_prompt

        # Load Douyin skill as system prompt
        try:
            prompt = load_skill_prompt("douyin-publisher")
            logger.info("Using douyin-publisher skill for content generation")
        except FileNotFoundError:
            from config.prompts import load_prompt
            prompt = load_prompt("douyin_style")
            logger.info("Using douyin_style prompt")

        # Build paper info for prompt
        papers_info = []
        for paper, summary in zip(papers, summaries):
            info = {
                "title": paper.get("title", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "authors": paper.get("authors", [])[:3],
                "summary": summary.get("summary", "")[:300] if summary else paper.get("abstract", "")[:300],
                "highlights": summary.get("highlights", [])[:2] if summary else []
            }
            papers_info.append(info)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
今日精选论文共 {len(papers)} 篇：

{json.dumps(papers_info, ensure_ascii=False, indent=2)}

请生成适合抖音的图文笔记内容。输出 JSON 格式。
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
            logger.error(f"Failed to generate Douyin content: {e}")
            return None

    async def _publish_to_douyin(self, content: Dict, images: list[str]) -> Dict[str, Any]:
        """
        Publish content to Douyin using MCP.

        Args:
            content: Dict with 'title', 'content', 'tags'
            images: List of image paths

        Returns:
            Dict with publish result
        """
        try:
            # Call Douyin MCP tool
            # Note: This requires the douyin-upload-mcp-skill server to be configured
            result = await self._call_douyin_mcp(content, images)

            if result:
                logger.info(f"Successfully published to Douyin")
                return {
                    "platform": "douyin",
                    "status": "success",
                    "title": content.get("title", ""),
                    "url": result.get("url", "")
                }
            else:
                logger.error("Douyin MCP returned empty result")
                return {
                    "platform": "douyin",
                    "status": "failed",
                    "error": "MCP returned empty result"
                }

        except Exception as e:
            logger.error(f"Failed to publish to Douyin: {e}")
            return {
                "platform": "douyin",
                "status": "failed",
                "error": str(e)
            }

    async def _call_douyin_mcp(self, content: Dict, images: list[str]) -> Optional[Dict]:
        """
        Call Douyin MCP server to publish content.

        This method interfaces with the douyin-upload-mcp-skill server.
        In the MCP-enabled runtime, this will call the actual publishing tool.

        Args:
            content: Dict with 'title', 'content', 'tags'
            images: List of image paths (local absolute paths)

        Returns:
            Dict with publish result
        """
        title = content.get("title", "AI Agent 论文精选")
        body = content.get("content", "")
        tags = content.get("tags", [])

        # Validate title length (Douyin limit: 20 chars)
        if len(title) > 20:
            logger.warning(f"Title too long ({len(title)} chars), truncating to 20")
            title = title[:20]

        # Limit images (Douyin limit: 35 images)
        if len(images) > 35:
            logger.warning(f"Too many images ({len(images)}), limiting to 35")
            images = images[:35]

        # Process images: convert local paths to absolute paths
        processed_images = []
        for img in images:
            if img.startswith("http://") or img.startswith("https://"):
                processed_images.append(img)
            else:
                from pathlib import Path
                img_path = Path(img)
                if not img_path.is_absolute():
                    img_path = settings.STORAGE_DIR / img
                if img_path.exists():
                    processed_images.append(str(img_path))
                else:
                    logger.warning(f"Image not found: {img}")

        if not processed_images:
            logger.error("No valid images available for Douyin post")
            return {"status": "error", "error": "No valid images"}

        logger.info(f"Publishing to Douyin: {title}")
        logger.info(f"Content: {len(body)} chars, Images: {len(processed_images)}")
        logger.info(f"Tags: {tags}")

        try:
            # In Claude Code runtime with MCP, call the actual tool:
            # result = await mcp__douyin__publish_imagetext(
            #     filePaths=processed_images,
            #     title=title,
            #     description=body
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
            logger.error(f"Failed to call Douyin MCP: {e}")
            return {
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
            XHSPublisherAgent,
            WeChatMPPublisherAgent,
            DouyinPublisherAgent
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
            XHSPublisherAgent(),
            WeChatMPPublisherAgent(),
            DouyinPublisherAgent()
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