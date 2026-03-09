"""
Semantic Scholar API client for citation and influence data.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import httpx
from loguru import logger


@dataclass
class AuthorInfo:
    """Author information from Semantic Scholar."""
    author_id: str
    name: str
    h_index: Optional[int] = None
    citation_count: Optional[int] = None
    affiliation: Optional[str] = None


@dataclass
class PaperMetrics:
    """Paper metrics from Semantic Scholar."""
    paper_id: str
    title: str
    citation_count: int
    influential_citation_count: int
    reference_count: int
    year: Optional[int] = None
    authors: List[AuthorInfo] = None
    venue: Optional[str] = None
    tldr: Optional[str] = None


class SemanticScholarClient:
    """
    Async client for Semantic Scholar API.
    API documentation: https://api.semanticscholar.org/
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None, delay_seconds: float = 0.1):
        """
        Initialize Semantic Scholar client.

        Args:
            api_key: Optional API key for higher rate limits
            delay_seconds: Delay between API calls
        """
        self.api_key = api_key
        self.delay_seconds = delay_seconds
        self._last_request_time: Optional[datetime] = None

    def _get_headers(self) -> dict:
        """Get request headers with optional API key."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)

    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[PaperMetrics]:
        """
        Get paper metrics by arxiv ID.

        Args:
            arxiv_id: arxiv paper ID (e.g., "2301.12345")

        Returns:
            PaperMetrics if found, None otherwise
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/paper/arXiv:{arxiv_id}"
        params = {
            "fields": "paperId,title,citationCount,influentialCitationCount,referenceCount,year,authors,venue,tldr"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                self._last_request_time = datetime.now()

                if response.status_code == 404:
                    logger.debug(f"Paper not found on Semantic Scholar: {arxiv_id}")
                    return None

                response.raise_for_status()
                data = response.json()

                authors = []
                for author_data in data.get("authors", []):
                    authors.append(AuthorInfo(
                        author_id=author_data.get("authorId", ""),
                        name=author_data.get("name", ""),
                    ))

                tldr = None
                if data.get("tldr"):
                    tldr = data["tldr"].get("text")

                return PaperMetrics(
                    paper_id=data["paperId"],
                    title=data.get("title", ""),
                    citation_count=data.get("citationCount", 0),
                    influential_citation_count=data.get("influentialCitationCount", 0),
                    reference_count=data.get("referenceCount", 0),
                    year=data.get("year"),
                    authors=authors,
                    venue=data.get("venue"),
                    tldr=tldr,
                )
            except Exception as e:
                logger.warning(f"Failed to fetch paper {arxiv_id} from Semantic Scholar: {e}")
                return None

    async def get_author_info(self, author_id: str) -> Optional[AuthorInfo]:
        """
        Get detailed author information.

        Args:
            author_id: Semantic Scholar author ID

        Returns:
            AuthorInfo if found, None otherwise
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/author/{author_id}"
        params = {
            "fields": "authorId,name,hIndex,citationCount,affiliations"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                self._last_request_time = datetime.now()

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

                affiliation = None
                if data.get("affiliations"):
                    affiliation = data["affiliations"][0]

                return AuthorInfo(
                    author_id=data["authorId"],
                    name=data.get("name", ""),
                    h_index=data.get("hIndex"),
                    citation_count=data.get("citationCount"),
                    affiliation=affiliation,
                )
            except Exception as e:
                logger.warning(f"Failed to fetch author {author_id}: {e}")
                return None

    async def get_papers_batch(
        self,
        arxiv_ids: List[str],
        batch_size: int = 100
    ) -> dict[str, PaperMetrics]:
        """
        Get metrics for multiple papers by arxiv IDs.

        Args:
            arxiv_ids: List of arxiv paper IDs
            batch_size: Number of papers per batch request

        Returns:
            Dictionary mapping arxiv_id to PaperMetrics
        """
        results = {}

        for i in range(0, len(arxiv_ids), batch_size):
            batch = arxiv_ids[i:i + batch_size]
            await self._rate_limit()

            # Use batch endpoint
            url = f"{self.BASE_URL}/paper/batch"
            params = {
                "fields": "paperId,title,citationCount,influentialCitationCount,referenceCount,year,authors,venue"
            }

            paper_ids = [f"arXiv:{aid}" for aid in batch]

            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    response = await client.post(
                        url,
                        params=params,
                        json={"ids": paper_ids},
                        headers=self._get_headers()
                    )
                    self._last_request_time = datetime.now()
                    response.raise_for_status()

                    for data in response.json():
                        if data is None:
                            continue

                        # Extract arxiv ID from the response
                        arxiv_id = None
                        for aid in batch:
                            if data.get("paperId"):
                                arxiv_id = aid
                                break

                        if arxiv_id:
                            authors = []
                            for author_data in data.get("authors", []):
                                authors.append(AuthorInfo(
                                    author_id=author_data.get("authorId", ""),
                                    name=author_data.get("name", ""),
                                ))

                            results[arxiv_id] = PaperMetrics(
                                paper_id=data["paperId"],
                                title=data.get("title", ""),
                                citation_count=data.get("citationCount", 0),
                                influential_citation_count=data.get("influentialCitationCount", 0),
                                reference_count=data.get("referenceCount", 0),
                                year=data.get("year"),
                                authors=authors,
                                venue=data.get("venue"),
                            )
                except Exception as e:
                    logger.warning(f"Failed to fetch batch papers: {e}")

        return results