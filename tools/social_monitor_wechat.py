"""
微信公众号文章监控工具。

由于微信公众号没有官方开放API，本模块提供多种监控方式：
1. 搜狗微信搜索（免费，但反爬严格）
2. 新榜/清博等第三方数据服务（需付费）
3. 微信读书/搜一搜等间接渠道
4. 用户自定义数据源接入

推荐：对于小规模监控，使用搜狗微信搜索；对于大规模商业使用，建议使用新榜API。
"""
import asyncio
import hashlib
import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from urllib.parse import quote, urlencode

import httpx
from loguru import logger


@dataclass
class WechatArticle:
    """微信公众号文章。"""
    title: str
    url: str
    account_name: str  # 公众号名称
    account_id: Optional[str]  # 公众号ID
    publish_time: Optional[datetime]
    abstract: str
    read_count: Optional[int] = None  # 阅读量（通常无法获取准确数字）
    like_count: Optional[int] = None  # 点赞数
    arxiv_id: Optional[str] = None  # 提取的arxiv ID
    is_ai_related: bool = False
    raw_data: Dict = field(default_factory=dict)


@dataclass
class WechatSignal:
    """微信公众号社交信号。"""
    platform: str = "wechat"
    arxiv_id: Optional[str]
    paper_title: str
    articles: List[WechatArticle] = field(default_factory=list)
    mention_count: int = 0
    engagement_score: float = 0.0
    sentiment_score: float = 0.0
    discussion_quality: float = 0.0
    influential_accounts: List[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)


@dataclass
class WechatHotPaperMetrics:
    """微信公众号聚合指标。"""
    arxiv_id: str
    paper_title: str
    total_articles: int = 0
    total_accounts: int = 0
    unique_accounts: Set[str] = field(default_factory=set)
    total_engagement: float = 0.0
    discussion_quality: float = 0.0
    trending_score: float = 0.0
    earliest_article: Optional[datetime] = None
    latest_article: Optional[datetime] = None
    top_articles: List[WechatArticle] = field(default_factory=list)


class SogouWechatMonitor:
    """
    基于搜狗微信搜索的公众号文章监控。

    搜狗微信搜索 (weixin.sogou.com) 可以搜索到公众号文章，但有以下限制：
    1. 反爬严格，需要处理验证码
    2. 每天搜索次数有限制
    3. 文章阅读量等数据通常无法获取

    适用场景：小规模监控、个人使用
    """

    BASE_URL = "https://weixin.sogou.com"

    def __init__(self):
        self.session_cookies: Dict[str, str] = {}
        self.last_request_time: Optional[datetime] = None
        self.request_delay = 3.0  # 请求间隔（秒）
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头。"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://weixin.sogou.com/",
        }

    async def _rate_limit(self):
        """请求频率限制。"""
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.request_delay:
                await asyncio.sleep(self.request_delay - elapsed)
        self.last_request_time = datetime.now()

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        """从文本中提取arxiv ID。"""
        patterns = [
            r'arxiv[\.:\s]*(\d{4}\.\d{4,5})',
            r'arXiv[\.:\s]*(\d{4}\.\d{4,5})',
            r'arxiv\.org/abs/(\d{4}\.\d{4,5})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _is_ai_paper_related(self, text: str) -> bool:
        """检查是否与AI论文相关。"""
        keywords = [
            "arxiv", "论文", "AI", "人工智能", "大模型", "LLM",
            "机器学习", "深度学习", "论文解读", "研究",
            "GPT", "ChatGPT", "Transformer", "神经网络"
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    async def search_articles(
        self,
        keyword: str,
        days: int = 7,
        limit: int = 10
    ) -> List[WechatArticle]:
        """
        使用搜狗微信搜索公众号文章。

        Args:
            keyword: 搜索关键词
            days: 时间范围（天）
            limit: 最大结果数

        Returns:
            文章列表
        """
        articles = []

        try:
            await self._rate_limit()

            # 构建搜索URL
            search_url = f"{self.BASE_URL}/weixin"
            params = {
                "type": "2",  # 搜索文章
                "query": keyword,
                "page": "1",
            }

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    search_url,
                    params=params,
                    headers=self._get_headers(),
                    cookies=self.session_cookies
                )

                # 检查是否需要验证码
                if "请输入验证码" in response.text or "captcha" in response.text.lower():
                    logger.warning("搜狗微信搜索触发验证码，请手动访问 https://weixin.sogou.com 验证")
                    return articles

                # 解析搜索结果
                articles = self._parse_search_results(response.text, days)

                # 保存cookies
                self.session_cookies.update(dict(response.cookies))

        except Exception as e:
            logger.warning(f"搜狗微信搜索失败: {e}")

        return articles[:limit]

    def _parse_search_results(self, html: str, days: int) -> List[WechatArticle]:
        """解析搜索结果HTML。"""
        articles = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # 查找文章列表
            result_list = soup.find('ul', class_='news-list')
            if not result_list:
                return articles

            for item in result_list.find_all('li'):
                try:
                    # 标题
                    title_tag = item.find('h3')
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    # 链接
                    link_tag = item.find('a', href=True)
                    url = link_tag['href'] if link_tag else ""

                    # 公众号名称
                    account_tag = item.find('a', class_='account')
                    account_name = account_tag.get_text(strip=True) if account_tag else "未知"

                    # 摘要
                    abstract_tag = item.find('p', class_='txt-info')
                    abstract = abstract_tag.get_text(strip=True) if abstract_tag else ""

                    # 发布时间
                    time_tag = item.find('span', class_='s2')
                    publish_time = self._parse_time(time_tag.get_text(strip=True) if time_tag else "")

                    # 检查时间范围
                    if publish_time and (datetime.now() - publish_time).days > days:
                        continue

                    # 提取arxiv ID
                    arxiv_id = self._extract_arxiv_id(title + " " + abstract)

                    # 检查是否AI相关
                    is_ai = self._is_ai_paper_related(title + " " + abstract)

                    article = WechatArticle(
                        title=title,
                        url=url,
                        account_name=account_name,
                        account_id=None,
                        publish_time=publish_time,
                        abstract=abstract,
                        arxiv_id=arxiv_id,
                        is_ai_related=is_ai
                    )
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"解析文章失败: {e}")
                    continue

        except ImportError:
            logger.warning("BeautifulSoup4 未安装，无法解析搜狗搜索结果")
        except Exception as e:
            logger.warning(f"解析搜索结果失败: {e}")

        return articles

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """解析发布时间字符串。"""
        try:
            # 支持格式："1天前", "2小时前", "2024-01-15"
            if "天前" in time_str:
                days = int(re.search(r'(\d+)', time_str).group(1))
                return datetime.now() - timedelta(days=days)
            elif "小时前" in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                return datetime.now() - timedelta(hours=hours)
            elif "分钟前" in time_str:
                minutes = int(re.search(r'(\d+)', time_str).group(1))
                return datetime.now() - timedelta(minutes=minutes)
            else:
                return datetime.strptime(time_str, "%Y-%m-%d")
        except:
            return None


class XinbangMonitor:
    """
    新榜数据服务监控。

    新榜 (newrank.cn) 提供微信公众号数据API，需要付费订阅。
    适合商业级应用。

    文档：https://www.newrank.cn/public/info/document/myApi
    """

    BASE_URL = "https://api.newrank.cn/api"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search_articles(
        self,
        keyword: str,
        days: int = 7,
        limit: int = 10
    ) -> List[WechatArticle]:
        """
        使用新榜API搜索公众号文章。

        需要申请API权限并订阅服务。
        """
        if not self.api_key:
            logger.debug("新榜API Key未配置")
            return []

        articles = []

        try:
            url = f"{self.BASE_URL}/search/articles"
            params = {
                "key": self.api_key,
                "keyword": keyword,
                "days": days,
                "size": limit,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    for item in data.get("data", []):
                        article = WechatArticle(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            account_name=item.get("account_name", ""),
                            account_id=item.get("account_id"),
                            publish_time=datetime.fromisoformat(item.get("publish_time")) if item.get("publish_time") else None,
                            abstract=item.get("abstract", ""),
                            read_count=item.get("read_count"),
                            like_count=item.get("like_count"),
                            arxiv_id=self._extract_arxiv_id(item.get("title", "") + " " + item.get("abstract", "")),
                            is_ai_related=self._is_ai_paper_related(item.get("title", "")),
                            raw_data=item
                        )
                        articles.append(article)

        except Exception as e:
            logger.warning(f"新榜API调用失败: {e}")

        return articles

    def _extract_arxiv_id(self, text: str) -> Optional[str]:
        pattern = r'arxiv[\.:\s]*(\d{4}\.\d{4,5})'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None

    def _is_ai_paper_related(self, text: str) -> bool:
        keywords = ["arxiv", "论文", "AI", "大模型", "机器学习"]
        return any(kw in text.lower() for kw in keywords)


class CustomWechatDataSource:
    """
    自定义微信公众号数据源。

    允许用户接入自己的数据源，如：
    - 自建爬虫系统
    - 第三方数据服务
    - 人工录入数据
    """

    def __init__(self, data_callback=None):
        """
        Args:
            data_callback: 异步回调函数，接收keyword和days参数，返回WechatArticle列表
        """
        self.data_callback = data_callback

    async def search_articles(
        self,
        keyword: str,
        days: int = 7,
        limit: int = 10
    ) -> List[WechatArticle]:
        """调用自定义数据源。"""
        if not self.data_callback:
            return []

        try:
            return await self.data_callback(keyword, days, limit)
        except Exception as e:
            logger.warning(f"自定义数据源调用失败: {e}")
            return []


class WechatArticleAggregator:
    """
    聚合多个微信公众号数据源。
    """

    def __init__(
        self,
        use_sogou: bool = True,
        xinbang_key: Optional[str] = None,
        custom_source: Optional[CustomWechatDataSource] = None
    ):
        self.sources = []

        if use_sogou:
            self.sources.append(SogouWechatMonitor())

        if xinbang_key:
            self.sources.append(XinbangMonitor(xinbang_key))

        if custom_source:
            self.sources.append(custom_source)

    async def search_papers(self, hours: int = 24) -> List[WechatSignal]:
        """
        搜索微信公众号中关于AI论文的文章。

        Args:
            hours: 时间窗口（小时）

        Returns:
            按arxiv ID聚合的信号列表
        """
        all_articles = []
        days = hours // 24 + 1

        # 搜索关键词列表
        keywords = [
            "arxiv AI",
            "论文解读",
            "大模型论文",
            "机器学习论文",
            "AI最新研究",
        ]

        for source in self.sources:
            for keyword in keywords:
                try:
                    articles = await source.search_articles(keyword, days=days, limit=10)
                    all_articles.extend(articles)
                    await asyncio.sleep(2)  # 避免请求过快
                except Exception as e:
                    logger.warning(f"数据源搜索失败: {e}")

        # 按arxiv ID聚合
        return self._aggregate_by_paper(all_articles)

    def _aggregate_by_paper(self, articles: List[WechatArticle]) -> List[WechatSignal]:
        """按论文聚合文章。"""
        paper_articles: Dict[str, List[WechatArticle]] = {}

        for article in articles:
            arxiv_id = article.arxiv_id
            if not arxiv_id:
                # 尝试从标题提取
                arxiv_id = self._extract_arxiv_from_title(article.title)

            if not arxiv_id:
                continue

            if arxiv_id not in paper_articles:
                paper_articles[arxiv_id] = []
            paper_articles[arxiv_id].append(article)

        # 创建信号
        signals = []
        for arxiv_id, articles in paper_articles.items():
            signal = self._create_signal(arxiv_id, articles)
            signals.append(signal)

        return signals

    def _create_signal(self, arxiv_id: str, articles: List[WechatArticle]) -> WechatSignal:
        """创建社交信号。"""
        unique_accounts = set(a.account_name for a in articles)

        # 计算参与度（基于文章数量和账号影响力）
        engagement = len(articles) * 10 + len(unique_accounts) * 20

        # 评估讨论质量
        quality = self._assess_quality(articles)

        # 识别影响力账号
        influential = self._identify_influential_accounts(articles)

        signal = WechatSignal(
            arxiv_id=arxiv_id,
            paper_title=articles[0].title if articles else "",
            articles=articles,
            mention_count=len(articles),
            engagement_score=engagement,
            discussion_quality=quality,
            influential_accounts=influential,
            first_seen=min((a.publish_time for a in articles if a.publish_time), default=datetime.now()),
            last_seen=max((a.publish_time for a in articles if a.publish_time), default=datetime.now())
        )

        return signal

    def _assess_quality(self, articles: List[WechatArticle]) -> float:
        """评估讨论质量。"""
        if not articles:
            return 0.0

        # 基于文章数量和账号多样性评估
        unique_accounts = len(set(a.account_name for a in articles))
        article_count = len(articles)

        # 有多个不同账号讨论，质量较高
        if unique_accounts >= 3 and article_count >= 5:
            return 0.8
        elif unique_accounts >= 2 and article_count >= 3:
            return 0.6
        elif article_count >= 2:
            return 0.4
        else:
            return 0.3

    def _identify_influential_accounts(self, articles: List[WechatArticle]) -> List[str]:
        """识别影响力账号。"""
        # 知名的AI/技术公众号列表
        influential_list = {
            "机器之心", "量子位", "AI科技评论", "新智元",
            "PaperWeekly", "CVer", "深度学习自然语言处理",
            "李沐", "张俊林", "刘知远", "邱锡鹏"
        }

        found = []
        for article in articles:
            account = article.account_name
            if any(name in account for name in influential_list):
                found.append(account)

        return list(set(found))

    def _extract_arxiv_from_title(self, title: str) -> Optional[str]:
        """从标题提取arxiv ID。"""
        pattern = r'arxiv[\.:\s]*(\d{4}\.\d{4,5})'
        match = re.search(pattern, title, re.IGNORECASE)
        return match.group(1) if match else None


class WechatSignalIntegrator:
    """
    将微信公众号信号整合进论文筛选流程。
    """

    def __init__(self, aggregator: Optional[WechatArticleAggregator] = None):
        self.aggregator = aggregator or WechatArticleAggregator()
        self._cache: Dict[str, WechatHotPaperMetrics] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)

    async def get_wechat_boost_score(self, arxiv_id: str) -> float:
        """获取微信公众号boost分数。"""
        if self._cache_time and datetime.now() - self._cache_time < self._cache_ttl:
            if arxiv_id in self._cache:
                return self._cache[arxiv_id].trending_score

        # 刷新缓存
        await self._refresh_cache()

        if arxiv_id in self._cache:
            return self._cache[arxiv_id].trending_score

        return 0.0

    async def _refresh_cache(self):
        """刷新缓存。"""
        signals = await self.aggregator.search_papers(hours=48)

        # 转换为指标
        for signal in signals:
            if not signal.arxiv_id:
                continue

            metrics = WechatHotPaperMetrics(
                arxiv_id=signal.arxiv_id,
                paper_title=signal.paper_title,
                total_articles=signal.mention_count,
                total_accounts=len(signal.articles),
                unique_accounts=set(a.account_name for a in signal.articles),
                discussion_quality=signal.discussion_quality,
                top_articles=signal.articles[:5]
            )

            # 计算 trending score
            account_bonus = len(metrics.unique_accounts) * 0.1
            article_score = min(1.0, metrics.total_articles / 10)
            quality_score = metrics.discussion_quality

            # 如果有影响力账号提及，额外加分
            influence_bonus = len(signal.influential_accounts) * 0.1

            metrics.trending_score = (
                0.4 * article_score +
                0.3 * quality_score +
                0.2 * account_bonus +
                0.1 * influence_bonus
            )

            self._cache[signal.arxiv_id] = metrics

        self._cache_time = datetime.now()

    async def enhance_paper_scores(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """增强论文分数（微信公众号版本）。"""
        await self._refresh_cache()

        for paper in papers:
            arxiv_id = paper.get("arxiv_id")
            if arxiv_id and arxiv_id in self._cache:
                metrics = self._cache[arxiv_id]
                paper["wechat_signals"] = {
                    "trending_score": metrics.trending_score,
                    "article_count": metrics.total_articles,
                    "account_count": len(metrics.unique_accounts),
                    "discussion_quality": metrics.discussion_quality,
                    "influential_accounts": list(metrics.unique_accounts)[:5],
                    "is_hot_on_wechat": metrics.trending_score >= 0.5
                }
                # 提升社区热度
                paper["community_score"] = max(
                    paper.get("community_score", 0),
                    metrics.trending_score
                )
            else:
                paper["wechat_signals"] = {
                    "trending_score": 0.0,
                    "is_hot_on_wechat": False
                }

        return papers

    async def get_wechat_only_recommendations(
        self,
        min_score: float = 0.5,
        limit: int = 5
    ) -> List[str]:
        """
        获取仅在微信公众号上热门的论文推荐。

        用于发现可能被其他渠道忽略的热门论文。
        """
        await self._refresh_cache()

        hot_papers = [
            (arxiv_id, metrics)
            for arxiv_id, metrics in self._cache.items()
            if metrics.trending_score >= min_score
        ]

        hot_papers.sort(key=lambda x: x[1].trending_score, reverse=True)

        return [arxiv_id for arxiv_id, _ in hot_papers[:limit]]
