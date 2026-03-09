"""
Arxiv API client for fetching AI Agent related papers.
"""
import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote

import httpx
from loguru import logger


@dataclass
class ArxivPaper:
    """Data class representing an arxiv paper."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published_date: datetime
    updated_date: datetime
    pdf_url: str
    abs_url: str

    def __hash__(self):
        return hash(self.arxiv_id)

    def __eq__(self, other):
        if isinstance(other, ArxivPaper):
            return self.arxiv_id == other.arxiv_id
        return False


class ArxivClient:
    """
    Async client for arxiv API.
    API documentation: https://export.arxiv.org/api/query
    """

    BASE_URL = "https://export.arxiv.org/api/query"

    # AI Agent related categories
    AGENT_CATEGORIES = [
        "cs.AI",  # Artificial Intelligence
        "cs.MA",  # Multiagent Systems
        "cs.CL",  # Computation and Language (NLP)
        "cs.LG",  # Machine Learning
        "cs.RO",  # Robotics
    ]

    # Keywords for agent-related papers
    AGENT_KEYWORDS = [
        "agent",
        "multi-agent",
        "LLM agent",
        "autonomous agent",
        "intelligent agent",
        "agent system",
        "agent framework",
        "AI agent",
        "agent planning",
        "agent reasoning",
    ]

    def __init__(self, batch_size: int = 100, delay_seconds: float = 3.0):
        """
        Initialize arxiv client.

        Args:
            batch_size: Maximum number of results per request
            delay_seconds: Delay between API calls to respect rate limits
        """
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds
        self._last_request_time: Optional[datetime] = None

    def _build_query(
        self,
        categories: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        date_range_days: int = 1
    ) -> str:
        """
        Build arxiv API query string.

        Args:
            categories: List of arxiv categories to search
            keywords: List of keywords to search in title/abstract
            date_range_days: Number of days to look back

        Returns:
            Query string for arxiv API
        """
        categories = categories or self.AGENT_CATEGORIES
        keywords = keywords or self.AGENT_KEYWORDS

        # Build category query (OR)
        cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
        cat_query = f"({cat_query})"

        # Build keyword query (OR) for title and abstract
        keyword_parts = []
        for kw in keywords:
            keyword_parts.append(f"ti:{quote(kw)}")
            keyword_parts.append(f"abs:{quote(kw)}")
        keyword_query = " OR ".join(keyword_parts)
        keyword_query = f"({keyword_query})"

        # Combine: papers in agent categories OR papers with agent keywords
        query = f"{cat_query} OR {keyword_query}"

        return query

    def _parse_paper(self, entry: ET.Element) -> ArxivPaper:
        """
        Parse arxiv API entry element into ArxivPaper.

        Args:
            entry: XML element representing a paper entry

        Returns:
            ArxivPaper instance
        """
        # Extract arxiv ID from the id element
        id_url = entry.find("{http://www.w3.org/2005/Atom}id").text
        arxiv_id = id_url.split("/")[-1]

        # Title
        title = entry.find("{http://www.w3.org/2005/Atom}title").text.strip()
        title = " ".join(title.split())  # Normalize whitespace

        # Authors
        authors = []
        for author in entry.findall("{http://www.w3.org/2005/Atom}author"):
            name = author.find("{http://www.w3.org/2005/Atom}name").text
            authors.append(name)

        # Abstract
        abstract = entry.find("{http://www.w3.org/2005/Atom}summary").text.strip()
        abstract = " ".join(abstract.split())  # Normalize whitespace

        # Categories
        categories = []
        for cat in entry.findall("{http://www.w3.org/2005/Atom}category"):
            categories.append(cat.get("term"))

        # Dates
        published = entry.find("{http://www.w3.org/2005/Atom}published").text
        updated = entry.find("{http://www.w3.org/2005/Atom}updated").text

        published_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        updated_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))

        # URLs
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            categories=categories,
            published_date=published_date,
            updated_date=updated_date,
            pdf_url=pdf_url,
            abs_url=abs_url,
        )

    async def fetch_papers(
        self,
        max_results: int = 100,
        categories: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        date_range_days: int = 1,
        start_index: int = 0
    ) -> List[ArxivPaper]:
        """
        Fetch papers from arxiv API.

        Args:
            max_results: Maximum number of papers to fetch
            categories: List of arxiv categories to search
            keywords: List of keywords to search
            date_range_days: Number of days to look back
            start_index: Start index for pagination

        Returns:
            List of ArxivPaper instances
        """
        query = self._build_query(categories, keywords, date_range_days)

        params = {
            "search_query": query,
            "start": start_index,
            "max_results": min(max_results, self.batch_size),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        # Rate limiting
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)

        logger.info(f"Fetching papers from arxiv with query: {query[:100]}...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            self._last_request_time = datetime.now()

        # Parse XML response
        root = ET.fromstring(response.content)

        papers = []
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            try:
                paper = self._parse_paper(entry)
                papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to parse paper entry: {e}")
                continue

        logger.info(f"Fetched {len(papers)} papers from arxiv")
        return papers

    async def fetch_papers_by_ids(self, arxiv_ids: List[str]) -> List[ArxivPaper]:
        """
        Fetch specific papers by their arxiv IDs.

        Args:
            arxiv_ids: List of arxiv IDs

        Returns:
            List of ArxivPaper instances
        """
        if not arxiv_ids:
            return []

        id_list = ",".join(arxiv_ids)
        params = {
            "id_list": id_list,
            "max_results": len(arxiv_ids),
        }

        # Rate limiting
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            self._last_request_time = datetime.now()

        root = ET.fromstring(response.content)

        papers = []
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            try:
                paper = self._parse_paper(entry)
                papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to parse paper entry: {e}")
                continue

        return papers

    async def fetch_daily_papers(self) -> List[ArxivPaper]:
        """
        Fetch AI Agent related papers from the last 24 hours.

        Returns:
            List of ArxivPaper instances
        """
        return await self.fetch_papers(
            max_results=200,
            date_range_days=1
        )