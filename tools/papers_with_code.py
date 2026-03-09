"""
Papers with Code API client for community heat metrics.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import httpx
from loguru import logger


@dataclass
class Repository:
    """Repository information from Papers with Code."""
    url: str
    stars: int
    forks: Optional[int] = None
    description: Optional[str] = None
    is_official: bool = False


@dataclass
class PaperCommunityMetrics:
    """Community metrics for a paper from Papers with Code."""
    paper_id: str
    title: str
    repositories: List[Repository]
    stars_total: int
    implementation_count: int
    arxiv_id: Optional[str] = None
    is_on_hub: bool = False
    dataset_count: int = 0


class PapersWithCodeClient:
    """
    Async client for Papers with Code API.
    API documentation: https://paperswithcode.com/api/v1/docs/
    """

    BASE_URL = "https://paperswithcode.com/api/v1"

    def __init__(self, delay_seconds: float = 0.5):
        """
        Initialize Papers with Code client.

        Args:
            delay_seconds: Delay between API calls
        """
        self.delay_seconds = delay_seconds
        self._last_request_time: Optional[datetime] = None

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)

    async def search_paper_by_arxiv(self, arxiv_id: str) -> Optional[PaperCommunityMetrics]:
        """
        Search for a paper by arxiv ID.

        Args:
            arxiv_id: arxiv paper ID

        Returns:
            PaperCommunityMetrics if found, None otherwise
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/papers/"
        params = {"arxiv_id": arxiv_id}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                self._last_request_time = datetime.now()

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    return None

                return self._parse_paper_data(results[0])
            except Exception as e:
                logger.debug(f"Paper {arxiv_id} not found on Papers with Code: {e}")
                return None

    async def get_paper(self, paper_id: str) -> Optional[PaperCommunityMetrics]:
        """
        Get paper by Papers with Code ID.

        Args:
            paper_id: Papers with Code paper ID

        Returns:
            PaperCommunityMetrics if found, None otherwise
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/papers/{paper_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url)
                self._last_request_time = datetime.now()

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

                return self._parse_paper_data(data)
            except Exception as e:
                logger.warning(f"Failed to get paper {paper_id}: {e}")
                return None

    async def get_repositories(self, paper_id: str) -> List[Repository]:
        """
        Get repositories for a paper.

        Args:
            paper_id: Papers with Code paper ID

        Returns:
            List of Repository instances
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/papers/{paper_id}/repositories/"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url)
                self._last_request_time = datetime.now()
                response.raise_for_status()
                data = response.json()

                repos = []
                for result in data.get("results", []):
                    repos.append(Repository(
                        url=result.get("url", ""),
                        stars=result.get("stars", 0),
                        forks=result.get("forks"),
                        description=result.get("description"),
                        is_official=result.get("is_official", False),
                    ))

                return repos
            except Exception as e:
                logger.warning(f"Failed to get repositories for {paper_id}: {e}")
                return []

    def _parse_paper_data(self, data: dict) -> PaperCommunityMetrics:
        """Parse paper data from API response."""
        repos = []
        for repo_data in data.get("repositories", []):
            repos.append(Repository(
                url=repo_data.get("url", ""),
                stars=repo_data.get("stars", 0),
                forks=repo_data.get("forks"),
                description=repo_data.get("description"),
                is_official=repo_data.get("is_official", False),
            ))

        return PaperCommunityMetrics(
            paper_id=data.get("id", ""),
            arxiv_id=data.get("arxiv_id"),
            title=data.get("title", ""),
            repositories=repos,
            stars_total=sum(r.stars for r in repos),
            implementation_count=len(repos),
            is_on_hub=data.get("is_on_hub", False),
            dataset_count=data.get("dataset_count", 0),
        )

    def calculate_community_heat_score(
        self,
        metrics: PaperCommunityMetrics,
        max_stars: int = 10000,
        max_implementations: int = 50
    ) -> float:
        """
        Calculate normalized community heat score.

        Args:
            metrics: PaperCommunityMetrics instance
            max_stars: Maximum stars for normalization
            max_implementations: Maximum implementations for normalization

        Returns:
            Normalized score between 0 and 1
        """
        if not metrics:
            return 0.0

        import math

        # Normalize stars (log scale)
        stars = metrics.stars_total
        star_score = min(math.log10(stars + 1) / math.log10(max_stars + 1), 1.0)

        # Normalize implementation count
        impl_score = min(metrics.implementation_count / max_implementations, 1.0)

        # Official implementation bonus
        official_bonus = 0.1 if any(r.is_official for r in metrics.repositories) else 0.0

        # Hugging Face hub bonus
        hub_bonus = 0.1 if metrics.is_on_hub else 0.0

        # Combine scores
        score = 0.5 * star_score + 0.3 * impl_score + official_bonus + hub_bonus
        return min(score, 1.0)