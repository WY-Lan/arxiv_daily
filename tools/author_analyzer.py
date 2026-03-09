"""
Author history analyzer for assessing author track record.

This module analyzes an author's publication history to assess
the quality and consistency of their research work.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

import httpx
from loguru import logger


@dataclass
class AuthorPaperRecord:
    """Record of a paper by an author."""
    title: str
    venue: Optional[str] = None
    year: Optional[int] = None
    citation_count: int = 0
    influential_citations: int = 0
    arxiv_id: Optional[str] = None
    is_high_impact: bool = False


@dataclass
class AuthorTrackRecord:
    """Author's research track record analysis."""
    author_id: str
    author_name: str
    total_papers: int = 0
    papers_last_5_years: int = 0
    total_citations: int = 0
    h_index: Optional[int] = None
    i10_index: Optional[int] = None
    high_impact_papers: int = 0
    venue_quality_score: float = 0.0
    consistency_score: float = 0.0
    recent_activity_score: float = 0.0
    collaboration_score: float = 0.0
    quality_score: float = 0.0  # Overall quality score (0-1)
    papers: List[AuthorPaperRecord] = field(default_factory=list)
    top_venues: List[str] = field(default_factory=list)
    analysis_timestamp: datetime = field(default_factory=datetime.now)


class SemanticScholarAuthorClient:
    """Client for fetching author data from Semantic Scholar."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None, delay_seconds: float = 0.5):
        self.api_key = api_key
        self.delay_seconds = delay_seconds
        self._cache: Dict[str, AuthorTrackRecord] = {}

    def _get_headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def search_author(self, name: str) -> Optional[str]:
        """
        Search for author by name and return author ID.

        Args:
            name: Author name

        Returns:
            Author ID if found, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.BASE_URL}/author/search"
                params = {
                    "query": name,
                    "fields": "authorId,name",
                    "limit": 5
                }

                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

                if data.get("data"):
                    # Return the first match (best match)
                    return data["data"][0]["authorId"]

        except Exception as e:
            logger.warning(f"Failed to search author {name}: {e}")

        return None

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get papers by author.

        Args:
            author_id: Semantic Scholar author ID
            limit: Maximum number of papers to fetch

        Returns:
            List of paper data
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.BASE_URL}/author/{author_id}/papers"
                params = {
                    "fields": "title,year,citationCount,influentialCitationCount,venue,authors",
                    "limit": limit
                }

                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

                return data.get("data", [])

        except Exception as e:
            logger.warning(f"Failed to fetch papers for author {author_id}: {e}")
            return []

    async def get_author_details(self, author_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed author information.

        Args:
            author_id: Semantic Scholar author ID

        Returns:
            Author details including h-index
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.BASE_URL}/author/{author_id}"
                params = {
                    "fields": "authorId,name,hIndex,citationCount,paperCount"
                }

                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.warning(f"Failed to fetch author details for {author_id}: {e}")
            return None


class AuthorHistoryAnalyzer:
    """
    Analyze author history to assess research quality and consistency.
    """

    # Top tier venues in AI/ML (customize based on your domain)
    TOP_TIER_VENUES = {
        # ML conferences
        "neurips", "icml", "iclr", "nips",
        # AI conferences
        "aaai", "ijcai",
        # NLP conferences
        "acl", "emnlp", "naacl", "coling",
        # Vision conferences
        "cvpr", "iccv", "eccv",
        # Robotics
        "icra", "iros",
        # Journals
        "nature", "science", "tpami", "ijcv", "jmlr", "ai journal"
    }

    # Second tier venues
    SECOND_TIER_VENUES = {
        "aistats", "uai", "kdd", "www", "icdm", "sdm",
        "wacv", "bmvc", "accv",
        "eacl", "conll", "findings",
        "aamas", "atal", "kr"
    }

    def __init__(self, api_key: Optional[str] = None):
        self.ss_client = SemanticScholarAuthorClient(api_key)
        self._cache: Dict[str, AuthorTrackRecord] = {}

    async def analyze_author(self, author_name: str, author_id: Optional[str] = None) -> AuthorTrackRecord:
        """
        Analyze an author's research track record.

        Args:
            author_name: Author's name
            author_id: Optional Semantic Scholar author ID

        Returns:
            AuthorTrackRecord with comprehensive analysis
        """
        # Check cache
        cache_key = author_id or author_name
        if cache_key in self._cache:
            return self._cache[cache_key]

        record = AuthorTrackRecord(
            author_id=author_id or "",
            author_name=author_name
        )

        # 1. Search for author ID if not provided
        if not author_id:
            author_id = await self.ss_client.search_author(author_name)
            if not author_id:
                logger.warning(f"Could not find author: {author_name}")
                record.quality_score = 0.5  # Neutral score for unknown authors
                return record
            record.author_id = author_id

        # 2. Get author details
        details = await self.ss_client.get_author_details(author_id)
        if details:
            record.h_index = details.get("hIndex")
            record.total_citations = details.get("citationCount", 0)
            record.total_papers = details.get("paperCount", 0)

        # 3. Get author papers
        papers_data = await self.ss_client.get_author_papers(author_id, limit=100)

        if not papers_data:
            record.quality_score = 0.5
            return record

        # 4. Analyze papers
        await self._analyze_papers(record, papers_data)

        # 5. Calculate quality score
        record.quality_score = self._calculate_quality_score(record)

        # Cache result
        self._cache[cache_key] = record

        return record

    async def _analyze_papers(self, record: AuthorTrackRecord, papers_data: List[Dict]):
        """Analyze papers and populate record."""
        current_year = datetime.now().year
        five_years_ago = current_year - 5

        venue_scores = []
        yearly_papers = defaultdict(int)
        unique_coauthors: Set[str] = set()

        for paper_data in papers_data:
            year = paper_data.get("year")
            venue = paper_data.get("venue", "").lower() if paper_data.get("venue") else ""
            citations = paper_data.get("citationCount", 0)
            influential = paper_data.get("influentialCitationCount", 0)

            # Create paper record
            paper_record = AuthorPaperRecord(
                title=paper_data.get("title", ""),
                venue=paper_data.get("venue"),
                year=year,
                citation_count=citations,
                influential_citations=influential,
                is_high_impact=self._is_high_impact_paper(citations, venue)
            )
            record.papers.append(paper_record)

            # Count recent papers
            if year and year >= five_years_ago:
                record.papers_last_5_years += 1

            # Count high impact papers
            if paper_record.is_high_impact:
                record.high_impact_papers += 1

            # Score venue
            venue_score = self._score_venue(venue)
            if venue_score > 0:
                venue_scores.append(venue_score)

            # Track yearly output
            if year:
                yearly_papers[year] += 1

            # Track coauthors
            for author in paper_data.get("authors", []):
                if author.get("name") != record.author_name:
                    unique_coauthors.add(author.get("name", ""))

        # Calculate metrics
        if venue_scores:
            record.venue_quality_score = sum(venue_scores) / len(venue_scores)

        # Consistency: variance in yearly output
        if yearly_papers:
            paper_counts = list(yearly_papers.values())
            avg_papers = sum(paper_counts) / len(paper_counts)
            variance = sum((c - avg_papers) ** 2 for c in paper_counts) / len(paper_counts)
            # Lower variance = higher consistency (capped at 1.0)
            record.consistency_score = max(0, 1.0 - (variance / 10))

        # Recent activity
        if record.papers_last_5_years > 0:
            record.recent_activity_score = min(1.0, record.papers_last_5_years / 20)

        # Collaboration score (diversity of coauthors)
        record.collaboration_score = min(1.0, len(unique_coauthors) / 50)

        # Top venues
        venue_counts = defaultdict(int)
        for p in record.papers:
            if p.venue:
                venue_counts[p.venue] += 1
        record.top_venues = [v for v, _ in sorted(venue_counts.items(), key=lambda x: x[1], reverse=True)[:5]]

    def _is_high_impact_paper(self, citations: int, venue: str) -> bool:
        """Determine if a paper is high impact."""
        # High citations
        if citations >= 100:
            return True

        # Top venue
        venue_lower = venue.lower()
        if any(top in venue_lower for top in self.TOP_TIER_VENUES):
            return True

        return False

    def _score_venue(self, venue: str) -> float:
        """Score a publication venue (0-1 scale)."""
        venue_lower = venue.lower()

        # Top tier
        for top in self.TOP_TIER_VENUES:
            if top in venue_lower:
                return 1.0

        # Second tier
        for second in self.SECOND_TIER_VENUES:
            if second in venue_lower:
                return 0.7

        # Other venues
        if venue and len(venue) > 3:
            return 0.4

        # Unknown/unpublished
        return 0.0

    def _calculate_quality_score(self, record: AuthorTrackRecord) -> float:
        """
        Calculate overall author quality score.

        Combines multiple factors:
        - Publication venue quality (30%)
        - Citation impact (25%)
        - Consistency (15%)
        - Recent activity (15%)
        - Collaboration diversity (15%)
        """
        # Venue quality (normalized)
        venue_score = record.venue_quality_score

        # Citation impact (log scale, normalized)
        citation_score = min(1.0, record.total_citations / 1000)
        if record.h_index:
            h_index_score = min(1.0, record.h_index / 50)
            citation_score = max(citation_score, h_index_score)

        # Consistency
        consistency_score = record.consistency_score

        # Recent activity
        activity_score = record.recent_activity_score

        # Collaboration
        collab_score = record.collaboration_score

        # Weighted combination
        weights = {
            "venue": 0.30,
            "citation": 0.25,
            "consistency": 0.15,
            "activity": 0.15,
            "collaboration": 0.15
        }

        overall = (
            weights["venue"] * venue_score +
            weights["citation"] * citation_score +
            weights["consistency"] * consistency_score +
            weights["activity"] * activity_score +
            weights["collaboration"] * collab_score
        )

        return round(overall, 2)


class PaperAuthorsAnalyzer:
    """
    Analyze all authors of a paper to get combined quality score.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.author_analyzer = AuthorHistoryAnalyzer(api_key)

    async def analyze_paper_authors(
        self,
        authors: List[str],
        author_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze all authors of a paper.

        Args:
            authors: List of author names
            author_ids: Optional list of Semantic Scholar author IDs

        Returns:
            Combined analysis result
        """
        if not authors:
            return {
                "overall_score": 0.5,
                "author_count": 0,
                "top_author": None,
                "concerns": ["No author information"]
            }

        author_records = []
        tasks = []

        for i, name in enumerate(authors):
            author_id = author_ids[i] if author_ids and i < len(author_ids) else None
            tasks.append(self.author_analyzer.analyze_author(name, author_id))

        # Analyze all authors concurrently
        records = await asyncio.gather(*tasks, return_exceptions=True)

        for record in records:
            if isinstance(record, AuthorTrackRecord):
                author_records.append(record)
            else:
                logger.warning(f"Failed to analyze author: {record}")

        if not author_records:
            return {
                "overall_score": 0.5,
                "author_count": len(authors),
                "top_author": None,
                "concerns": ["Could not analyze any authors"]
            }

        # Calculate combined scores
        quality_scores = [r.quality_score for r in author_records]
        h_indices = [r.h_index for r in author_records if r.h_index]

        # Use max score for top author, average for overall
        max_score = max(quality_scores)
        avg_score = sum(quality_scores) / len(quality_scores)

        # Weight: 60% top author, 40% average
        combined_score = 0.6 * max_score + 0.4 * avg_score

        # Find top author
        top_author = max(author_records, key=lambda r: r.quality_score)

        # Identify concerns
        concerns = []
        low_quality_count = sum(1 for s in quality_scores if s < 0.3)
        if low_quality_count > len(author_records) / 2:
            concerns.append("Majority of authors have limited track record")

        if top_author.quality_score < 0.3:
            concerns.append("No established researcher in author list")

        if top_author.papers_last_5_years < 3:
            concerns.append("Low recent activity from lead author")

        return {
            "overall_score": round(combined_score, 2),
            "author_count": len(authors),
            "analyzed_count": len(author_records),
            "top_author": {
                "name": top_author.author_name,
                "quality_score": top_author.quality_score,
                "h_index": top_author.h_index,
                "total_citations": top_author.total_citations,
                "top_venues": top_author.top_venues[:3]
            },
            "author_details": [
                {
                    "name": r.author_name,
                    "score": r.quality_score,
                    "h_index": r.h_index,
                    "high_impact_papers": r.high_impact_papers
                }
                for r in author_records[:3]  # Top 3 authors
            ],
            "concerns": concerns
        }
