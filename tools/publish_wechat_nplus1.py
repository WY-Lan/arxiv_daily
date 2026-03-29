"""
Publish n+1 posts to WeChat Official Account:
- n detailed posts (one per paper with in-depth analysis)
- 1 summary post with links to all detailed posts

The number n is dynamic, determined by the selection results.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from loguru import logger
from tools.llm_client import BailianClient
from tools.pdf_screenshot import download_and_screenshot
from tools.wechat_publisher import WeChatMPClient, get_wechat_client
from config.prompts import load_prompt
from config.settings import settings


async def generate_single_paper_content(
    paper: dict,
    llm_client: BailianClient
) -> dict:
    """Generate detailed WeChat article content for a single paper."""
    # Load prompt template
    prompt_template = load_prompt("wechat_single_paper")

    # Prepare paper info
    authors = json.loads(paper['authors']) if isinstance(paper['authors'], str) else paper['authors']

    paper_info = {
        "title": paper['title'],
        "arxiv_id": paper['arxiv_id'],
        "authors": authors[:3] if authors else [],
        "abstract": paper.get('abstract', ''),
        "pdf_url": paper.get('pdf_url', ''),
        "abs_url": paper.get('abs_url', f"https://arxiv.org/abs/{paper['arxiv_id']}")
    }

    # Create full prompt
    prompt = f"""{prompt_template}

## 论文数据

请根据以下论文信息生成微信公众号深度解读文章：

{json.dumps(paper_info, ensure_ascii=False, indent=2)}
"""

    logger.info(f"Generating single-paper content for {paper['arxiv_id']}...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def generate_summary_content(
    papers: list[dict],
    llm_client: BailianClient
) -> dict:
    """Generate summary WeChat article with all papers."""
    # Build papers info
    papers_info = []
    for p in papers:
        authors = json.loads(p['authors']) if isinstance(p['authors'], str) else p['authors']
        papers_info.append({
            "title": p['title'],
            "arxiv_id": p['arxiv_id'],
            "authors": authors[:3] if authors else [],
            "summary": p.get('abstract', '')[:300]
        })

    # Create summary prompt
    prompt = f"""你是一位专业的微信公众号编辑，擅长撰写论文合集文章。

请根据以下 {len(papers)} 篇论文生成一篇合集文章。输出JSON格式，包含：
- title: 文章标题（30字以内）
- digest: 摘要（100字以内）
- content: HTML格式的正文内容

正文要求：
1. 开头简要介绍今日推荐主题
2. 每篇论文用简短的段落介绍（标题、核心贡献、应用价值）
3. 结尾引导关注

## 今日论文

{json.dumps(papers_info, ensure_ascii=False, indent=2)}
"""

    logger.info("Generating summary content...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def create_paper_cover(paper: dict) -> Optional[bytes]:
    """Create cover image for a single paper from arxiv PDF."""
    logger.info(f"Creating cover for {paper['arxiv_id']}...")

    try:
        # Download and screenshot PDF
        screenshot_path = await download_and_screenshot(
            pdf_url=paper.get('pdf_url', f"https://arxiv.org/pdf/{paper['arxiv_id']}.pdf"),
            arxiv_id=paper['arxiv_id']
        )

        if screenshot_path:
            # Read the image and convert to bytes
            from PIL import Image
            import io

            img = Image.open(screenshot_path)

            # Resize to WeChat cover dimensions (900x500)
            # WeChat requires specific aspect ratio
            img = img.resize((900, 500), Image.Resampling.LANCZOS)

            # Convert to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            buffer.seek(0)

            return buffer.getvalue()

        return None
    except Exception as e:
        logger.error(f"Failed to create cover for {paper['arxiv_id']}: {e}")
        return None


async def publish_single_article(
    wechat_client: WeChatMPClient,
    title: str,
    content: str,
    digest: str,
    cover_data: bytes,
    arxiv_url: str
) -> Optional[dict]:
    """Publish a single article to WeChat MP as draft."""
    logger.info(f"Creating draft: {title[:30]}...")

    try:
        # Upload cover image
        thumb_media_id = await wechat_client.upload_image(cover_data, "cover.jpg")

        # Create article
        article = {
            "title": title[:30],  # WeChat title limit
            "author": "arxiv_daily",
            "digest": digest[:100],  # WeChat digest limit
            "content": content,
            "thumb_media_id": thumb_media_id,
            "content_source_url": arxiv_url,
            "need_open_comment": 0,
            "only_fans_can_comment": 0
        }

        # Create draft
        draft_media_id = await wechat_client.create_draft([article])

        logger.info(f"Draft created: {draft_media_id}")

        return {
            "title": title,
            "draft_media_id": draft_media_id,
            "thumb_media_id": thumb_media_id
        }

    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        return None


async def publish_summary_article(
    wechat_client: WeChatMPClient,
    content: dict,
    papers: list[dict]
) -> Optional[dict]:
    """Publish the summary article with all papers."""
    logger.info("Creating summary draft...")

    try:
        # Use first paper's cover for summary
        cover_data = await create_paper_cover(papers[0])

        if not cover_data:
            # Fallback: create a simple cover
            from PIL import Image
            import io

            img = Image.new('RGB', (900, 500), color=(52, 73, 94))
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            buffer.seek(0)
            cover_data = buffer.getvalue()

        # Upload cover
        thumb_media_id = await wechat_client.upload_image(cover_data, "summary_cover.jpg")

        # Create article
        article = {
            "title": content.get("title", f"AI Agent 论文精选 ({len(papers)}篇)")[:30],
            "author": "arxiv_daily",
            "digest": content.get("digest", f"今日精选 {len(papers)} 篇高质量论文")[:100],
            "content": content.get("content", ""),
            "thumb_media_id": thumb_media_id,
            "content_source_url": "https://arxiv.org",
            "need_open_comment": 0,
            "only_fans_can_comment": 0
        }

        # Create draft
        draft_media_id = await wechat_client.create_draft([article])

        logger.info(f"Summary draft created: {draft_media_id}")

        return {
            "title": content.get("title"),
            "draft_media_id": draft_media_id
        }

    except Exception as e:
        logger.error(f"Failed to create summary draft: {e}")
        return None


async def main():
    """Main function for n+1 publishing to WeChat MP."""
    print("\n" + "=" * 60)
    print("WeChat MP n+1 Publishing - Detailed Posts + Summary")
    print("=" * 60)

    # Check configuration
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        print("❌ WeChat MP not configured. Set WECHAT_APP_ID and WECHAT_APP_SECRET.")
        return

    # Load papers from database or file
    papers_path = Path('storage/selected_papers.json')
    if not papers_path.exists():
        print("❌ No selected papers found. Run selection first.")
        return

    with open(papers_path, 'r') as f:
        papers = json.load(f)

    # Filter AI-related papers
    ai_papers = [p for p in papers if any(cat in p.get('categories', '[]') for cat in ['cs.CL', 'cs.AI', 'cs.LG', 'cs.MA'])]

    n = len(ai_papers)
    print(f"\n准备发布 {n} 篇AI论文 (n+1模式)...")

    # Initialize
    llm_client = BailianClient()
    wechat_client = get_wechat_client()

    if not wechat_client:
        print("❌ Failed to initialize WeChat client.")
        return

    published_posts = []

    # ========== Step 1: Publish n detailed posts ==========
    print("\n" + "-" * 60)
    print(f"Step 1: Publishing {n} detailed posts")
    print("-" * 60)

    for i, paper in enumerate(ai_papers):
        print(f"\n[{i+1}/{n}] Processing: {paper['arxiv_id']} - {paper['title'][:40]}...")

        # Generate content
        content = await generate_single_paper_content(paper, llm_client)
        if not content:
            print(f"  ❌ Failed to generate content")
            continue

        # Create cover from PDF
        cover_data = await create_paper_cover(paper)
        if not cover_data:
            print(f"  ⚠️ Failed to create cover, skipping")
            continue

        # Create draft
        arxiv_url = f"https://arxiv.org/abs/{paper['arxiv_id']}"
        result = await publish_single_article(
            wechat_client=wechat_client,
            title=content.get('title', paper['title'][:30]),
            content=content.get('content', ''),
            digest=content.get('digest', ''),
            cover_data=cover_data,
            arxiv_url=arxiv_url
        )

        if result:
            print(f"  ✅ Draft created!")
            published_posts.append({
                "arxiv_id": paper['arxiv_id'],
                "title": paper['title'],
                "wechat_title": content.get('title'),
                "draft_media_id": result.get('draft_media_id')
            })
        else:
            print(f"  ❌ Failed to create draft")

    print(f"\n✅ Created {len(published_posts)} detailed drafts")

    # ========== Step 2: Publish summary post ==========
    print("\n" + "-" * 60)
    print("Step 2: Publishing summary post")
    print("-" * 60)

    summary_content = await generate_summary_content(ai_papers, llm_client)
    if not summary_content:
        print("❌ Failed to generate summary content")
        return

    summary_result = await publish_summary_article(wechat_client, summary_content, ai_papers)

    if summary_result:
        print(f"✅ Summary draft created!")
    else:
        print("⚠️ Summary draft creation failed")

    # Final summary
    print("\n" + "=" * 60)
    print("发布完成！")
    print("=" * 60)
    print(f"  详细文章草稿: {len(published_posts)} 篇")
    print(f"  汇总文章草稿: 1 篇")
    print("\n⚠️ 草稿已创建，请在微信公众号后台预览并发布")

    return {
        "detailed_posts": published_posts,
        "summary_post": summary_result
    }


if __name__ == "__main__":
    result = asyncio.run(main())