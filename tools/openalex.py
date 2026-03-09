"""
OpenAlex API client for author and institution data.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote

import httpx
from loguru import logger


@dataclass
class Institution:
    """Institution information from OpenAlex."""
    institution_id: str
    name: str
    country: Optional[str] = None
    type: Optional[str] = None  # education, company, etc.
    ror_id: Optional[str] = None


@dataclass
class AuthorProfile:
    """Author profile from OpenAlex."""
    openalex_id: str
    name: str
    orcid: Optional[str] = None
    h_index: Optional[int] = None
    i10_index: Optional[int] = None
    works_count: Optional[int] = None
    cited_by_count: Optional[int] = None
    last_known_institution: Optional[Institution] = None


class OpenAlexClient:
    """
    Async client for OpenAlex API.
    API documentation: https://docs.openalex.org/
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: Optional[str] = None, delay_seconds: float = 0.1):
        """
        Initialize OpenAlex client.

        Args:
            email: Email for polite pool (faster responses)
            delay_seconds: Delay between API calls
        """
        self.email = email
        self.delay_seconds = delay_seconds
        self._last_request_time: Optional[datetime] = None

    def _get_headers(self) -> dict:
        """Get request headers with email for polite pool."""
        headers = {"Accept": "application/json"}
        if self.email:
            headers["mailto"] = self.email
        return headers

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)

    async def search_author_by_name(self, name: str) -> List[AuthorProfile]:
        """
        Search for authors by name.

        Args:
            name: Author name to search

        Returns:
            List of matching AuthorProfile instances
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/authors"
        params = {
            "search": name,
            "per_page": 10,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                self._last_request_time = datetime.now()
                response.raise_for_status()
                data = response.json()

                authors = []
                for result in data.get("results", []):
                    institution = None
                    inst_data = result.get("last_known_institution")
                    if inst_data:
                        institution = Institution(
                            institution_id=inst_data.get("id", ""),
                            name=inst_data.get("display_name", ""),
                            country=inst_data.get("country_code"),
                            type=inst_data.get("type"),
                            ror_id=inst_data.get("ror"),
                        )

                    authors.append(AuthorProfile(
                        openalex_id=result.get("id", ""),
                        name=result.get("display_name", ""),
                        orcid=result.get("orcid"),
                        h_index=result.get("summary_stats", {}).get("h_index"),
                        i10_index=result.get("summary_stats", {}).get("i10_index"),
                        works_count=result.get("works_count"),
                        cited_by_count=result.get("cited_by_count"),
                        last_known_institution=institution,
                    ))

                return authors
            except Exception as e:
                logger.warning(f"Failed to search author '{name}': {e}")
                return []

    async def get_author(self, openalex_id: str) -> Optional[AuthorProfile]:
        """
        Get author by OpenAlex ID.

        Args:
            openalex_id: OpenAlex author ID (e.g., "A1234567890")

        Returns:
            AuthorProfile if found, None otherwise
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/authors/{openalex_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                self._last_request_time = datetime.now()

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                result = response.json()

                institution = None
                inst_data = result.get("last_known_institution")
                if inst_data:
                    institution = Institution(
                        institution_id=inst_data.get("id", ""),
                        name=inst_data.get("display_name", ""),
                        country=inst_data.get("country_code"),
                        type=inst_data.get("type"),
                        ror_id=inst_data.get("ror"),
                    )

                return AuthorProfile(
                    openalex_id=result.get("id", ""),
                    name=result.get("display_name", ""),
                    orcid=result.get("orcid"),
                    h_index=result.get("summary_stats", {}).get("h_index"),
                    i10_index=result.get("summary_stats", {}).get("i10_index"),
                    works_count=result.get("works_count"),
                    cited_by_count=result.get("cited_by_count"),
                    last_known_institution=institution,
                )
            except Exception as e:
                logger.warning(f"Failed to get author {openalex_id}: {e}")
                return None

    async def get_institution(self, openalex_id: str) -> Optional[Institution]:
        """
        Get institution by OpenAlex ID.

        Args:
            openalex_id: OpenAlex institution ID (e.g., "I1234567890")

        Returns:
            Institution if found, None otherwise
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/institutions/{openalex_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                self._last_request_time = datetime.now()

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                result = response.json()

                return Institution(
                    institution_id=result.get("id", ""),
                    name=result.get("display_name", ""),
                    country=result.get("country_code"),
                    type=result.get("type"),
                    ror_id=result.get("ror"),
                )
            except Exception as e:
                logger.warning(f"Failed to get institution {openalex_id}: {e}")
                return None

    def calculate_author_influence_score(
        self,
        author: AuthorProfile,
        max_h_index: int = 100,
        max_citations: int = 100000
    ) -> float:
        """
        Calculate normalized influence score for an author.

        Args:
            author: AuthorProfile instance
            max_h_index: Maximum h-index for normalization
            max_citations: Maximum citations for normalization

        Returns:
            Normalized score between 0 and 1
        """
        if not author:
            return 0.0

        h_index = author.h_index or 0
        citations = author.cited_by_count or 0

        # Normalize h-index (0-1)
        h_score = min(h_index / max_h_index, 1.0)

        # Normalize citations (log scale for better distribution)
        import math
        citation_score = min(math.log10(citations + 1) / math.log10(max_citations + 1), 1.0)

        # Institution bonus
        inst_bonus = 0.0
        if author.last_known_institution:
            # Top institutions get bonus
            top_institutions = {
                "MIT", "Stanford", "CMU", "UC Berkeley", "Google",
                "DeepMind", "OpenAI", "Microsoft", "Meta", "Tsinghua",
                "Peking University", "ETH Zurich", "Oxford", "Cambridge"
            }
            if any(top in author.last_known_institution.name for top in top_institutions):
                inst_bonus = 0.2

        # Combine scores
        score = 0.4 * h_score + 0.4 * citation_score + inst_bonus
        return min(score, 1.0)