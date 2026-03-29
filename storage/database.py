"""
Database models and storage for arxiv daily push system.
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings

Base = declarative_base()


class Paper(Base):
    """Paper model for storing fetched papers."""
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    arxiv_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    authors = Column(Text)  # JSON list of authors
    abstract = Column(Text)
    categories = Column(Text)  # JSON list of categories
    published_date = Column(DateTime)
    updated_date = Column(DateTime)
    pdf_url = Column(String(255))
    abs_url = Column(String(255))

    # Metrics
    citation_count = Column(Integer, default=0)
    influence_score = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)
    community_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)

    # Processing status
    is_processed = Column(Boolean, default=False)
    is_selected = Column(Boolean, default=False)
    processed_at = Column(DateTime)

    # Review status
    review_status = Column(String(20), default="pending")  # pending, approved, rejected
    review_feedback = Column(Text)  # JSON: 审核反馈

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublishRecord(Base):
    """Publish record for tracking platform publishes."""
    __tablename__ = "publish_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, nullable=False, index=True)
    platform = Column(String(50), nullable=False)  # notion, xhs, wechat
    status = Column(String(20), default="pending")  # pending, success, failed
    published_at = Column(DateTime)
    platform_url = Column(String(500))  # URL of published content
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentExecution(Base):
    """Agent execution log for debugging and monitoring."""
    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False)
    execution_type = Column(String(50))  # fetch, select, summary, publish
    status = Column(String(20), default="running")  # running, success, failed
    input_data = Column(Text)  # JSON
    output_data = Column(Text)  # JSON
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)


class MCPServerConfig(Base):
    """Configuration for MCP servers."""
    __tablename__ = "mcp_server_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    server_type = Column(String(50))  # stdio, sse, http
    command = Column(String(255))  # For stdio
    args = Column(Text)  # JSON list of args
    env = Column(Text)  # JSON dict of env vars
    url = Column(String(255))  # For sse/http
    is_enabled = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkillConfig(Base):
    """Configuration for skills."""
    __tablename__ = "skill_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    skill_type = Column(String(50))  # builtin, custom
    description = Column(Text)
    config = Column(Text)  # JSON config
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewSession(Base):
    """Review session for paper approval workflow."""
    __tablename__ = "review_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    papers_data = Column(Text)  # JSON: 待审核论文列表
    review_result = Column(Text)  # JSON: 审核结果
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    expires_at = Column(DateTime)  # 审核链接过期时间


class Database:
    """Database manager for async operations."""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = None
        self.async_session = None

    async def init(self):
        """Initialize database connection and create tables."""
        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    async def get_session(self) -> AsyncSession:
        """Get async session."""
        return self.async_session()

    # Paper operations
    async def save_paper(self, paper_data: dict) -> Paper:
        """Save or update a paper."""
        async with self.async_session() as session:
            async with session.begin():
                from sqlalchemy import select
                stmt = select(Paper).where(Paper.arxiv_id == paper_data["arxiv_id"])
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing paper
                    for key, value in paper_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    paper = existing
                else:
                    # Create new paper
                    paper = Paper(**paper_data)
                    session.add(paper)

                await session.commit()
                return paper

    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        """Get paper by arxiv ID."""
        async with self.async_session() as session:
            result = await session.execute(
                text("SELECT * FROM papers WHERE arxiv_id = :arxiv_id"),
                {"arxiv_id": arxiv_id}
            )
            return result.fetchone()

    async def get_selected_papers(self, limit: int = 5) -> List[Paper]:
        """Get selected papers for publishing."""
        async with self.async_session() as session:
            result = await session.execute(
                text("SELECT * FROM papers WHERE is_selected = TRUE ORDER BY total_score DESC LIMIT :limit"),
                {"limit": limit}
            )
            return result.fetchall()

    async def mark_papers_selected(self, arxiv_ids: List[str]):
        """Mark papers as selected."""
        if not arxiv_ids:
            return
        async with self.async_session() as session:
            async with session.begin():
                # Build the IN clause with proper placeholders
                placeholders = ", ".join([f":id{i}" for i in range(len(arxiv_ids))])
                params = {f"id{i}": aid for i, aid in enumerate(arxiv_ids)}
                await session.execute(
                    text(f"UPDATE papers SET is_selected = TRUE WHERE arxiv_id IN ({placeholders})"),
                    params
                )
                await session.commit()

    # MCP Server operations
    async def save_mcp_server(self, config: dict) -> MCPServerConfig:
        """Save MCP server configuration."""
        async with self.async_session() as session:
            async with session.begin():
                server = MCPServerConfig(**config)
                session.add(server)
                await session.commit()
                return server

    async def get_enabled_mcp_servers(self) -> List[MCPServerConfig]:
        """Get all enabled MCP servers."""
        async with self.async_session() as session:
            result = await session.execute(
                "SELECT * FROM mcp_server_configs WHERE is_enabled = TRUE"
            )
            return result.fetchall()

    # Skill operations
    async def save_skill(self, config: dict) -> SkillConfig:
        """Save skill configuration."""
        async with self.async_session() as session:
            async with session.begin():
                skill = SkillConfig(**config)
                session.add(skill)
                await session.commit()
                return skill

    async def get_enabled_skills(self) -> List[SkillConfig]:
        """Get all enabled skills."""
        async with self.async_session() as session:
            result = await session.execute(
                "SELECT * FROM skill_configs WHERE is_enabled = TRUE"
            )
            return result.fetchall()

    # Publish record operations
    async def create_publish_record(self, record: dict) -> PublishRecord:
        """Create a publish record."""
        async with self.async_session() as session:
            async with session.begin():
                pub_record = PublishRecord(**record)
                session.add(pub_record)
                await session.commit()
                return pub_record

    async def update_publish_record(self, record_id: int, updates: dict):
        """Update a publish record."""
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    "UPDATE publish_records SET {} WHERE id = :id".format(
                        ", ".join(f"{k} = :{k}" for k in updates.keys())
                    ),
                    {"id": record_id, **updates}
                )
                await session.commit()

    # Review session operations
    async def create_review_session(self, session_data: dict) -> ReviewSession:
        """Create a new review session."""
        async with self.async_session() as session:
            async with session.begin():
                review_session = ReviewSession(**session_data)
                session.add(review_session)
                await session.commit()
                return review_session

    async def get_review_session(self, session_id: str) -> Optional[ReviewSession]:
        """Get review session by session_id."""
        async with self.async_session() as session:
            from sqlalchemy import select
            stmt = select(ReviewSession).where(ReviewSession.session_id == session_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_review_session(self, session_id: str, updates: dict):
        """Update a review session."""
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "UPDATE review_sessions SET {} WHERE session_id = :session_id".format(
                            ", ".join(f"{k} = :{k}" for k in updates.keys())
                        )
                    ),
                    {"session_id": session_id, **updates}
                )
                await session.commit()

    async def get_pending_review_session(self) -> Optional[ReviewSession]:
        """Get the most recent pending review session."""
        async with self.async_session() as session:
            from sqlalchemy import select
            stmt = select(ReviewSession).where(
                ReviewSession.status == "pending"
            ).order_by(ReviewSession.created_at.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_paper_review_status(
        self,
        arxiv_id: str,
        review_status: str,
        review_feedback: str = None
    ):
        """Update paper review status."""
        async with self.async_session() as session:
            async with session.begin():
                if review_feedback:
                    await session.execute(
                        text(
                            "UPDATE papers SET review_status = :status, "
                            "review_feedback = :feedback WHERE arxiv_id = :arxiv_id"
                        ),
                        {
                            "status": review_status,
                            "feedback": review_feedback,
                            "arxiv_id": arxiv_id
                        }
                    )
                else:
                    await session.execute(
                        text(
                            "UPDATE papers SET review_status = :status "
                            "WHERE arxiv_id = :arxiv_id"
                        ),
                        {"status": review_status, "arxiv_id": arxiv_id}
                    )
                await session.commit()


# Global database instance
db = Database()