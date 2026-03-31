"""
Paper Fetcher Agent - 负责从 arxiv 获取 AI Agent 相关论文。
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from loguru import logger

from agents.base import BaseAgent, AgentContext, AgentRole, AgentConfig, register_agent
from tools.arxiv_api import ArxivClient, ArxivPaper
from tools.semantic_scholar import SemanticScholarClient
from tools.openalex import OpenAlexClient
from tools.papers_with_code import PapersWithCodeClient
from storage.hybrid_storage import storage
from storage.database import Paper
from config.settings import settings


@register_agent
class PaperFetcherAgent(BaseAgent):
    """
    论文获取 Agent

    职责：
    1. 每日从 arxiv 获取 AI Agent 相关论文
    2. 获取论文的引用数、影响力等元数据
    3. 将论文信息存储到数据库
    """

    name = "paper_fetcher"
    description = "从 arxiv 获取 AI Agent 相关论文"
    role = AgentRole.FETCHER

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        # 使用配置决定是否启用网页抓取模式
        self.arxiv_client = ArxivClient(
            use_web_scraping=settings.ARXIV_USE_WEB_SCRAPING,
            use_new_page=settings.ARXIV_USE_NEW_PAGE
        )
        self.s2_client = SemanticScholarClient()
        self.openalex_client = OpenAlexClient()
        self.pwc_client = PapersWithCodeClient()

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行论文获取流程

        Args:
            context: Agent 执行上下文

        Returns:
            获取结果，包含论文列表和统计信息
        """
        logger.info("开始获取 AI Agent 相关论文...")

        # 1. 从 arxiv 获取论文
        papers = await self.arxiv_client.fetch_daily_papers()
        logger.info(f"从 arxiv 获取到 {len(papers)} 篇论文")

        # 2. 获取论文元数据（引用数、影响力等）
        enriched_papers = await self._enrich_paper_metadata(papers)

        # 3. 存储到数据库
        saved_count = await self._save_papers(enriched_papers)

        # 4. 更新上下文
        context.set("fetched_papers", [p["arxiv_id"] for p in enriched_papers])
        context.set("fetch_count", len(enriched_papers))

        return {
            "total_fetched": len(papers),
            "enriched": len(enriched_papers),
            "saved": saved_count,
            "paper_ids": [p["arxiv_id"] for p in enriched_papers[:10]],  # 前10个ID
        }

    async def _enrich_paper_metadata(
        self,
        papers: List[ArxivPaper],
        batch_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取论文的额外元数据

        Args:
            papers: arxiv 论文列表
            batch_size: 批量处理大小

        Returns:
            增强后的论文数据列表
        """
        enriched = []
        arxiv_ids = [p.arxiv_id for p in papers]

        # 批量获取 Semantic Scholar 数据
        logger.info("正在获取引用数据...")
        s2_metrics = await self.s2_client.get_papers_batch(arxiv_ids)

        # 获取 Papers with Code 数据
        logger.info("正在获取社区热度数据...")

        for paper in papers:
            paper_data = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": json.dumps(paper.authors),
                "abstract": paper.abstract,
                "categories": json.dumps(paper.categories),
                "published_date": paper.published_date,
                "updated_date": paper.updated_date,
                "pdf_url": paper.pdf_url,
                "abs_url": paper.abs_url,
                "citation_count": 0,
                "influence_score": 0.0,
                "community_score": 0.0,
            }

            # Semantic Scholar 数据
            if paper.arxiv_id in s2_metrics:
                metrics = s2_metrics[paper.arxiv_id]
                paper_data["citation_count"] = metrics.citation_count

                # 计算影响力分数（基于引用数和影响引用数）
                if metrics.influential_citation_count > 0:
                    paper_data["influence_score"] = min(
                        metrics.influential_citation_count / 100, 1.0
                    )

            # Papers with Code 数据
            pwc_metrics = await self.pwc_client.search_paper_by_arxiv(paper.arxiv_id)
            if pwc_metrics:
                paper_data["community_score"] = self.pwc_client.calculate_community_heat_score(
                    pwc_metrics
                )

            enriched.append(paper_data)

            # 避免请求过快
            await asyncio.sleep(0.1)

        return enriched

    async def _save_papers(self, papers: List[Dict[str, Any]]) -> int:
        """
        将论文保存到数据库

        Args:
            papers: 论文数据列表

        Returns:
            成功保存的数量
        """
        saved = 0
        for paper_data in papers:
            try:
                result = await storage.save_paper(paper_data)
                if result.get("local") or result.get("remote"):
                    saved += 1
            except Exception as e:
                logger.warning(f"保存论文 {paper_data['arxiv_id']} 失败: {e}")

        return saved

    async def fetch_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        按日期范围获取论文

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            论文数据列表
        """
        days = (end_date - start_date).days
        papers = await self.arxiv_client.fetch_papers(
            max_results=days * 200,  # 每天最多200篇
            date_range_days=days
        )

        enriched = await self._enrich_paper_metadata(papers)
        await self._save_papers(enriched)

        return enriched


@register_agent
class SelectionAgent(BaseAgent):
    """
    论文筛选 Agent - 改进版

    职责：
    1. 使用动态权重体系（基于论文年龄）
    2. 结合 LLM 进行全文内容质量评估
    3. 分析作者历史工作质量
    4. 与已有工作进行对比分析
    5. 选出 Top N 论文
    """

    name = "selection"
    description = "使用多维度评估筛选高质量论文"
    role = AgentRole.SELECTOR

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self.llm_client = None
        self.paper_analyzer = None
        self.author_analyzer = None
        self.comparison_analyzer = None

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行论文筛选流程

        Args:
            context: Agent 执行上下文

        Returns:
            筛选结果，包含选中的论文列表
        """
        from tools.llm_client import get_llm_client
        from tools.paper_analyzer import PaperContentAnalyzer, PaperComparisonAnalyzer
        from tools.author_analyzer import PaperAuthorsAnalyzer
        from tools.social_monitor import SocialMediaAggregator, SocialSignalIntegrator
        from config.settings import settings

        self.llm_client = get_llm_client()

        # Initialize analyzers if enabled
        if settings.ENABLE_FULL_PDF_ANALYSIS:
            self.paper_analyzer = PaperContentAnalyzer(self.llm_client)
        if settings.ENABLE_AUTHOR_HISTORY_ANALYSIS:
            self.author_analyzer = PaperAuthorsAnalyzer(settings.SEMANTIC_SCHOLAR_API_KEY)
        if settings.ENABLE_PAPER_COMPARISON:
            self.comparison_analyzer = PaperComparisonAnalyzer(self.llm_client)

        # Initialize social media monitoring
        social_integrator = None
        social_aggregator = None  # 统一的 aggregator 变量
        wechat_integrator = None

        if settings.ENABLE_SOCIAL_MONITORING:
            if settings.SOCIAL_MEDIA_REGION == "china":
                # 国内平台监控
                from tools.social_monitor_cn import CNSocialMediaAggregator, CNSocialSignalIntegrator
                social_aggregator = CNSocialMediaAggregator(
                    xiaohongshu_cookie=settings.XIAOHONGSHU_COOKIE
                )
                social_integrator = CNSocialSignalIntegrator(social_aggregator)
                logger.info("使用国内社交媒体监控（知乎、掘金、CSDN、小红书、即刻）")
            else:
                # 国际平台监控
                from tools.social_monitor import SocialMediaAggregator, SocialSignalIntegrator
                social_aggregator = SocialMediaAggregator(settings.TWITTER_BEARER_TOKEN)
                social_integrator = SocialSignalIntegrator(social_aggregator)
                logger.info("使用国际社交媒体监控（Hacker News、Reddit、Twitter）")

        # 初始化微信公众号监控
        if settings.ENABLE_WECHAT_MONITORING:
            from tools.social_monitor_wechat import WechatArticleAggregator, WechatSignalIntegrator
            wechat_aggregator = WechatArticleAggregator(
                use_sogou=(settings.WECHAT_MONITOR_SOURCE == "sogou"),
                xinbang_key=settings.XINBANG_API_KEY if settings.WECHAT_MONITOR_SOURCE == "xinbang" else None
            )
            wechat_integrator = WechatSignalIntegrator(wechat_aggregator)
            logger.info("使用微信公众号监控")

        # 从上下文获取待筛选的论文
        paper_ids = context.get("fetched_papers", [])
        if not paper_ids:
            # 从数据库获取最近未处理的论文
            papers = await self._get_unprocessed_papers()
        else:
            papers = await self._get_papers_by_ids(paper_ids)

        logger.info(f"开始筛选 {len(papers)} 篇论文...")

        if not papers:
            return {
                "total_evaluated": 0,
                "selected_count": 0,
                "selected_papers": [],
            }

        # 阶段 0: 检查社交媒体热点（可能包含不在当前批次的热门论文）
        hot_paper_ids = []

        # 0a. 检查微信公众号热点
        if wechat_integrator:
            try:
                wechat_hot_ids = await wechat_integrator.get_wechat_only_recommendations(
                    min_score=0.5,
                    limit=10
                )
                hot_paper_ids.extend(wechat_hot_ids)
                logger.info(f"从微信公众号发现 {len(wechat_hot_ids)} 篇热点论文")
            except Exception as e:
                logger.warning(f"微信公众号热点检查失败: {e}")

        # 0b. 检查其他社交媒体热点
        if social_integrator and social_aggregator:
            hot_papers = await social_aggregator.get_top_trending_papers(hours=48, limit=20)
            social_hot_ids = [p.arxiv_id for p in hot_papers if p.trending_score >= 0.6]
            hot_paper_ids.extend(social_hot_ids)
            logger.info(f"发现 {len(social_hot_ids)} 篇其他社交媒体热点论文")

        # 去重并添加热点论文
        hot_paper_ids = list(set(hot_paper_ids))
        if hot_paper_ids:
            logger.info(f"总共发现 {len(hot_paper_ids)} 篇社交媒体热点论文")

            # 将热点论文加入候选列表（如果尚未包含）
            existing_ids = {p["arxiv_id"] for p in papers}
            for hot_id in hot_paper_ids:
                if hot_id not in existing_ids:
                    # 尝试从存储获取，或标记为待获取
                    hot_paper = await storage.get_paper_by_arxiv_id(hot_id)
                    if hot_paper:
                        papers.append({
                            "arxiv_id": hot_paper.get("arxiv_id"),
                            "title": hot_paper.get("title"),
                            "authors": hot_paper.get("authors"),
                            "abstract": hot_paper.get("abstract"),
                            "published_date": hot_paper.get("published_date"),
                            "citation_count": hot_paper.get("citation_count", 0),
                            "influence_score": hot_paper.get("influence_score", 0),
                            "community_score": hot_paper.get("community_score", 0),
                            "is_hot_on_social": True,
                        })
                        logger.info(f"添加社交媒体热点论文: {hot_id}")

        # 阶段 1: 粗筛 - 基于元数据快速过滤
        coarse_candidates = await self._coarse_filter(papers)
        logger.info(f"粗筛后剩余 {len(coarse_candidates)} 篇候选论文")

        # 阶段 2: 深度分析 - 全文内容分析
        analyzed_papers = await self._deep_analysis(coarse_candidates)

        # 阶段 3: 对比分析（与已有论文对比）
        if settings.ENABLE_PAPER_COMPARISON:
            analyzed_papers = await self._perform_comparison_analysis(analyzed_papers)

        # 阶段 4: 添加社交媒体信号
        if social_integrator:
            analyzed_papers = await social_integrator.enhance_paper_scores(analyzed_papers)
            logger.info("已添加社交媒体信号")

        # 阶段 4b: 添加微信公众号信号
        if wechat_integrator:
            try:
                analyzed_papers = await wechat_integrator.enhance_paper_scores(analyzed_papers)
                logger.info("已添加微信公众号信号")
            except Exception as e:
                logger.warning(f"微信公众号信号添加失败: {e}")

        # 阶段 5: 动态评分 - 基于论文年龄使用不同权重
        scored_papers = await self._dynamic_scoring(analyzed_papers)

        # 选出 Top N
        selected = self._select_top_papers(scored_papers, settings.DAILY_PAPER_COUNT)

        # 更新存储
        selected_ids = [p["arxiv_id"] for p in selected]
        await storage.mark_papers_selected(selected_ids)

        # 更新上下文
        context.set("selected_papers", selected)

        return {
            "total_evaluated": len(papers),
            "coarse_filtered": len(coarse_candidates),
            "deep_analyzed": len(analyzed_papers),
            "selected_count": len(selected),
            "selected_papers": selected,
        }

    async def _coarse_filter(self, papers: List[Dict]) -> List[Dict]:
        """
        粗筛：基于元数据快速过滤明显不合适的论文
        """
        candidates = []

        for paper in papers:
            # 跳过过于简短的摘要（可能是预印本占位符）
            abstract = paper.get("abstract", "")
            if len(abstract) < 100:
                logger.debug(f"Skipping {paper['arxiv_id']}: abstract too short")
                continue

            # 跳过明显非 Agent 相关的论文（简单关键词过滤）
            title = paper.get("title", "").lower()
            if not any(kw in title or kw in abstract.lower() for kw in [
                "agent", "multi-agent", "llm", "language model",
                "autonomous", "reasoning", "planning"
            ]):
                logger.debug(f"Skipping {paper['arxiv_id']}: not agent-related")
                continue

            candidates.append(paper)

        return candidates

    async def _deep_analysis(self, papers: List[Dict]) -> List[Dict]:
        """
        深度分析：PDF 全文内容分析 + 作者历史分析
        """
        from config.settings import settings

        analyzed = []

        for paper in papers:
            arxiv_id = paper["arxiv_id"]
            logger.info(f"深度分析论文: {arxiv_id}")

            paper_analysis = {
                "arxiv_id": arxiv_id,
                "title": paper.get("title"),
                "abstract": paper.get("abstract"),
                "authors": paper.get("authors"),
                "published_date": paper.get("published_date"),
                "citation_count": paper.get("citation_count", 0),
                "influence_score": paper.get("influence_score", 0),
                "community_score": paper.get("community_score", 0),
            }

            # 1. PDF 内容分析
            if settings.ENABLE_FULL_PDF_ANALYSIS and self.paper_analyzer:
                try:
                    content_result = await self.paper_analyzer.analyze_paper(arxiv_id, paper)
                    paper_analysis["content_analysis"] = {
                        "method_score": content_result.method_analysis.get("score", 0.5),
                        "experiment_score": content_result.experiment_analysis.get("score", 0.5),
                        "novelty_score": content_result.novelty_analysis.get("score", 0.5),
                        "overall_quality": content_result.overall_quality_score,
                        "method_details": content_result.method_analysis,
                        "experiment_details": content_result.experiment_analysis,
                        "novelty_details": content_result.novelty_analysis,
                        "has_error": content_result.error is not None,
                    }
                except Exception as e:
                    logger.warning(f"PDF analysis failed for {arxiv_id}: {e}")
                    paper_analysis["content_analysis"] = {
                        "method_score": 0.5,
                        "experiment_score": 0.5,
                        "novelty_score": 0.5,
                        "overall_quality": 0.5,
                        "has_error": True,
                    }
            else:
                # 回退到基于摘要的分析
                quality_score = await self._evaluate_content_quality_from_abstract(paper)
                paper_analysis["content_analysis"] = {
                    "method_score": quality_score,
                    "experiment_score": quality_score,
                    "novelty_score": quality_score,
                    "overall_quality": quality_score,
                    "is_abstract_only": True,
                }

            # 2. 作者历史分析
            if settings.ENABLE_AUTHOR_HISTORY_ANALYSIS and self.author_analyzer:
                try:
                    authors = paper.get("authors", [])
                    if isinstance(authors, str):
                        import json
                        authors = json.loads(authors)

                    author_result = await self.author_analyzer.analyze_paper_authors(authors)
                    paper_analysis["author_analysis"] = author_result
                except Exception as e:
                    logger.warning(f"Author analysis failed for {arxiv_id}: {e}")
                    paper_analysis["author_analysis"] = {
                        "overall_score": 0.5,
                        "author_count": len(authors) if isinstance(authors, list) else 0,
                    }
            else:
                paper_analysis["author_analysis"] = {
                    "overall_score": 0.5,
                    "author_count": 0,
                }

            analyzed.append(paper_analysis)

            # 避免请求过快
            await asyncio.sleep(0.5)

        return analyzed

    async def _perform_comparison_analysis(self, papers: List[Dict]) -> List[Dict]:
        """
        对比分析：与数据库中已有论文进行对比
        """
        # 获取数据库中已有的相关论文（最近30天）
        from datetime import datetime, timedelta

        existing_papers = await self._get_recent_existing_papers(days=30, limit=20)

        for paper in papers:
            arxiv_id = paper["arxiv_id"]

            try:
                comparison = await self.comparison_analyzer.compare_with_existing(
                    paper,
                    existing_papers
                )
                paper["comparison_analysis"] = comparison
            except Exception as e:
                logger.warning(f"Comparison analysis failed for {arxiv_id}: {e}")
                paper["comparison_analysis"] = {
                    "comparison_score": 0.5,
                    "is_significant_advance": True,
                }

            await asyncio.sleep(0.3)

        return papers

    async def _dynamic_scoring(self, papers: List[Dict]) -> List[Dict]:
        """
        动态评分：基于论文年龄使用不同权重
        """
        from datetime import datetime
        from config.settings import settings

        scored_papers = []

        for paper in papers:
            arxiv_id = paper["arxiv_id"]

            # 计算论文年龄（天数）
            published_date = paper.get("published_date")
            if published_date:
                if isinstance(published_date, str):
                    from dateutil import parser
                    published_date = parser.parse(published_date)
                paper_age_days = (datetime.now() - published_date).days
            else:
                paper_age_days = 0

            # 选择权重配置
            if paper_age_days <= settings.PAPER_AGE_THRESHOLD_NEW:
                weights = settings.SELECTION_WEIGHTS_NEW
                age_category = "new"
            else:
                weights = settings.SELECTION_WEIGHTS_MATURE
                age_category = "mature"

            # 获取各项指标分数
            content_analysis = paper.get("content_analysis", {})
            author_analysis = paper.get("author_analysis", {})
            comparison_analysis = paper.get("comparison_analysis", {})
            social_signals = paper.get("social_signals", {})

            # 计算各项指标
            scores = {
                "citations": self._normalize_citation(paper.get("citation_count", 0)),
                "author_history": author_analysis.get("overall_score", 0.5),
                "content_quality": content_analysis.get("overall_quality", 0.5),
                "community_heat": paper.get("community_score", 0),
                "novelty": content_analysis.get("novelty_score", 0.5),
                "social_signal": social_signals.get("trending_score", 0.0),
                "wechat_signal": paper.get("wechat_signals", {}).get("trending_score", 0.0),
            }

            # 对于成熟论文，添加引用质量分数
            if age_category == "mature":
                influence_score = paper.get("influence_score", 0)
                scores["citation_quality"] = influence_score

            # 应用对比分析结果调整 novelty 分数
            if comparison_analysis:
                comparison_score = comparison_analysis.get("comparison_score", 0.5)
                is_significant = comparison_analysis.get("is_significant_advance", True)
                if not is_significant:
                    scores["novelty"] *= 0.7  # 降低非真正创新的论文的 novelty 分
                else:
                    scores["novelty"] = (scores["novelty"] + comparison_score) / 2

            # 社交媒体热点论文给予额外 boost
            social_signal_key = "social_signals" if "social_signals" in paper else "cn_social_signals"
            social_data = paper.get(social_signal_key, {})
            wechat_data = paper.get("wechat_signals", {})

            # 其他社交媒体 boost
            if paper.get("is_hot_on_social") or social_data.get("is_trending") or social_data.get("is_trending_cn"):
                social_boost = scores.get("social_signal", 0) * settings.SOCIAL_SIGNAL_WEIGHT
                # 如果社交媒体热度很高，显著提升总分
                if scores.get("social_signal", 0) >= settings.MIN_SOCIAL_SCORE_FOR_BOOST:
                    logger.info(f"论文 {arxiv_id} 获得社交媒体热点 boost: +{social_boost:.3f}")
                    scores["social_boost"] = social_boost

            # 微信公众号 boost
            if wechat_data.get("is_hot_on_wechat"):
                wechat_boost = scores.get("wechat_signal", 0) * settings.WECHAT_SIGNAL_WEIGHT
                if scores.get("wechat_signal", 0) >= 0.5:  # 微信公众号热度阈值
                    logger.info(f"论文 {arxiv_id} 获得微信公众号热点 boost: +{wechat_boost:.3f}")
                    scores["wechat_boost"] = wechat_boost

            # 计算加权总分
            total_score = 0.0
            for key, weight in weights.items():
                if key in scores:
                    total_score += weight * scores[key]

            # 添加社交媒体 boost（额外加分，不占用权重）
            if "social_boost" in scores:
                total_score += scores["social_boost"]
            if "wechat_boost" in scores:
                total_score += scores["wechat_boost"]
            total_score = min(total_score, 1.0)  # 上限 1.0

            paper["scores"] = scores
            paper["total_score"] = round(total_score, 3)
            paper["age_category"] = age_category
            paper["age_days"] = paper_age_days

            scored_papers.append(paper)

            logger.info(
                f"论文 {arxiv_id} 评分: {total_score:.3f} "
                f"(类别: {age_category}, 内容: {scores['content_quality']:.2f}, "
                f"作者: {scores['author_history']:.2f}, 新颖性: {scores['novelty']:.2f}, "
                f"社交: {scores['social_signal']:.2f}, 微信: {scores['wechat_signal']:.2f})"
            )

        return scored_papers

    async def _get_recent_existing_papers(self, days: int = 30, limit: int = 20) -> List[Dict]:
        """获取数据库中最近已存在的论文"""
        from datetime import datetime, timedelta

        # 这里简化处理，实际应从数据库查询
        # 返回空列表表示没有对比数据
        return []

    async def _get_unprocessed_papers(self, limit: int = 100) -> List[Dict]:
        """获取未处理的论文"""
        return await storage.get_unprocessed_papers(limit)

    async def _get_papers_by_ids(self, arxiv_ids: List[str]) -> List[Dict]:
        """根据 ID 获取论文"""
        papers = []
        for aid in arxiv_ids:
            paper = await storage.get_paper_by_arxiv_id(aid)
            if paper:
                papers.append(paper)
        return papers

    def _normalize_citation(self, citation_count: int, max_citations: int = 100) -> float:
        """归一化引用数"""
        import math
        return min(math.log10(citation_count + 1) / math.log10(max_citations + 1), 1.0)

    async def _evaluate_content_quality_from_abstract(self, paper: Dict) -> float:
        """使用 LLM 基于摘要评估内容质量（回退方案）"""
        from config.prompts import load_prompt

        prompt = load_prompt("selection")

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
请评估以下论文：

标题：{paper.get('title')}
摘要：{paper.get('abstract')[:1000] if paper.get('abstract') else ''}

请返回JSON格式的评估结果。
"""}
        ]

        try:
            result = await self.llm_client.generate_json(
                messages=messages,
                model=settings.MODEL_SELECTION,
                temperature=0.3
            )

            if "total_score" in result:
                return float(result["total_score"])
            elif "scores" in result:
                return float(result["scores"].get("innovation", 0.5))

        except Exception as e:
            logger.warning(f"LLM 评估失败: {e}")

        return 0.5  # 默认分数

    def _select_top_papers(
        self,
        papers: List[Dict],
        n: int
    ) -> List[Dict]:
        """选出 Top N 论文"""
        sorted_papers = sorted(
            papers,
            key=lambda x: x.get("total_score", 0),
            reverse=True
        )
        return sorted_papers[:n]


@register_agent
class SummaryAgent(BaseAgent):
    """
    内容生成 Agent

    职责：
    1. 为选中论文生成结构化摘要
    2. 生成核心贡献、推荐理由等
    3. 准备各平台适配的内容
    """

    name = "summary"
    description = "生成论文摘要和推荐内容"
    role = AgentRole.SUMMARIZER

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self.llm_client = None

    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行内容生成流程

        Args:
            context: Agent 执行上下文

        Returns:
            生成的内容
        """
        from tools.llm_client import get_llm_client

        self.llm_client = get_llm_client()

        # 获取选中的论文
        selected_papers = context.get("selected_papers", [])
        if not selected_papers:
            logger.warning("没有选中论文，跳过内容生成")
            return {"summaries": []}

        logger.info(f"开始为 {len(selected_papers)} 篇论文生成内容...")

        summaries = []
        for paper in selected_papers:
            summary = await self._generate_summary(paper)
            summaries.append({
                "paper": paper,
                "summary": summary
            })

        # 更新上下文
        context.set("summaries", summaries)

        return {
            "summaries": summaries,
            "count": len(summaries)
        }

    async def _generate_summary(self, paper: Dict) -> Dict[str, Any]:
        """为单篇论文生成摘要"""
        from config.prompts import load_prompt
        from config.settings import settings

        prompt = load_prompt("summary")

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"""
请为以下论文生成结构化摘要：

标题：{paper.get('title')}
作者：{paper.get('authors')}
摘要：{paper.get('abstract')}
arxiv ID: {paper.get('arxiv_id')}
PDF: {paper.get('pdf_url')}

请返回JSON格式的结果。
"""}
        ]

        try:
            result = await self.llm_client.generate_json(
                messages=messages,
                model=settings.MODEL_SUMMARY,
                temperature=0.5,
                max_tokens=2048
            )
            return result
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return {"error": str(e)}


# 便捷函数
def load_prompt(name: str) -> str:
    """加载提示词模板"""
    from pathlib import Path
    prompt_file = Path(__file__).parent.parent / "config" / "prompts" / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""