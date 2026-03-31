"""
Notion数据库操作封装

将论文元数据和发布记录存储到Notion云端数据库。
"""
import asyncio
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from loguru import logger
from notion_client import AsyncClient

from config.settings import settings


class NotionDatabase:
    """
    Notion云端数据库管理器

    提供论文和发布记录的CRUD操作，支持API限速处理。
    """

    def __init__(
        self,
        api_key: str = None,
        papers_database_id: str = None,
        records_database_id: str = None
    ):
        self.api_key = api_key or settings.NOTION_API_KEY
        self.papers_database_id = papers_database_id or settings.NOTION_PAPERS_DATABASE_ID
        self.records_database_id = records_database_id or settings.NOTION_RECORDS_DATABASE_ID
        self.client: Optional[AsyncClient] = None
        self._initialized = False

    async def init(self):
        """初始化Notion客户端"""
        if not self.api_key:
            logger.warning("NOTION_API_KEY not configured, Notion storage disabled")
            return False

        self.client = AsyncClient(auth=self.api_key)
        self._initialized = True
        logger.info("Notion database initialized")
        return True

    async def close(self):
        """关闭客户端连接"""
        if self.client:
            await self.client.aclose()
            self._initialized = False

    def is_enabled(self) -> bool:
        """检查Notion存储是否启用"""
        return self._initialized and bool(self.papers_database_id)

    # =========================================================================
    # 论文操作
    # =========================================================================

    async def save_paper(self, paper_data: dict) -> Optional[str]:
        """
        保存论文到Notion数据库

        Args:
            paper_data: 论文数据字典

        Returns:
            创建的页面ID，失败返回None
        """
        if not self.is_enabled():
            logger.warning("Notion papers database not configured")
            return None

        try:
            # 构建Notion属性
            properties = self._build_paper_properties(paper_data)

            # 创建页面
            response = await self.client.pages.create(
                parent={"database_id": self.papers_database_id},
                properties=properties
            )

            page_id = response.get("id", "")
            logger.info(f"Saved paper to Notion: {paper_data.get('arxiv_id')} -> {page_id}")
            return page_id

        except Exception as e:
            logger.error(f"Failed to save paper to Notion: {e}")
            return None

    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        根据arxiv_id查询论文

        Args:
            arxiv_id: arxiv论文ID

        Returns:
            论文数据字典，未找到返回None
        """
        if not self.is_enabled():
            return None

        try:
            # 使用filter查询
            response = await self.client.databases.query(
                database_id=self.papers_database_id,
                filter={
                    "property": "arxiv_id",
                    "text": {"equals": arxiv_id}
                }
            )

            results = response.get("results", [])
            if results:
                return self._parse_paper_page(results[0])
            return None

        except Exception as e:
            logger.error(f"Failed to query paper from Notion: {e}")
            return None

    async def get_selected_papers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取选中状态的论文

        Args:
            limit: 最大返回数量

        Returns:
            论文列表
        """
        if not self.is_enabled():
            return []

        try:
            response = await self.client.databases.query(
                database_id=self.papers_database_id,
                filter={
                    "property": "选择状态",
                    "select": {"equals": "selected"}
                },
                sorts=[{
                    "property": "总评分",
                    "direction": "descending"
                }],
                page_size=limit
            )

            papers = []
            for page in response.get("results", []):
                papers.append(self._parse_paper_page(page))

            return papers

        except Exception as e:
            logger.error(f"Failed to get selected papers from Notion: {e}")
            return []

    async def get_unprocessed_papers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取未处理的论文

        Args:
            limit: 最大返回数量

        Returns:
            论文列表
        """
        if not self.is_enabled():
            return []

        try:
            response = await self.client.databases.query(
                database_id=self.papers_database_id,
                filter={
                    "property": "处理状态",
                    "checkbox": {"equals": False}
                },
                sorts=[{
                    "property": "创建时间",
                    "direction": "descending"
                }],
                page_size=limit
            )

            papers = []
            for page in response.get("results", []):
                papers.append(self._parse_paper_page(page))

            return papers

        except Exception as e:
            logger.error(f"Failed to get unprocessed papers from Notion: {e}")
            return []

    async def mark_papers_selected(self, arxiv_ids: List[str]) -> int:
        """
        标记论文为选中状态

        Args:
            arxiv_ids: arxiv ID列表

        Returns:
            成功更新的数量
        """
        if not self.is_enabled() or not arxiv_ids:
            return 0

        updated = 0
        for arxiv_id in arxiv_ids:
            try:
                # 先查询获取page_id
                paper = await self.get_paper_by_arxiv_id(arxiv_id)
                if paper and paper.get("notion_page_id"):
                    await self.client.pages.update(
                        page_id=paper["notion_page_id"],
                        properties={
                            "选择状态": {"select": {"name": "selected"}},
                            "处理状态": {"checkbox": True}
                        }
                    )
                    updated += 1

                # 避免触发API限速
                await asyncio.sleep(0.4)

            except Exception as e:
                logger.warning(f"Failed to mark paper {arxiv_id} as selected: {e}")

        logger.info(f"Marked {updated} papers as selected in Notion")
        return updated

    async def update_paper(self, arxiv_id: str, updates: dict) -> bool:
        """
        更新论文信息

        Args:
            arxiv_id: arxiv论文ID
            updates: 要更新的字段

        Returns:
            是否成功
        """
        if not self.is_enabled():
            return False

        try:
            paper = await self.get_paper_by_arxiv_id(arxiv_id)
            if not paper or not paper.get("notion_page_id"):
                return False

            properties = {}
            for key, value in updates.items():
                if key in ["total_score", "citation_count", "influence_score", "quality_score"]:
                    properties[self._map_property_name(key)] = {"number": value}
                elif key in ["is_selected", "is_processed"]:
                    prop_name = "选择状态" if key == "is_selected" else "处理状态"
                    if key == "is_selected":
                        properties[prop_name] = {"select": {"name": "selected" if value else "pending"}}
                    else:
                        properties[prop_name] = {"checkbox": value}

            if properties:
                await self.client.pages.update(
                    page_id=paper["notion_page_id"],
                    properties=properties
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to update paper in Notion: {e}")
            return False

    # =========================================================================
    # 发布记录操作
    # =========================================================================

    async def create_publish_record(self, record: dict) -> Optional[str]:
        """
        创建发布记录

        Args:
            record: 发布记录数据

        Returns:
            创建的页面ID
        """
        if not self._initialized or not self.records_database_id:
            logger.warning("Notion records database not configured")
            return None

        try:
            properties = {
                "标题": {
                    "title": [{"text": {"content": record.get("title", "未命名记录")}}]
                },
                "平台": {"select": {"name": record.get("platform", "unknown")}},
                "状态": {"select": {"name": record.get("status", "pending")}},
            }

            if record.get("platform_url"):
                properties["平台链接"] = {"url": record.get("platform_url")}

            if record.get("error_message"):
                properties["错误信息"] = {
                    "rich_text": [{"text": {"content": record.get("error_message", "")[:2000]}}]
                }

            if record.get("published_at"):
                properties["发布时间"] = {
                    "date": {"start": record["published_at"]}
                }

            response = await self.client.pages.create(
                parent={"database_id": self.records_database_id},
                properties=properties
            )

            page_id = response.get("id", "")
            logger.info(f"Created publish record in Notion: {page_id}")
            return page_id

        except Exception as e:
            logger.error(f"Failed to create publish record in Notion: {e}")
            return None

    async def update_publish_record(self, record_id: str, updates: dict) -> bool:
        """
        更新发布记录

        Args:
            record_id: 记录页面ID
            updates: 要更新的字段

        Returns:
            是否成功
        """
        if not self._initialized or not self.records_database_id:
            return False

        try:
            properties = {}

            if "status" in updates:
                properties["状态"] = {"select": {"name": updates["status"]}}

            if "platform_url" in updates:
                properties["平台链接"] = {"url": updates["platform_url"]}

            if "error_message" in updates:
                properties["错误信息"] = {
                    "rich_text": [{"text": {"content": updates["error_message"][:2000]}}]
                }

            if "published_at" in updates:
                properties["发布时间"] = {
                    "date": {"start": updates["published_at"]}
                }

            if properties:
                await self.client.pages.update(
                    page_id=record_id,
                    properties=properties
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to update publish record in Notion: {e}")
            return False

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _build_paper_properties(self, paper_data: dict) -> dict:
        """构建Notion页面属性（使用英文属性名）"""
        properties = {}

        # 标题 (使用默认的 Name 属性)
        title = paper_data.get("title", "")[:100]
        properties["Name"] = {
            "title": [{"text": {"content": title}}]
        }

        # arxiv_id
        if paper_data.get("arxiv_id"):
            properties["arxiv_id"] = {
                "rich_text": [{"text": {"content": paper_data["arxiv_id"]}}]
            }

        # 作者 (multi-select)
        authors = paper_data.get("authors", [])
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except:
                authors = [authors] if authors else []

        if authors:
            properties["作者"] = {
                "multi_select": [{"name": a[:50]} for a in authors[:10]]
            }

        # 摘要
        if paper_data.get("abstract"):
            abstract = paper_data["abstract"][:2000]
            properties["摘要"] = {
                "rich_text": [{"text": {"content": abstract}}]
            }

        # 发布日期
        if paper_data.get("published_date"):
            date_str = paper_data["published_date"]
            if isinstance(date_str, datetime):
                date_str = date_str.strftime("%Y-%m-%d")
            properties["发布日期"] = {
                "date": {"start": date_str[:10]}
            }

        # URL字段
        if paper_data.get("abs_url"):
            properties["arxiv链接"] = {"url": paper_data["abs_url"]}

        if paper_data.get("pdf_url"):
            properties["PDF链接"] = {"url": paper_data["pdf_url"]}

        # 数值字段
        if paper_data.get("citation_count") is not None:
            properties["引用数"] = {"number": int(paper_data["citation_count"])}

        if paper_data.get("influence_score") is not None:
            properties["影响力分数"] = {"number": round(float(paper_data["influence_score"]), 3)}

        if paper_data.get("quality_score") is not None:
            properties["质量分数"] = {"number": round(float(paper_data["quality_score"]), 3)}

        if paper_data.get("total_score") is not None:
            properties["总评分"] = {"number": round(float(paper_data["total_score"]), 3)}

        # 选择状态
        is_selected = paper_data.get("is_selected", False)
        properties["选择状态"] = {
            "select": {"name": "selected" if is_selected else "pending"}
        }

        # 处理状态
        properties["处理状态"] = {
            "checkbox": paper_data.get("is_processed", False)
        }

        return properties

    def _parse_paper_page(self, page: dict) -> dict:
        """解析Notion页面为论文数据字典"""
        props = page.get("properties", {})

        paper = {
            "notion_page_id": page.get("id", ""),
        }

        # 标题（使用默认的 Name 属性）
        title_prop = props.get("Name", {})
        if title_prop.get("title"):
            paper["title"] = title_prop["title"][0].get("text", {}).get("content", "")

        # arxiv_id
        arxiv_prop = props.get("arxiv_id", {})
        if arxiv_prop.get("rich_text"):
            paper["arxiv_id"] = arxiv_prop["rich_text"][0].get("text", {}).get("content", "")

        # 作者
        authors_prop = props.get("作者", {})
        if authors_prop.get("multi_select"):
            paper["authors"] = json.dumps([a.get("name", "") for a in authors_prop["multi_select"]])

        # 摘要
        abstract_prop = props.get("摘要", {})
        if abstract_prop.get("rich_text"):
            paper["abstract"] = abstract_prop["rich_text"][0].get("text", {}).get("content", "")

        # 数值字段
        for field in ["引用数", "影响力分数", "质量分数", "总评分"]:
            prop = props.get(field, {})
            if prop.get("number") is not None:
                key = {
                    "引用数": "citation_count",
                    "影响力分数": "influence_score",
                    "质量分数": "quality_score",
                    "总评分": "total_score"
                }[field]
                paper[key] = prop["number"]

        # 日期
        date_prop = props.get("发布日期", {})
        if date_prop.get("date"):
            paper["published_date"] = date_prop["date"].get("start", "")

        # URL
        for field in ["arxiv链接", "PDF链接"]:
            prop = props.get(field, {})
            if prop.get("url"):
                key = "abs_url" if field == "arxiv链接" else "pdf_url"
                paper[key] = prop["url"]

        # 状态
        status_prop = props.get("选择状态", {})
        if status_prop.get("select"):
            paper["is_selected"] = status_prop["select"].get("name") == "selected"

        processed_prop = props.get("处理状态", {})
        if processed_prop.get("checkbox") is not None:
            paper["is_processed"] = processed_prop["checkbox"]

        return paper

    def _map_property_name(self, internal_name: str) -> str:
        """映射内部字段名到Notion属性名"""
        mapping = {
            "total_score": "总评分",
            "citation_count": "引用数",
            "influence_score": "影响力分数",
            "quality_score": "质量分数",
            "community_score": "社区热度",
        }
        return mapping.get(internal_name, internal_name)


# 全局实例
notion_db = NotionDatabase()