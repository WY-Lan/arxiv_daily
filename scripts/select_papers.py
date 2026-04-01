"""
论文筛选脚本
"""
import asyncio
import json
import sys
sys.path.insert(0, '/Users/wuyang.lan/Downloads/arxiv_daily')

from tools.arxiv_api import ArxivClient
from tools.llm_client import get_llm_client
from config.settings import settings
from config.prompts import load_prompt
from loguru import logger
from datetime import datetime


async def fetch_and_select():
    # 1. 获取论文
    client = ArxivClient(use_web_scraping=True, use_new_page=False)
    papers = await client.fetch_papers_via_web_scraping(use_new_page=False)

    # 筛选 26、27 号的论文
    target_dates = [datetime(2026, 3, 26), datetime(2026, 3, 27)]
    filtered = [p for p in papers if p.published_date.date() in [d.date() for d in target_dates]]

    print(f"\n获取到 {len(filtered)} 篇论文")

    # 2. 使用 LLM 筛选
    llm_client = get_llm_client()
    selection_prompt = load_prompt('selection')

    scored = []
    for paper in filtered[:10]:  # 先处理前10篇
        try:
            user_content = f"""
请评估以下 AI Agent 相关论文，返回 JSON 格式的评分结果：

标题：{paper.title}
摘要：{paper.abstract[:800]}
arxiv ID：{paper.arxiv_id}

请返回包含以下字段的 JSON（分数范围0-1）：
- relevance_score: 与AI Agent的相关性
- quality_score: 论文质量
- novelty_score: 创新性
- total_score: 综合评分
- recommend_reason: 推荐理由（一句话）
"""

            messages = [
                {'role': 'system', 'content': selection_prompt},
                {'role': 'user', 'content': user_content}
            ]

            result = await llm_client.generate_json(
                messages=messages,
                model=settings.MODEL_SELECTION,
                temperature=0.3
            )

            total_score = result.get('total_score', 0.5)
            logger.info(f'{paper.arxiv_id} score: {total_score}')

            scored.append({
                'arxiv_id': paper.arxiv_id,
                'title': paper.title,
                'abstract': paper.abstract,
                'authors': paper.authors,
                'published_date': paper.published_date,
                'pdf_url': paper.pdf_url,
                'total_score': total_score,
                'llm_scores': result
            })

        except Exception as e:
            logger.warning(f'LLM eval failed for {paper.arxiv_id}: {e}')
            scored.append({
                'arxiv_id': paper.arxiv_id,
                'title': paper.title,
                'abstract': paper.abstract,
                'authors': paper.authors,
                'published_date': paper.published_date,
                'pdf_url': paper.pdf_url,
                'total_score': 0.3,
                'llm_scores': {}
            })

        await asyncio.sleep(0.3)

    # 3. 排序并选出 Top 5
    scored.sort(key=lambda x: x['total_score'], reverse=True)
    selected = scored[:5]

    print("\n=== 篮选结果 (Top 5) ===")
    for i, p in enumerate(selected, 1):
        print(f"\n{i}. [{p['arxiv_id']}] {p['title']}")
        print(f"   评分: {p['total_score']:.2f}")
        reason = p['llm_scores'].get('recommend_reason', 'N/A')
        print(f"   推荐理由: {reason}")

    return selected


if __name__ == "__main__":
    selected = asyncio.run(fetch_and_select())
    # 保存结果
    with open('/Users/wuyang.lan/Downloads/arxiv_daily/storage/selected_papers.json', 'w') as f:
        json.dump(selected, f, ensure_ascii=False, indent=2, default=str)
    print("\n结果已保存到 storage/selected_papers.json")