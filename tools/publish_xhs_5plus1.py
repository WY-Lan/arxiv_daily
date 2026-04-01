"""
Publish 5+1 posts to Xiaohongshu:
- 5 detailed posts (one per paper with in-depth analysis)
- 1 summary post with links to the 5 detailed posts

Now supports multi-image posts with key figures extracted from PDF.
"""
import asyncio
import json
from pathlib import Path
from typing import Optional, List

from loguru import logger
from tools.llm_client import BailianClient
from tools.pdf_screenshot import download_and_screenshot
from tools.pdf_image_extractor import (
    PDFImageExtractor,
    ImageSelector,
    extract_key_images_for_paper
)
from config.prompts import load_prompt


async def generate_single_paper_content(
    paper: dict,
    llm_client: BailianClient
) -> dict:
    """Generate detailed XHS content for a single paper using skill guidelines."""
    from config.prompts import load_skill_prompt

    # Load XHS publisher skill prompt (includes SKILL.md + examples)
    skill_prompt = load_skill_prompt("xhs-publisher")

    # Prepare paper info with abstract for unit extraction
    authors = json.loads(paper['authors']) if isinstance(paper['authors'], str) else paper['authors']

    paper_info = {
        "title": paper['title'],
        "arxiv_id": paper['arxiv_id'],
        "authors": authors[:5] if authors else [],  # More authors for unit extraction
        "abstract": paper.get('abstract', ''),
    }

    # Create full prompt using skill guidelines
    prompt = f"""{skill_prompt}

## 当前任务

请根据以下论文信息，按照上述单篇发布模式的规范生成小红书深度解读笔记。

**注意**：
1. 标题必须包含单位信息（从摘要/作者中提取），格式：单位 + "推出" + 「核心概念」产品名 + emoji
2. 正文段落式写作，空行分隔，学术化风格
3. 结尾格式：paper：论文标题
4. 不需要互动引导

## 论文数据

{json.dumps(paper_info, ensure_ascii=False, indent=2)}
"""

    logger.info(f"Generating single-paper content for {paper['arxiv_id']} using skill...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def generate_summary_content(
    papers: list[dict],
    llm_client: BailianClient,
    published_posts: list[dict]
) -> dict:
    """Generate summary XHS content with links to detailed posts."""
    from datetime import datetime

    # Load prompt template
    prompt_template = load_prompt("xhs_collection")

    # Get current date
    today = datetime.now()
    date_str = today.strftime("%Y年%m月%d日")
    year_str = str(today.year)

    # Prepare papers info with links
    papers_info = []
    for i, p in enumerate(papers[:5]):
        authors = json.loads(p['authors']) if isinstance(p['authors'], str) else p['authors']
        post_info = published_posts[i] if i < len(published_posts) else {}

        papers_info.append({
            "title": p['title'],
            "arxiv_id": p['arxiv_id'],
            "authors": authors[:3] if authors else [],
            "summary": p.get('abstract', '')[:300],
            "post_url": post_info.get('url', '待发布')
        })

    # Create prompt
    prompt = f"""{prompt_template}

## 今日论文数据（含详细推文链接）

请根据以下论文信息生成小红书合集笔记：

{json.dumps(papers_info, ensure_ascii=False, indent=2)}

注意：
1. 标题使用"今日"开头，如"今日5篇AI Agent论文精选"，不要带年份
2. 每篇论文简介后添加"👉 详解见评论区置顶"，引导读者查看详细解读
"""

    logger.info("Generating summary content...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def create_single_paper_cover(paper: dict, output_dir: Path) -> Optional[str]:
    """Create cover image for a single paper (PDF first page screenshot)."""
    logger.info(f"Creating cover for {paper['arxiv_id']}...")

    try:
        # download_and_screenshot automatically saves to storage/covers/
        # and returns the path. We don't specify output_path.
        result = await download_and_screenshot(
            pdf_url=paper['pdf_url'],
            arxiv_id=paper['arxiv_id']
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create cover for {paper['arxiv_id']}: {e}")
        return None


async def create_single_paper_images(
    paper: dict,
    output_dir: Path,
    max_pages: int = 18
) -> List[str]:
    """
    Extract all PDF pages as images for XHS multi-image post.

    XHS supports up to 18 images per post. This function extracts all pages
    from the PDF (up to max_pages) to create a multi-image post.

    Args:
        paper: Paper dict with arxiv_id and pdf_url
        output_dir: Directory to save images
        max_pages: Maximum number of pages to extract (default 18, XHS limit)

    Returns:
        List of image paths (page_1, page_2, ..., page_n)
    """
    images = []

    try:
        logger.info(f"Extracting all pages from PDF for {paper['arxiv_id']}...")

        # Extract all PDF pages as images (prefer_full_pages=True)
        page_paths = await extract_key_images_for_paper(
            arxiv_id=paper['arxiv_id'],
            pdf_url=paper.get('pdf_url'),
            max_images=max_pages,
            output_dir=output_dir,
            prefer_full_pages=True  # Extract all pages, not just key images
        )

        if page_paths:
            images = page_paths
            logger.info(f"Extracted {len(images)} pages for {paper['arxiv_id']}")
        else:
            logger.warning(f"No pages extracted for {paper['arxiv_id']}")
            # Fallback to cover image
            cover_path = await create_single_paper_cover(paper, output_dir)
            if cover_path:
                images.append(cover_path)

    except Exception as e:
        logger.error(f"Failed to extract pages for {paper['arxiv_id']}: {e}")
        # Fallback to cover image
        cover_path = await create_single_paper_cover(paper, output_dir)
        if cover_path:
            images.append(cover_path)

    logger.info(f"Final images for {paper['arxiv_id']}: {len(images)} pages")
    return images


async def publish_single_post(
    title: str,
    content: str,
    tags: list,
    images: list  # Changed from single cover_image to list of images
) -> Optional[dict]:
    """
    Publish a single post to XHS using MCP.

    Args:
        title: Post title (max 20 chars)
        content: Post content
        tags: List of tags (without # prefix)
        images: List of image paths (1-18 images)

    Returns:
        Publish result dict with url, feed_id, xsec_token
    """
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    logger.info(f"Publishing: {title}")
    logger.info(f"Images: {len(images)}")

    # Clean tags - remove # prefix if present
    clean_tags = [t.lstrip('#') for t in tags]

    try:
        # Use MCP client to publish directly to xiaohongshu-mcp server
        async with streamablehttp_client("http://localhost:18060/mcp") as (read, write, session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool("publish_content", {
                    "title": title[:20],  # XHS title limit
                    "content": content,
                    "images": images,
                    "tags": clean_tags,
                    "is_original": False
                })

                # Parse result
                if result and hasattr(result, 'content'):
                    for c in result.content:
                        if c.type == 'text':
                            text = c.text
                            # Check for success message
                            if "发布成功" in text or "发布完成" in text:
                                logger.info(f"Publish success detected: {text[:100]}")
                                # Try to extract URL if present
                                url = ""
                                if "http" in text:
                                    # Extract URL from text
                                    import re
                                    url_match = re.search(r'https?://[^\s]+', text)
                                    if url_match:
                                        url = url_match.group(0)
                                return {
                                    "url": url,
                                    "feed_id": "",
                                    "xsec_token": "",
                                    "raw_result": text
                                }
                            # Try JSON parse
                            try:
                                data = json.loads(text)
                                return {
                                    "url": data.get("url", ""),
                                    "feed_id": data.get("feed_id", ""),
                                    "xsec_token": data.get("xsec_token", "")
                                }
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse result as JSON: {text[:200]}")
                                # Return empty but mark as potential success
                                return {"url": "", "feed_id": "", "xsec_token": "", "raw_result": text}

                return result
    except Exception as e:
        logger.error(f"Failed to publish post: {e}")
        return None


async def post_pinned_comment(
    feed_id: str,
    xsec_token: str,
    comment_content: str
) -> bool:
    """Post a comment and pin it to the top."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    logger.info("Posting pinned comment...")

    try:
        async with streamablehttp_client("http://localhost:18060/mcp") as (read, write, session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Post the comment
                result = await session.call_tool("post_comment_to_feed", {
                    "feed_id": feed_id,
                    "xsec_token": xsec_token,
                    "content": comment_content
                })

                # Note: Pinning requires manual action in XHS app
                # The comment will be posted but not automatically pinned
                logger.info("Comment posted. Please pin it manually in XHS app.")
                return True
    except Exception as e:
        logger.error(f"Failed to post comment: {e}")
        return False


async def main():
    """Main function for 5+1 publishing."""
    print("\n" + "=" * 60)
    print("XHS 5+1 Publishing - Detailed Posts + Summary")
    print("=" * 60)

    # Get project root directory
    project_root = Path(__file__).parent.parent

    # Load papers
    with open(project_root / 'storage/selected_papers.json', 'r') as f:
        papers = json.load(f)

    # Use all selected papers (they are already filtered)
    # Only filter by categories if the field exists
    ai_papers = []
    for p in papers:
        categories = p.get('categories', '')
        if not categories:
            # No categories field, include by default
            ai_papers.append(p)
        elif isinstance(categories, str):
            if any(cat in categories for cat in ['cs.CL', 'cs.AI', 'cs.LG', 'cs.MA']):
                ai_papers.append(p)
        elif isinstance(categories, list):
            if any(cat in categories for cat in ['cs.CL', 'cs.AI', 'cs.LG', 'cs.MA']):
                ai_papers.append(p)

    ai_papers = ai_papers[:5]  # Limit to 5 papers

    print(f"\n准备发布 {len(ai_papers)} 篇AI相关论文...")

    # Initialize
    llm_client = BailianClient()
    output_dir = project_root / "storage/xhs_posts"
    output_dir.mkdir(exist_ok=True)

    published_posts = []

    # ========== Step 1: Publish 5 detailed posts ==========
    print("\n" + "-" * 60)
    print("Step 1: Publishing 5 detailed posts")
    print("-" * 60)

    for i, paper in enumerate(ai_papers):
        print(f"\n[{i+1}/5] Processing: {paper['arxiv_id']} - {paper['title'][:40]}...")

        # Generate content
        content = await generate_single_paper_content(paper, llm_client)
        if not content:
            print(f"  ❌ Failed to generate content")
            continue

        # Create images (all PDF pages, up to 18 for XHS limit)
        images = await create_single_paper_images(paper, output_dir, max_pages=18)
        if not images:
            print(f"  ❌ Failed to create images")
            continue

        print(f"  📷 Images: {len(images)} PDF pages")

        # Publish with multiple images
        result = await publish_single_post(
            title=content.get('title', ''),
            content=content.get('content', ''),
            tags=content.get('tags', []),
            images=images  # Pass all images (cover + key figures)
        )

        if result:
            print(f"  ✅ Published successfully!")
            published_posts.append({
                "arxiv_id": paper['arxiv_id'],
                "title": paper['title'],
                "xhs_title": content.get('title', ''),
                "url": result.get('url', ''),
                "feed_id": result.get('feed_id', ''),
                "xsec_token": result.get('xsec_token', '')
            })
        else:
            print(f"  ⚠️ Published but no URL returned")

        # Save progress
        with open(output_dir / "published_posts.json", 'w') as f:
            json.dump(published_posts, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Published {len(published_posts)} detailed posts")

    # ========== Step 2: Publish summary post ==========
    print("\n" + "-" * 60)
    print("Step 2: Publishing summary post")
    print("-" * 60)

    summary_content = await generate_summary_content(ai_papers, llm_client, published_posts)
    if not summary_content:
        print("❌ Failed to generate summary content")
        return

    # Create summary cover using 5 paper first pages
    print("Creating summary cover with 5 paper first pages...")
    summary_images = []

    for paper in ai_papers[:5]:
        # Get first page image for each paper
        first_page = output_dir / f"{paper['arxiv_id']}_page_1.png"
        if first_page.exists():
            summary_images.append(str(first_page))
        else:
            # Try to get from covers directory
            cover_path = project_root / f"storage/covers/{paper['arxiv_id']}.png"
            if cover_path.exists():
                summary_images.append(str(cover_path))

    if not summary_images:
        # Fallback to default cover
        fallback = project_root / "storage/cover_fallback.jpg"
        if fallback.exists():
            summary_images = [str(fallback)]

    print(f"  📷 Summary cover: {len(summary_images)} paper first pages")

    summary_result = await publish_single_post(
        title=summary_content.get('title', '今日AI论文精选'),
        content=summary_content.get('content', ''),
        tags=summary_content.get('tags', []),
        images=summary_images  # Use 5 paper first pages as cover
    )

    if summary_result:
        print(f"✅ Summary post published!")
        summary_post = {
            "title": summary_content.get('title', ''),
            "url": summary_result.get('url', ''),
            "feed_id": summary_result.get('feed_id', ''),
            "xsec_token": summary_result.get('xsec_token', '')
        }
    else:
        print("⚠️ Summary post published but no URL returned")
        summary_post = {}

    # ========== Step 3: Prepare pinned comment ==========
    print("\n" + "-" * 60)
    print("Step 3: Preparing pinned comment")
    print("-" * 60)

    if summary_post.get('feed_id') and published_posts:
        # Build comment with links
        comment_lines = ["📌 详细解读传送门：\n"]
        for i, post in enumerate(published_posts, 1):
            short_title = post.get('xhs_title', post.get('title', ''))[:15]
            url = post.get('url', '待更新')
            comment_lines.append(f"{i}. {short_title}...")
            comment_lines.append(f"   🔗 {url}\n")

        comment_content = "\n".join(comment_lines)

        # Save comment for manual posting
        with open(output_dir / "pinned_comment.txt", 'w') as f:
            f.write(comment_content)

        print("✅ Pinned comment prepared:")
        print(comment_content)
        print("\n⚠️ 请在小红书App中手动置顶此评论")

    # Final summary
    print("\n" + "=" * 60)
    print("发布完成！")
    print("=" * 60)
    print(f"  详细推文: {len(published_posts)} 篇")
    print(f"  汇总推文: 1 篇")
    print(f"  置顶评论: 已准备 (storage/xhs_posts/pinned_comment.txt)")

    return {
        "detailed_posts": published_posts,
        "summary_post": summary_post
    }


if __name__ == "__main__":
    result = asyncio.run(main())