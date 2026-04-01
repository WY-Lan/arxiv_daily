"""
Arxiv API client for fetching AI Agent related papers.
Supports both API and web scraping modes.
"""
import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
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

    Supports two modes:
    - API mode: Use arXiv's official API (may be rate limited)
    - Web scraping mode: Fetch papers via web pages (more reliable)
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

    def __init__(self, batch_size: int = 100, delay_seconds: float = 3.0, use_web_scraping: bool = False, use_new_page: bool = True):
        """
        Initialize arxiv client.

        Args:
            batch_size: Maximum number of results per request
            delay_seconds: Delay between API calls to respect rate limits
            use_web_scraping: Use web scraping instead of API (recommended when API is rate limited)
            use_new_page: Use /new page (today's papers) instead of /recent (recent days)
        """
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds
        self.use_web_scraping = use_web_scraping
        self.use_new_page = use_new_page
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
        if self.use_web_scraping:
            return await self.fetch_papers_via_web_scraping(use_new_page=self.use_new_page)
        return await self.fetch_papers(
            max_results=200,
            date_range_days=1
        )

    async def fetch_papers_via_web_scraping(
        self,
        categories: Optional[List[str]] = None,
        max_results: int = 200,
        use_new_page: bool = True
    ) -> List[ArxivPaper]:
        """
        Fetch papers via web scraping (more reliable when API is rate limited).

        Args:
            categories: List of arxiv categories to search (default: agent categories)
            max_results: Maximum number of papers to fetch
            use_new_page: Use /new page (today's papers) instead of /recent (recent days)

        Returns:
            List of ArxivPaper instances
        """
        categories = categories or self.AGENT_CATEGORIES
        papers = []
        seen_ids = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for category in categories:
                try:
                    # Use /new for today's papers, /recent for recent days
                    page_type = "new" if use_new_page else "recent"
                    url = f"https://arxiv.org/list/{category}/{page_type}"
                    logger.info(f"Fetching papers from: {url}")

                    response = await client.get(url)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, 'html.parser')
                    articles = soup.find('dl', id='articles')

                    if not articles:
                        logger.warning(f"No articles found for {category}")
                        continue

                    # Get paper IDs from the list
                    dt_tags = articles.find_all('dt')
                    arxiv_ids = []

                    for dt in dt_tags:
                        a_tag = dt.find('a', title='Abstract')
                        if a_tag:
                            arxiv_id = a_tag.text.strip().replace('arXiv:', '')
                            if arxiv_id not in seen_ids:
                                arxiv_ids.append(arxiv_id)
                                seen_ids.add(arxiv_id)

                    logger.info(f"Found {len(arxiv_ids)} papers in {category}")

                    # Fetch details for each paper (with rate limiting)
                    for arxiv_id in arxiv_ids[:max_results // len(categories)]:
                        try:
                            paper = await self._fetch_paper_details(client, arxiv_id)
                            if paper:
                                # Filter by agent keywords in title/abstract
                                if self._is_agent_related(paper):
                                    papers.append(paper)
                            # Rate limiting between detail fetches
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.warning(f"Failed to fetch details for {arxiv_id}: {e}")
                            continue

                    # Rate limiting between category requests
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(f"Failed to fetch papers from {category}: {e}")
                    continue

        logger.info(f"Fetched {len(papers)} agent-related papers via web scraping")
        return papers

    async def _fetch_paper_details(self, client: httpx.AsyncClient, arxiv_id: str) -> Optional[ArxivPaper]:
        """
        Fetch details for a single paper from its abstract page.

        Args:
            client: HTTP client
            arxiv_id: arXiv paper ID

        Returns:
            ArxivPaper instance or None if failed
        """
        url = f"https://arxiv.org/abs/{arxiv_id}"
        response = await client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Title
        title_elem = soup.find('h1', class_='title')
        title = title_elem.text.replace('Title:', '').strip() if title_elem else ""
        title = " ".join(title.split())  # Normalize whitespace

        # Authors
        authors_div = soup.find('div', class_='authors')
        authors = [a.text for a in authors_div.find_all('a')] if authors_div else []

        # Abstract
        abstract_elem = soup.find('blockquote', class_='abstract')
        abstract = abstract_elem.text.replace('Abstract:', '').strip() if abstract_elem else ""
        abstract = " ".join(abstract.split())  # Normalize whitespace

        # Categories
        subjects_div = soup.find('div', class_='subjects')
        categories = []
        if subjects_div:
            cat_text = subjects_div.text
            # Parse categories like "Primary Category: cs.AI; Secondary Categories: cs.CL, cs.LG"
            if "Primary Category:" in cat_text:
                primary = cat_text.split("Primary Category:")[1].split(";")[0].strip()
                categories.append(primary)
            if "Secondary Categories:" in cat_text:
                secondary = cat_text.split("Secondary Categories:")[1].strip()
                categories.extend([c.strip() for c in secondary.split(",")])

        # Dates
        dateline = soup.find('div', class_='dateline')
        published_date = datetime.now()
        updated_date = datetime.now()

        if dateline:
            date_text = dateline.text.strip()
            # Parse date like "[Submitted on 26 Mar 2026]"
            date_match = date_text.lower()
            if "submitted on" in date_match:
                try:
                    # Extract date string
                    date_str = date_text.split("Submitted on")[1].strip().replace("[", "").replace("]", "")
                    # Parse "26 Mar 2026" format
                    published_date = datetime.strptime(date_str.split("(v1)")[0].strip(), "%d %b %Y")
                    updated_date = published_date
                except Exception:
                    pass

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            categories=categories,
            published_date=published_date,
            updated_date=updated_date,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        )

    def _is_agent_related(self, paper: ArxivPaper) -> bool:
        """
        Check if a paper is related to AI agents based on title/abstract keywords.

        Args:
            paper: ArxivPaper instance

        Returns:
            True if paper is agent-related
        """
        text = f"{paper.title} {paper.abstract}".lower()
        for keyword in self.AGENT_KEYWORDS:
            if keyword.lower() in text:
                return True
        # Also check if in agent categories
        for cat in self.AGENT_CATEGORIES:
            if cat in paper.categories:
                return True
        return False