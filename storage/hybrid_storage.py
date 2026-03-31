"""
混合存储层 - Notion优先 + 本地缓存

实现Notion云端存储与本地SQLite的混合策略：
- 日常操作优先使用Notion
- 本地SQLite作为离线缓存和备份
- 网络故障时自动回退到本地
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from loguru import logger

from config.settings import settings
from storage.database import Database, db as default_local_db
from storage.notion_db import NotionDatabase, notion_db as default_remote_db


class HybridStorage:
    """
    混合存储管理器

    策略：
    - 写入：同时写入Notion和本地（双写）
    - 读取：优先Notion，失败时回退本地
    - 离线：完全使用本地存储
    """

    def __init__(
        self,
        use_notion: bool = None,
        notion_db: NotionDatabase = None,
        local_db: Database = None
    ):
        self.use_notion = use_notion if use_notion is not None else settings.USE_NOTION_STORAGE
        self.remote = notion_db or default_remote_db
        self.local = local_db or default_local_db
        self._initialized = False

    async def init(self):
        """初始化存储层"""
        # 始终初始化本地数据库
        await self.local.init()

        # 尝试初始化Notion
        if self.use_notion:
            try:
                success = await self.remote.init()
                if success and self.remote.is_enabled():
                    logger.info("Hybrid storage: Notion enabled as primary storage")
                else:
                    logger.warning("Hybrid storage: Notion not available, using local only")
                    self.use_notion = False
            except Exception as e:
                logger.warning(f"Hybrid storage: Failed to init Notion, using local only: {e}")
                self.use_notion = False
        else:
            logger.info("Hybrid storage: Using local SQLite only")

        self._initialized = True

    async def close(self):
        """关闭存储连接"""
        await self.local.close()
        if self.use_notion:
            await self.remote.close()
        self._initialized = False

    def is_notion_enabled(self) -> bool:
        """检查Notion存储是否启用"""
        return self.use_notion and self.remote.is_enabled()

    # =========================================================================
    # 论文操作
    # =========================================================================

    async def save_paper(self, paper_data: dict) -> Dict[str, Any]:
        """
        保存论文（双写策略）

        Args:
            paper_data: 论文数据

        Returns:
            包含存储结果的字典
        """
        result = {
            "local": False,
            "remote": False,
            "notion_page_id": None
        }

        # 1. 保存到本地（始终执行）
        try:
            await self.local.save_paper(paper_data)
            result["local"] = True
        except Exception as e:
            logger.error(f"Failed to save paper locally: {e}")

        # 2. 保存到Notion（如果启用）
        if self.is_notion_enabled():
            try:
                page_id = await self.remote.save_paper(paper_data)
                if page_id:
                    result["remote"] = True
                    result["notion_page_id"] = page_id
                    # 更新本地记录，添加notion_page_id
                    paper_data["notion_page_id"] = page_id
            except Exception as e:
                logger.warning(f"Failed to save paper to Notion (will use local): {e}")

        return result

    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        获取论文（优先Notion，回退本地）

        Args:
            arxiv_id: arxiv论文ID

        Returns:
            论文数据字典
        """
        # 优先从Notion获取
        if self.is_notion_enabled():
            try:
                paper = await self.remote.get_paper_by_arxiv_id(arxiv_id)
                if paper:
                    return paper
            except Exception as e:
                logger.warning(f"Failed to get paper from Notion, falling back to local: {e}")

        # 回退到本地
        try:
            paper = await self.local.get_paper_by_arxiv_id(arxiv_id)
            if paper:
                # 转换SQLAlchemy对象为字典
                return self._paper_to_dict(paper)
        except Exception as e:
            logger.error(f"Failed to get paper locally: {e}")

        return None

    async def get_selected_papers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取选中的论文

        Args:
            limit: 最大返回数量

        Returns:
            论文列表
        """
        # 优先从Notion获取
        if self.is_notion_enabled():
            try:
                papers = await self.remote.get_selected_papers(limit)
                if papers:
                    return papers
            except Exception as e:
                logger.warning(f"Failed to get selected papers from Notion, falling back to local: {e}")

        # 回退到本地
        try:
            papers = await self.local.get_selected_papers(limit)
            return [self._paper_to_dict(p) for p in papers]
        except Exception as e:
            logger.error(f"Failed to get selected papers locally: {e}")
            return []

    async def get_unprocessed_papers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取未处理的论文

        Args:
            limit: 最大返回数量

        Returns:
            论文列表
        """
        # 优先从Notion获取
        if self.is_notion_enabled():
            try:
                papers = await self.remote.get_unprocessed_papers(limit)
                if papers:
                    return papers
            except Exception as e:
                logger.warning(f"Failed to get unprocessed papers from Notion, falling back to local: {e}")

        # 回退到本地
        from storage.database import Paper
        from sqlalchemy import select

        papers = []
        async with self.local.async_session() as session:
            stmt = select(Paper).where(
                Paper.is_processed == False
            ).order_by(Paper.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            for paper in rows:
                papers.append(self._paper_to_dict(paper))

        return papers

    async def mark_papers_selected(self, arxiv_ids: List[str]) -> int:
        """
        标记论文为选中状态

        Args:
            arxiv_ids: arxiv ID列表

        Returns:
            成功更新的数量
        """
        local_count = 0
        remote_count = 0

        # 1. 更新本地
        try:
            await self.local.mark_papers_selected(arxiv_ids)
            local_count = len(arxiv_ids)
        except Exception as e:
            logger.error(f"Failed to mark papers selected locally: {e}")

        # 2. 更新Notion
        if self.is_notion_enabled():
            try:
                remote_count = await self.remote.mark_papers_selected(arxiv_ids)
            except Exception as e:
                logger.warning(f"Failed to mark papers selected in Notion: {e}")

        return max(local_count, remote_count)

    async def update_paper(self, arxiv_id: str, updates: dict) -> bool:
        """
        更新论文信息

        Args:
            arxiv_id: arxiv论文ID
            updates: 要更新的字段

        Returns:
            是否成功
        """
        local_success = False
        remote_success = False

        # 1. 更新本地
        try:
            # 本地更新逻辑（简化版，实际可能需要更多字段映射）
            async with self.local.async_session() as session:
                from sqlalchemy import text
                set_clauses = []
                params = {"arxiv_id": arxiv_id}

                for key, value in updates.items():
                    if key in ["total_score", "citation_count", "influence_score", "quality_score",
                               "community_score", "is_selected", "is_processed"]:
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value

                if set_clauses:
                    query = f"UPDATE papers SET {', '.join(set_clauses)} WHERE arxiv_id = :arxiv_id"
                    await session.execute(text(query), params)
                    await session.commit()
                    local_success = True
        except Exception as e:
            logger.error(f"Failed to update paper locally: {e}")

        # 2. 更新Notion
        if self.is_notion_enabled():
            try:
                remote_success = await self.remote.update_paper(arxiv_id, updates)
            except Exception as e:
                logger.warning(f"Failed to update paper in Notion: {e}")

        return local_success or remote_success

    # =========================================================================
    # 发布记录操作
    # =========================================================================

    async def create_publish_record(self, record: dict) -> Dict[str, Any]:
        """
        创建发布记录

        Args:
            record: 发布记录数据

        Returns:
            包含存储结果的字典
        """
        result = {
            "local": False,
            "remote": False,
            "local_id": None,
            "notion_page_id": None
        }

        # 1. 保存到本地
        try:
            local_record = await self.local.create_publish_record(record)
            result["local"] = True
            result["local_id"] = local_record.id if hasattr(local_record, 'id') else None
        except Exception as e:
            logger.error(f"Failed to create publish record locally: {e}")

        # 2. 保存到Notion
        if self.is_notion_enabled() and self.remote.records_database_id:
            try:
                page_id = await self.remote.create_publish_record(record)
                if page_id:
                    result["remote"] = True
                    result["notion_page_id"] = page_id
            except Exception as e:
                logger.warning(f"Failed to create publish record in Notion: {e}")

        return result

    async def update_publish_record(self, record_id: int, updates: dict) -> bool:
        """
        更新发布记录

        Args:
            record_id: 记录ID
            updates: 要更新的字段

        Returns:
            是否成功
        """
        # 本地更新
        try:
            await self.local.update_publish_record(record_id, updates)
            return True
        except Exception as e:
            logger.error(f"Failed to update publish record: {e}")
            return False

    # =========================================================================
    # 同步操作
    # =========================================================================

    async def sync_local_to_notion(self, batch_size: int = 10) -> Dict[str, int]:
        """
        将本地数据同步到Notion

        Args:
            batch_size: 每批处理数量

        Returns:
            同步统计
        """
        if not self.is_notion_enabled():
            return {"synced": 0, "failed": 0, "skipped": 1}

        stats = {"synced": 0, "failed": 0, "skipped": 0}

        # 获取本地所有论文
        papers = await self.get_unprocessed_papers(limit=1000)

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]

            for paper in batch:
                # 检查是否已存在于Notion
                existing = await self.remote.get_paper_by_arxiv_id(paper.get("arxiv_id", ""))
                if existing:
                    stats["skipped"] += 1
                    continue

                # 同步到Notion
                try:
                    page_id = await self.remote.save_paper(paper)
                    if page_id:
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logger.warning(f"Failed to sync paper {paper.get('arxiv_id')}: {e}")
                    stats["failed"] += 1

                # 避免API限速
                import asyncio
                await asyncio.sleep(0.5)

            logger.info(f"Synced batch {i // batch_size + 1}: {stats}")

        return stats

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _paper_to_dict(self, paper) -> dict:
        """将SQLAlchemy Paper对象或Row对象转换为字典"""
        # 如果已经是字典，直接返回
        if isinstance(paper, dict):
            return paper

        # 如果是SQLAlchemy Row对象（有 _fields 属性）
        if hasattr(paper, '_fields'):
            return {field: getattr(paper, field) for field in paper._fields}

        # 如果是SQLAlchemy Model对象（有 arxiv_id 等属性）
        if hasattr(paper, 'arxiv_id'):
            return {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "categories": paper.categories,
                "published_date": paper.published_date,
                "pdf_url": paper.pdf_url,
                "abs_url": paper.abs_url,
                "citation_count": paper.citation_count,
                "influence_score": paper.influence_score,
                "quality_score": paper.quality_score,
                "community_score": paper.community_score,
                "total_score": paper.total_score,
                "is_processed": paper.is_processed,
                "is_selected": paper.is_selected,
                "created_at": paper.created_at,
                "updated_at": paper.updated_at,
            }

        # 尝试转换为字典（最后的手段）
        try:
            return dict(paper)
        except Exception:
            logger.warning(f"Cannot convert paper to dict: {type(paper)}")
            return {}


# 全局实例
storage = HybridStorage()