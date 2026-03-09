"""
国内社交媒体热点论文监控工具。

针对国内部署环境（阿里云 ECS 等），监控国内社交媒体平台的 AI 论文讨论：
- 知乎热榜/搜索
- 掘金社区
- CSDN
- 即刻 App
- 小红书
- 微博

由于国内平台大多需要登录或反爬策略，这里提供多种实现方式。
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict
from urllib.parse import quote

import httpx
from loguru import logger


@dataclass
class CNSocialSignal:
    """国内社交媒体信号。"""
    platform: str  # zhihu, juejin, csdn, jike, xiaohongshu, weibo
    arxiv_id: Optional[str]
    paper_title: str
    mention_count: int = 0
    engagement_score: float = 0.0  # 点赞、收藏、评论等
    sentiment_score: float = 0.0  # -1 to 1
    discussion_quality: float = 0.0  # 0 to 1
    key_discussions: List[str] = field(default_factory=list)
    url: str = ""  # 原帖链接
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)


@dataclass
class CNHotPaperMetrics:
    """国内社交媒体聚合指标。"""
    arxiv_id: str
    paper_title: str
    total_mentions: int = 0
    total_engagement: float = 0.0
    platforms: Set[str] = field(default_factory=set)
    sentiment_average: float = 0.0
    discussion_quality: float = 0.0
    trending_score: float = 0.0
    earliest_mention: Optional[datetime] = None
    latest_mention: Optional[datetime] = None
    raw_signals: List[CNSocialSignal] = field(default_factory=list)


class ZhihuMonitor:
    """
    知乎监控 - AI 论文相关讨论。

    知乎反爬较严，建议：
    1. 使用官方 API（需要申请）
    2. 使用 RSS 源
    3. 搜索热榜话题
    """

    def __init__(self):
        self.base_url = "https://www.zhihu.com"
        self.session = None

    async def search_papers(self, hours: int = 24) -> List[CNSocialSignal]:
        """
        搜索知乎上与 arxiv/AI 论文相关的内容。

        注意：知乎需要登录，这里使用简化的热榜监控。
        """
        signals = []

        try:
            # 获取知乎热榜
            hot_list = await self._get_hot_list()

            for item in hot_list:
                title = item.get("title", "")
                url = item.get("url", "")

                # 检查是否与 AI/论文相关
                if self._is_ai_paper_related(title):
                    arxiv_id = self._extract_arxiv_id(title)

                    signal = CNSocialSignal(
                        platform="zhihu",
                        arxiv_id=arxiv_id,
                        paper_title=title,
                        mention_count=item.get("metrics", 0) // 10000,  # 热度估算
                        engagement_score=item.get("metrics", 0) / 1000000,
                        discussion_quality=0.7,  # 知乎讨论质量一般较高
                        url=url,
                        first_seen=datetime.now(),
                        last_seen=datetime.now()
                    )
                    signals.append(signal)

        except Exception as e:
            logger.warning(f"知乎监控失败: {e}")

        return signals

    async def _get_hot_list(self) -> List[Dict]:
        """获取知乎热榜（简化版，实际可能需要登录）。"""
        # 知乎热榜 API（可能随时变更）
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.zhihu.com/hot"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
        except Exception as e:
            logger.debug(f"获取知乎热榜失败: {e}")

        return []

    def _is_ai_paper_related(self, text: str) -> bool:
        """检查文本是否与 AI 论文相关。"""
        keywords = [
            "arxiv", "论文", "AI", "人工智能", "大模型", "LLM",
            "ChatGPT", "GPT", "机器学习", "深度学习",
            "论文解读", "最新研究"
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        """从文本中提取 arxiv ID。"""
        patterns = [
            r'arxiv[\.:]\s*(\d{4}\.\d{4,5})',
            r'arxiv\.org/abs/(\d{4}\.\d{4,5})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


class JuejinMonitor:
    """
    掘金社区监控 - 开发者社区中的 AI 论文讨论。

    掘金有较好的开放 API。
    """

    def __init__(self):
        self.base_url = "https://api.juejin.cn"

    async def search_papers(self, hours: int = 24) -> List[CNSocialSignal]:
        """搜索掘金上的 AI 论文相关内容。"""
        signals = []

        try:
            # 搜索 AI/论文相关文章
            search_terms = ["arxiv", "AI论文", "大模型论文", "机器学习论文"]

            for term in search_terms:
                articles = await self._search_articles(term)

                for article in articles:
                    title = article.get("article_info", {}).get("title", "")
                    arxiv_id = self._extract_arxiv_id(title)

                    if arxiv_id or self._is_paper_related(title):
                        views = article.get("article_info", {}).get("view_count", 0)
                        likes = article.get("article_info", {}).get("digg_count", 0)
                        comments = article.get("article_info", {}).get("comment_count", 0)

                        signal = CNSocialSignal(
                            platform="juejin",
                            arxiv_id=arxiv_id,
                            paper_title=title,
                            mention_count=1,
                            engagement_score=views + likes * 10 + comments * 20,
                            discussion_quality=0.6 if comments > 10 else 0.4,
                            url=f"https://juejin.cn/post/{article.get('article_id', '')}",
                            first_seen=datetime.now(),
                            last_seen=datetime.now()
                        )
                        signals.append(signal)

                await asyncio.sleep(1)  # 避免请求过快

        except Exception as e:
            logger.warning(f"掘金监控失败: {e}")

        return signals

    async def _search_articles(self, keyword: str, limit: int = 20) -> List[Dict]:
        """搜索掘金文章。"""
        url = "https://api.juejin.cn/search_api/v1/search"

        payload = {
            "key_word": keyword,
            "search_type": 0,  # 文章
            "cursor": "0",
            "limit": limit
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
        except Exception as e:
            logger.debug(f"掘金搜索失败: {e}")

        return []

    def _is_paper_related(self, text: str) -> bool:
        """检查是否与论文相关。"""
        keywords = ["论文", "arxiv", "研究", "模型", "算法"]
        return any(kw in text for kw in keywords)

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        """提取 arxiv ID。"""
        patterns = [
            r'arxiv[\.:\s]*([a-z\-]*\d{4}\.\d{4,5})',
            r'arXiv[\.:\s]*([a-z\-]*\d{4}\.\d{4,5})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


class CSDNMonitor:
    """
    CSDN 博客监控。

    CSDN 有开放 API 可以搜索博客文章。
    """

    def __init__(self):
        self.base_url = "https://blog.csdn.net"

    async def search_papers(self, hours: int = 24) -> List[CNSocialSignal]:
        """搜索 CSDN 上的 AI 论文相关内容。"""
        signals = []

        try:
            # CSDN 热榜或搜索
            keywords = ["arxiv", "AI论文", "大模型"]

            for keyword in keywords:
                articles = await self._search_blogs(keyword)

                for article in articles:
                    title = article.get("title", "")
                    arxiv_id = self._extract_arxiv_id(title)

                    if arxiv_id or self._is_paper_related(title):
                        views = article.get("view_count", 0)

                        signal = CNSocialSignal(
                            platform="csdn",
                            arxiv_id=arxiv_id,
                            paper_title=title,
                            mention_count=1,
                            engagement_score=views,
                            discussion_quality=0.5,
                            url=article.get("url", ""),
                            first_seen=datetime.now(),
                            last_seen=datetime.now()
                        )
                        signals.append(signal)

                await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"CSDN监控失败: {e}")

        return signals

    async def _search_blogs(self, keyword: str) -> List[Dict]:
        """搜索 CSDN 博客。"""
        # CSDN API 可能需要登录，这里使用简化实现
        return []

    def _is_paper_related(self, text: str) -> bool:
        keywords = ["论文", "arxiv", "研究"]
        return any(kw in text.lower() for kw in keywords)

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        pattern = r'arxiv[\.:\s]*(\d{4}\.\d{4,5})'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None


class XiaoHongShuMonitor:
    """
    小红书监控 - AI 论文解读内容。

    小红书反爬严格，需要特殊处理：
    1. 使用搜索 API（需要登录）
    2. 监控特定话题标签
    3. 使用第三方数据服务
    """

    def __init__(self, cookie: Optional[str] = None):
        self.cookie = cookie
        self.base_url = "https://www.xiaohongshu.com"

    async def search_papers(self, hours: int = 24) -> List[CNSocialSignal]:
        """搜索小红书上的 AI 论文相关内容。"""
        signals = []

        if not self.cookie:
            logger.debug("小红书监控需要 cookie，跳过")
            return signals

        try:
            # 搜索关键词
            keywords = ["论文解读", "arxiv", "AI论文", "大模型论文"]

            for keyword in keywords:
                notes = await self._search_notes(keyword)

                for note in notes:
                    title = note.get("title", "")
                    desc = note.get("desc", "")
                    content = title + " " + desc

                    arxiv_id = self._extract_arxiv_id(content)

                    if arxiv_id or self._is_paper_related(content):
                        likes = note.get("likes", 0)
                        comments = note.get("comments", 0)
                        collects = note.get("collects", 0)

                        signal = CNSocialSignal(
                            platform="xiaohongshu",
                            arxiv_id=arxiv_id,
                            paper_title=title or desc[:50],
                            mention_count=1,
                            engagement_score=likes + collects * 2 + comments * 3,
                            discussion_quality=0.5 if comments > 5 else 0.3,
                            url=f"https://www.xiaohongshu.com/explore/{note.get('id', '')}",
                            first_seen=datetime.now(),
                            last_seen=datetime.now()
                        )
                        signals.append(signal)

                await asyncio.sleep(2)  # 避免请求过快

        except Exception as e:
            logger.warning(f"小红书监控失败: {e}")

        return signals

    async def _search_notes(self, keyword: str) -> List[Dict]:
        """搜索小红书笔记（需要登录）。"""
        # 需要实现登录后的搜索逻辑
        # 小红书 API 加密且经常变更
        return []

    def _is_paper_related(self, text: str) -> bool:
        keywords = ["论文", "arxiv", "研究", "解读"]
        return any(kw in text.lower() for kw in keywords)

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        pattern = r'arxiv[\.:\s]*(\d{4}\.\d{4,5})'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None


class JikeMonitor:
    """
    即刻 App 监控 - 即刻上有很多 AI 相关圈子。

    即刻有开发者 API，但需要申请。
    """

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token
        self.base_url = "https://api.okjike.com"

    async def search_papers(self, hours: int = 24) -> List[CNSocialSignal]:
        """搜索即刻上的 AI 论文讨论。"""
        signals = []

        if not self.api_token:
            logger.debug("即刻监控需要 API token，跳过")
            return signals

        try:
            # 搜索特定话题
            topics = ["AI大模型", "论文解读", "机器学习"]

            for topic in topics:
                posts = await self._search_posts(topic)

                for post in posts:
                    content = post.get("content", "")
                    arxiv_id = self._extract_arxiv_id(content)

                    if arxiv_id or self._is_paper_related(content):
                        likes = post.get("likeCount", 0)
                        comments = post.get("commentCount", 0)
                        reposts = post.get("repostCount", 0)

                        signal = CNSocialSignal(
                            platform="jike",
                            arxiv_id=arxiv_id,
                            paper_title=content[:50],
                            mention_count=1,
                            engagement_score=likes + reposts * 3 + comments * 5,
                            discussion_quality=0.6 if comments > 3 else 0.4,
                            url=post.get("url", ""),
                            first_seen=datetime.now(),
                            last_seen=datetime.now()
                        )
                        signals.append(signal)

        except Exception as e:
            logger.warning(f"即刻监控失败: {e}")

        return signals

    async def _search_posts(self, keyword: str) -> List[Dict]:
        """搜索即刻帖子（需要 API）。"""
        return []

    def _is_paper_related(self, text: str) -> bool:
        keywords = ["论文", "arxiv", "研究"]
        return any(kw in text.lower() for kw in keywords)

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        pattern = r'arxiv[\.:\s]*(\d{4}\.\d{4,5})'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None


class CNSocialMediaAggregator:
    """
    聚合国内社交媒体信号。
    """

    def __init__(
        self,
        xiaohongshu_cookie: Optional[str] = None,
        jike_token: Optional[str] = None
    ):
        self.zhihu = ZhihuMonitor()
        self.juejin = JuejinMonitor()
        self.csdn = CSDNMonitor()
        self.xiaohongshu = XiaoHongShuMonitor(xiaohongshu_cookie)
        self.jike = JikeMonitor(jike_token)

    async def collect_hot_papers(self, hours: int = 24) -> Dict[str, CNHotPaperMetrics]:
        """
        从国内平台收集热点论文。

        Args:
            hours: 时间窗口

        Returns:
            按 arxiv_id 聚合的热点指标
        """
        all_signals = []

        # 并发收集各平台数据
        tasks = [
            self.zhihu.search_papers(hours),
            self.juejin.search_papers(hours),
            self.csdn.search_papers(hours),
            self.xiaohongshu.search_papers(hours),
            self.jike.search_papers(hours),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_signals.extend(result)
            else:
                logger.warning(f"平台监控失败: {result}")

        # 按 arxiv_id 聚合
        aggregated: Dict[str, CNHotPaperMetrics] = {}

        for signal in all_signals:
            arxiv_id = signal.arxiv_id
            if not arxiv_id:
                # 尝试从标题提取
                arxiv_id = self._extract_arxiv_id_from_text(signal.paper_title)

            if not arxiv_id:
                continue

            if arxiv_id not in aggregated:
                aggregated[arxiv_id] = CNHotPaperMetrics(
                    arxiv_id=arxiv_id,
                    paper_title=signal.paper_title
                )

            metrics = aggregated[arxiv_id]
            metrics.platforms.add(signal.platform)
            metrics.total_mentions += signal.mention_count
            metrics.total_engagement += signal.engagement_score
            metrics.discussion_quality = max(metrics.discussion_quality, signal.discussion_quality)
            metrics.raw_signals.append(signal)

            # 时间窗口
            if metrics.earliest_mention is None or signal.first_seen < metrics.earliest_mention:
                metrics.earliest_mention = signal.first_seen
            if metrics.latest_mention is None or signal.last_seen > metrics.latest_mention:
                metrics.latest_mention = signal.last_seen

        # 计算 trending score
        for arxiv_id, metrics in aggregated.items():
            platform_bonus = len(metrics.platforms) * 0.15
            engagement_normalized = min(1.0, metrics.total_engagement / 10000)
            mention_normalized = min(1.0, metrics.total_mentions / 10)

            metrics.trending_score = (
                0.35 * engagement_normalized +
                0.30 * mention_normalized +
                0.25 * metrics.discussion_quality +
                0.10 * platform_bonus
            )

        return aggregated

    async def get_top_trending_papers(
        self,
        hours: int = 24,
        min_score: float = 0.3,
        limit: int = 10
    ) -> List[CNHotPaperMetrics]:
        """获取国内 trending 论文。"""
        aggregated = await self.collect_hot_papers(hours)

        hot_papers = [
            metrics for metrics in aggregated.values()
            if metrics.trending_score >= min_score
        ]

        hot_papers.sort(key=lambda x: x.trending_score, reverse=True)
        return hot_papers[:limit]

    def _extract_arxiv_id_from_text(self, text: str) -> Optional[str]:
        """从文本中提取 arxiv ID。"""
        pattern = r'arxiv[\.:\s]*(\d{4}\.\d{4,5})'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None


class CNSocialSignalIntegrator:
    """
    将国内社交媒体信号整合进论文筛选流程。
    """

    def __init__(self, aggregator: Optional[CNSocialMediaAggregator] = None):
        self.aggregator = aggregator or CNSocialMediaAggregator()
        self._cache: Dict[str, CNHotPaperMetrics] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)

    async def get_social_boost_score(self, arxiv_id: str) -> float:
        """获取国内社交媒体 boost 分数。"""
        if self._cache_time and datetime.now() - self._cache_time < self._cache_ttl:
            if arxiv_id in self._cache:
                return self._cache[arxiv_id].trending_score

        # 刷新缓存
        hot_papers = await self.aggregator.get_top_trending_papers(hours=48)
        self._cache = {p.arxiv_id: p for p in hot_papers}
        self._cache_time = datetime.now()

        if arxiv_id in self._cache:
            return self._cache[arxiv_id].trending_score

        return 0.0

    async def enhance_paper_scores(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """增强论文分数（国内社交媒体版本）。"""
        hot_papers = await self.aggregator.get_top_trending_papers(hours=48)
        hot_map = {p.arxiv_id: p for p in hot_papers}

        for paper in papers:
            arxiv_id = paper.get("arxiv_id")
            if arxiv_id and arxiv_id in hot_map:
                metrics = hot_map[arxiv_id]
                paper["cn_social_signals"] = {
                    "trending_score": metrics.trending_score,
                    "platforms": list(metrics.platforms),
                    "total_mentions": metrics.total_mentions,
                    "total_engagement": metrics.total_engagement,
                    "is_trending_cn": metrics.trending_score >= 0.5
                }
                # 提升社区热度分数
                paper["community_score"] = max(
                    paper.get("community_score", 0),
                    metrics.trending_score
                )
            else:
                paper["cn_social_signals"] = {
                    "trending_score": 0.0,
                    "is_trending_cn": False
                }

        return papers
