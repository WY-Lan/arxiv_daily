"""
FastAPI web application for paper review system.

Provides:
- Review page UI for reviewing papers
- API endpoints for submitting review results
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from storage.database import db, ReviewSession


# Pydantic models for API
class PaperReviewResult(BaseModel):
    """Review result for a single paper."""
    arxiv_id: str
    action: str  # approve, reject, edit
    feedback: Optional[str] = None
    edited_summary: Optional[str] = None


class ReviewSubmitRequest(BaseModel):
    """Request body for submitting review results."""
    results: List[PaperReviewResult]


class ReviewStatusResponse(BaseModel):
    """Response for review status check."""
    session_id: str
    status: str
    papers_count: int
    reviewed_at: Optional[str] = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="论文审核系统",
        description="Web interface for reviewing papers before publishing",
        version="1.0.0"
    )

    # Setup templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.on_event("startup")
    async def startup_event():
        """Initialize database on startup."""
        await db.init()
        logger.info("Database initialized for review web app")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Close database on shutdown."""
        await db.close()
        logger.info("Database closed for review web app")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Index page."""
        return "<h1>论文审核系统</h1><p>请使用审核链接访问审核页面。</p>"

    @app.get("/review/{session_id}", response_class=HTMLResponse)
    async def review_page(request: Request, session_id: str):
        """
        Display the review page for a session.

        Args:
            session_id: Review session ID

        Returns:
            HTML page with paper review UI
        """
        try:
            # Get session from database
            review_session = await db.get_review_session(session_id)

            if not review_session:
                return templates.TemplateResponse(
                    "error.html",
                    {"request": request, "error": "审核会话不存在"}
                )

            # Check expiration
            expires_at = review_session.expires_at
            if expires_at and datetime.utcnow() > expires_at:
                return templates.TemplateResponse(
                    "error.html",
                    {"request": request, "error": "审核链接已过期"}
                )

            # Check if already reviewed
            if review_session.status != "pending":
                return templates.TemplateResponse(
                    "completed.html",
                    {
                        "request": request,
                        "status": review_session.status,
                        "reviewed_at": review_session.reviewed_at
                    }
                )

            # Parse papers data
            papers_data = json.loads(review_session.papers_data) if review_session.papers_data else []

            return templates.TemplateResponse(
                "review.html",
                {
                    "request": request,
                    "session_id": session_id,
                    "papers": papers_data,
                    "expire_time": expires_at.strftime("%Y-%m-%d %H:%M:%S") if expires_at else ""
                }
            )

        except Exception as e:
            logger.error(f"Error loading review page: {e}")
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": f"加载审核页面失败: {str(e)}"}
            )

    @app.post("/api/review/{session_id}")
    async def submit_review(session_id: str, request: ReviewSubmitRequest):
        """
        Submit review results.

        Args:
            session_id: Review session ID
            request: Review results

        Returns:
            Success or error response
        """
        try:
            # Get session
            review_session = await db.get_review_session(session_id)

            if not review_session:
                raise HTTPException(status_code=404, detail="审核会话不存在")

            if review_session.status != "pending":
                raise HTTPException(status_code=400, detail="该审核已完成")

            # Check expiration
            if review_session.expires_at and datetime.utcnow() > review_session.expires_at:
                raise HTTPException(status_code=400, detail="审核链接已过期")

            # Process results
            approved_count = 0
            rejected_count = 0

            for result in request.results:
                if result.action == "approve":
                    approved_count += 1
                    await db.update_paper_review_status(
                        result.arxiv_id,
                        "approved",
                        result.feedback
                    )
                elif result.action == "reject":
                    rejected_count += 1
                    await db.update_paper_review_status(
                        result.arxiv_id,
                        "rejected",
                        result.feedback
                    )
                elif result.action == "edit":
                    await db.update_paper_review_status(
                        result.arxiv_id,
                        "approved",
                        result.feedback
                    )

            # Update session status
            overall_status = "approved" if approved_count > rejected_count else "rejected"

            await db.update_review_session(
                session_id,
                {
                    "status": overall_status,
                    "review_result": json.dumps([r.dict() for r in request.results]),
                    "reviewed_at": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                f"Review completed: session={session_id}, "
                f"approved={approved_count}, rejected={rejected_count}"
            )

            return {
                "success": True,
                "status": overall_status,
                "approved_count": approved_count,
                "rejected_count": rejected_count
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error submitting review: {e}")
            raise HTTPException(status_code=500, detail=f"提交审核失败: {str(e)}")

    @app.get("/api/review/{session_id}/status", response_model=ReviewStatusResponse)
    async def get_review_status(session_id: str):
        """
        Get the status of a review session.

        Args:
            session_id: Review session ID

        Returns:
            Review status information
        """
        review_session = await db.get_review_session(session_id)

        if not review_session:
            raise HTTPException(status_code=404, detail="审核会话不存在")

        papers_data = json.loads(review_session.papers_data) if review_session.papers_data else []

        return ReviewStatusResponse(
            session_id=session_id,
            status=review_session.status,
            papers_count=len(papers_data),
            reviewed_at=review_session.reviewed_at
        )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

    return app


async def create_review_session(papers: List[Dict[str, Any]]) -> str:
    """
    Create a new review session.

    Args:
        papers: List of paper data to review

    Returns:
        Session ID
    """
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=settings.REVIEW_LINK_EXPIRE_HOURS)

    session_data = {
        "session_id": session_id,
        "papers_data": json.dumps(papers, ensure_ascii=False),
        "status": "pending",
        "expires_at": expires_at
    }

    await db.create_review_session(session_data)

    logger.info(f"Created review session: {session_id}, expires at {expires_at}")

    return session_id


def get_review_url(session_id: str) -> str:
    """
    Get the full review URL for a session.

    Args:
        session_id: Review session ID

    Returns:
        Full URL to the review page
    """
    return f"{settings.REVIEW_BASE_URL}/review/{session_id}"


async def run_server_async(host: str = None, port: int = None):
    """
    Run the web server asynchronously (for use within existing event loop).

    Args:
        host: Server host (uses settings if not provided)
        port: Server port (uses settings if not provided)
    """
    import uvicorn

    host = host or settings.REVIEW_SERVER_HOST
    port = port or settings.REVIEW_SERVER_PORT

    app = create_app()

    logger.info(f"Starting review server on {host}:{port}")

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


def run_server(host: str = None, port: int = None):
    """
    Run the web server (blocking, creates new event loop).

    Args:
        host: Server host (uses settings if not provided)
        port: Server port (uses settings if not provided)
    """
    import uvicorn

    host = host or settings.REVIEW_SERVER_HOST
    port = port or settings.REVIEW_SERVER_PORT

    app = create_app()

    logger.info(f"Starting review server on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


# For running directly
if __name__ == "__main__":
    import asyncio
    asyncio.run(db.init())
    run_server()