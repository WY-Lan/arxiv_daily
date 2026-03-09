"""
Social media hot papers tracker.

This module monitors social media platforms (Twitter/X, Reddit, Hacker News, etc.)
to identify trending AI papers and incorporate social signals into the selection process.
"""
import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

import httpx
from loguru import logger


@dataclass
class SocialSignal:
    """Represents social media attention for a paper."""
    platform: str  # twitter, reddit, hackernews, etc.
    arxiv_id: Optional[str]
    paper_title: str
    mention_count: int = 0
    engagement_score: float = 0.0  # Likes, retweets, upvotes, etc.
    sentiment_score: float = 0.0  # -1 to 1
    discussion_quality: float = 0.0  # 0 to 1
    key_discussions: List[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)


@dataclass
class HotPaperMetrics:
    """Aggregated social metrics for a paper."""
    arxiv_id: str
    paper_title: str
    total_mentions: int = 0
    total_engagement: float = 0.0
    platforms: Set[str] = field(default_factory=set)
    sentiment_average: float = 0.0
    discussion_quality: float = 0.0
    trending_score: float = 0.0  # Overall hotness score
    hourly_velocity: float = 0.0  # Mentions per hour
    influential_mentions: int = 0  # Mentions from high-follower accounts
    earliest_mention: Optional[datetime] = None
    latest_mention: Optional[datetime] = None
    raw_signals: List[SocialSignal] = field(default_factory=list)


class HackerNewsMonitor:
    """Monitor Hacker News for AI paper discussions."""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA_URL = "https://hn.algolia.com/api/v1"

    def __init__(self):
        self.processed_stories: Set[int] = set()

    async def search_papers(self, query: str = "arxiv", hours: int = 24) -> List[SocialSignal]:
        """
        Search Hacker News for arxiv paper mentions.

        Args:
            query: Search query
            hours: Time window in hours

        Returns:
            List of social signals
        """
        signals = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search for stories mentioning arxiv
                url = f"{self.ALGOLIA_URL}/search"
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{int((datetime.now() - timedelta(hours=hours)).timestamp())}",
                    "hitsPerPage": 50
                }

                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                for hit in data.get("hits", []):
                    story_id = hit.get("objectID")
                    if story_id in self.processed_stories:
                        continue

                    title = hit.get("title", "")
                    url = hit.get("url", "")
                    points = hit.get("points", 0)
                    num_comments = hit.get("num_comments", 0)

                    # Extract arxiv ID
                    arxiv_id = self._extract_arxiv_id(title + " " + url)

                    if arxiv_id or "arxiv" in title.lower():
                        signal = SocialSignal(
                            platform="hackernews",
                            arxiv_id=arxiv_id,
                            paper_title=title,
                            mention_count=1,
                            engagement_score=points + num_comments * 2,
                            discussion_quality=min(1.0, num_comments / 50),
                            key_discussions=[hit.get("story_text", "")[:500]] if hit.get("story_text") else [],
                            first_seen=datetime.fromtimestamp(hit.get("created_at_i", 0)),
                            last_seen=datetime.now()
                        )
                        signals.append(signal)
                        self.processed_stories.add(int(story_id))

        except Exception as e:
            logger.warning(f"Failed to fetch Hacker News data: {e}")

        return signals

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        """Extract arxiv ID from text."""
        # Match patterns like arxiv:2301.12345, arxiv.org/abs/2301.12345
        patterns = [
            r'arxiv[\.:]\s*(\d{4}\.\d{4,5})',
            r'arxiv\.org/abs/(\d{4}\.\d{4,5})',
            r'arxiv\.org/pdf/(\d{4}\.\d{4,5})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


class RedditMonitor:
    """Monitor Reddit for AI paper discussions."""

    def __init__(self):
        self.base_url = "https://www.reddit.com"
        self.subreddits = [
            "MachineLearning",
            "artificial",
            "LocalLLaMA",
            "singularity",
            "OpenAI",
        ]

    async def search_papers(self, hours: int = 24) -> List[SocialSignal]:
        """
        Search Reddit for arxiv paper discussions.

        Note: Reddit API requires authentication for better access.
        This is a simplified implementation using public endpoints.
        """
        signals = []

        # Reddit API requires OAuth, so this is a placeholder
        # In production, you'd use praw or similar with API credentials
        logger.debug("Reddit monitoring requires API credentials (not implemented)")

        return signals


class TwitterXMonitor:
    """
    Monitor Twitter/X for AI paper mentions.

    Note: Twitter API v2 requires paid access.
    This is a placeholder for the implementation.
    """

    def __init__(self, bearer_token: Optional[str] = None):
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"

    async def search_papers(self, query: str = "arxiv OR arxiv.org", hours: int = 24) -> List[SocialSignal]:
        """
        Search Twitter for arxiv paper mentions.

        Requires Twitter API v2 access (paid tier).
        """
        signals = []

        if not self.bearer_token:
            logger.debug("Twitter API token not configured")
            return signals

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {self.bearer_token}"}

                # Search recent tweets
                url = f"{self.base_url}/tweets/search/recent"
                params = {
                    "query": f"({query}) -is:retweet lang:en",
                    "max_results": 100,
                    "tweet.fields": "created_at,public_metrics,author_id",
                    "expansions": "author_id"
                }

                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    # Process tweets and extract arxiv mentions
                    for tweet in data.get("data", []):
                        text = tweet.get("text", "")
                        arxiv_id = self._extract_arxiv_id(text)

                        if arxiv_id:
                            metrics = tweet.get("public_metrics", {})
                            engagement = (
                                metrics.get("like_count", 0) +
                                metrics.get("retweet_count", 0) * 2 +
                                metrics.get("reply_count", 0) * 3
                            )

                            signal = SocialSignal(
                                platform="twitter",
                                arxiv_id=arxiv_id,
                                paper_title=text[:100],
                                mention_count=1,
                                engagement_score=engagement,
                                first_seen=datetime.fromisoformat(tweet.get("created_at", "").replace("Z", "+00:00")),
                                last_seen=datetime.now()
                            )
                            signals.append(signal)
                else:
                    logger.warning(f"Twitter API error: {response.status_code}")

        except Exception as e:
            logger.warning(f"Failed to fetch Twitter data: {e}")

        return signals

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        """Extract arxiv ID from tweet text."""
        patterns = [
            r'arxiv[\.:]\s*(\d{4}\.\d{4,5})',
            r'arxiv\.org/abs/(\d{4}\.\d{4,5})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


class SocialMediaAggregator:
    """
    Aggregate social media signals from multiple platforms.
    """

    def __init__(self, twitter_token: Optional[str] = None):
        self.hackernews = HackerNewsMonitor()
        self.reddit = RedditMonitor()
        self.twitter = TwitterXMonitor(twitter_token)

    async def collect_hot_papers(self, hours: int = 24) -> Dict[str, HotPaperMetrics]:
        """
        Collect and aggregate hot papers from all platforms.

        Args:
            hours: Time window in hours

        Returns:
            Dictionary mapping arxiv_id to HotPaperMetrics
        """
        all_signals = []

        # Collect from all platforms concurrently
        tasks = [
            self.hackernews.search_papers(hours=hours),
            self.reddit.search_papers(hours=hours),
            self.twitter.search_papers(hours=hours),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_signals.extend(result)
            else:
                logger.warning(f"Platform monitoring failed: {result}")

        # Aggregate by arxiv_id
        aggregated: Dict[str, HotPaperMetrics] = {}

        for signal in all_signals:
            arxiv_id = signal.arxiv_id
            if not arxiv_id:
                continue

            if arxiv_id not in aggregated:
                aggregated[arxiv_id] = HotPaperMetrics(
                    arxiv_id=arxiv_id,
                    paper_title=signal.paper_title
                )

            metrics = aggregated[arxiv_id]
            metrics.platforms.add(signal.platform)
            metrics.total_mentions += signal.mention_count
            metrics.total_engagement += signal.engagement_score
            metrics.discussion_quality = max(metrics.discussion_quality, signal.discussion_quality)
            metrics.raw_signals.append(signal)

            # Track time window
            if metrics.earliest_mention is None or signal.first_seen < metrics.earliest_mention:
                metrics.earliest_mention = signal.first_seen
            if metrics.latest_mention is None or signal.last_seen > metrics.latest_mention:
                metrics.latest_mention = signal.last_seen

        # Calculate derived metrics
        for arxiv_id, metrics in aggregated.items():
            # Trending score calculation
            platform_bonus = len(metrics.platforms) * 0.1
            engagement_normalized = min(1.0, metrics.total_engagement / 100)
            mention_normalized = min(1.0, metrics.total_mentions / 20)

            metrics.trending_score = (
                0.4 * engagement_normalized +
                0.3 * mention_normalized +
                0.2 * metrics.discussion_quality +
                0.1 * platform_bonus
            )

            # Calculate velocity (mentions per hour)
            if metrics.earliest_mention and metrics.latest_mention:
                time_span = (metrics.latest_mention - metrics.earliest_mention).total_seconds() / 3600
                if time_span > 0:
                    metrics.hourly_velocity = metrics.total_mentions / time_span

        return aggregated

    async def get_top_trending_papers(
        self,
        hours: int = 24,
        min_score: float = 0.3,
        limit: int = 10
    ) -> List[HotPaperMetrics]:
        """
        Get top trending papers based on social signals.

        Args:
            hours: Time window
            min_score: Minimum trending score threshold
            limit: Maximum number of results

        Returns:
            List of hot paper metrics, sorted by trending score
        """
        aggregated = await self.collect_hot_papers(hours)

        # Filter and sort
        hot_papers = [
            metrics for metrics in aggregated.values()
            if metrics.trending_score >= min_score
        ]

        hot_papers.sort(key=lambda x: x.trending_score, reverse=True)

        return hot_papers[:limit]


class SocialSignalIntegrator:
    """
    Integrate social signals into the paper selection process.
    """

    def __init__(self, aggregator: Optional[SocialMediaAggregator] = None):
        self.aggregator = aggregator or SocialMediaAggregator()
        self._cache: Dict[str, HotPaperMetrics] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)

    async def get_social_boost_score(self, arxiv_id: str) -> float:
        """
        Get social media boost score for a paper.

        Returns a score from 0 to 1 indicating social media attention.
        """
        # Check cache
        if self._cache_time and datetime.now() - self._cache_time < self._cache_ttl:
            if arxiv_id in self._cache:
                return self._cache[arxiv_id].trending_score

        # Refresh cache
        hot_papers = await self.aggregator.get_top_trending_papers(hours=48)
        self._cache = {p.arxiv_id: p for p in hot_papers}
        self._cache_time = datetime.now()

        if arxiv_id in self._cache:
            return self._cache[arxiv_id].trending_score

        return 0.0

    async def enhance_paper_scores(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enhance paper scores with social media signals.

        Args:
            papers: List of paper dictionaries with scores

        Returns:
            Papers with added social_signal_score
        """
        # Batch fetch social signals
        hot_papers = await self.aggregator.get_top_trending_papers(hours=48)
        hot_map = {p.arxiv_id: p for p in hot_papers}

        for paper in papers:
            arxiv_id = paper.get("arxiv_id")
            if arxiv_id and arxiv_id in hot_map:
                metrics = hot_map[arxiv_id]
                paper["social_signals"] = {
                    "trending_score": metrics.trending_score,
                    "platforms": list(metrics.platforms),
                    "total_mentions": metrics.total_mentions,
                    "total_engagement": metrics.total_engagement,
                    "discussion_quality": metrics.discussion_quality,
                    "is_trending": metrics.trending_score >= 0.5
                }
                # Boost community heat score
                paper["community_score"] = max(
                    paper.get("community_score", 0),
                    metrics.trending_score
                )
            else:
                paper["social_signals"] = {
                    "trending_score": 0.0,
                    "is_trending": False
                }

        return papers

    def get_recommendations_based_on_social(
        self,
        hot_papers: List[HotPaperMetrics],
        existing_selected: List[str]
    ) -> List[str]:
        """
        Get paper recommendations based purely on social signals.

        This can be used to include hot papers that might have been missed.
        """
        recommendations = []

        for metrics in hot_papers:
            if metrics.arxiv_id not in existing_selected:
                # High threshold for inclusion
                if metrics.trending_score >= 0.7 and len(metrics.platforms) >= 2:
                    recommendations.append(metrics.arxiv_id)

        return recommendations
