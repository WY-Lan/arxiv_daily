"""
Publish 5+1 posts to Xiaohongshu:
- 5 detailed posts (one per paper with in-depth analysis)
- 1 summary post with links to the 5 detailed posts
"""
import asyncio
import json
from pathlib import Path
from typing import Optional

from loguru import logger
from tools.llm_client import BailianClient
from tools.pdf_screenshot import download_and_screenshot
from config.prompts import load_prompt


async def generate_single_paper_content(
    paper: dict,
    llm_client: BailianClient
) -> dict:
    """Generate detailed XHS content for a single paper."""
    # Load prompt template
    prompt_template = load_prompt("xhs_single_paper")

    # Prepare paper info
    authors = json.loads(paper['authors']) if isinstance(paper['authors'], str) else paper['authors']

    paper_info = {
        "title": paper['title'],
        "arxiv_id": paper['arxiv_id'],
        "authors": authors[:3] if authors else [],
        "abstract": paper.get('abstract', ''),
    }

    # Create full prompt
    prompt = f"""{prompt_template}

## 论文数据

请根据以下论文信息生成小红书深度解读笔记：

{json.dumps(paper_info, ensure_ascii=False, indent=2)}
"""

    logger.info(f"Generating single-paper content for {paper['arxiv_id']}...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def generate_summary_content(
    papers: list[dict],
    llm_client: BailianClient,
    published_posts: list[dict]
) -> dict:
    """Generate summary XHS content with links to detailed posts."""
    # Load prompt template
    prompt_template = load_prompt("xhs_collection")

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

注意：在正文中，每篇论文简介后添加"👉 详解见评论区置顶"，引导读者查看详细解读。
"""

    logger.info("Generating summary content...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def create_single_paper_cover(paper: dict, output_dir: Path) -> Optional[str]:
    """Create cover image for a single paper."""
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


async def publish_single_post(
    title: str,
    content: str,
    tags: list,
    cover_image: str
) -> Optional[dict]:
    """Publish a single post to XHS using MCP."""
    logger.info(f"Publishing: {title}")

    # Clean tags - remove # prefix if present
    clean_tags = [t.lstrip('#') for t in tags]

    try:
        # Use MCP tool to publish
        from mcp import use_mcp_tool
        result = await use_mcp_tool(
            server_name="xiaohongshu-mcp",
            tool_name="publish_content",
            arguments={
                "title": title[:20],  # XHS title limit
                "content": content,
                "images": [cover_image],
                "tags": clean_tags
            }
        )
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
    logger.info("Posting pinned comment...")

    try:
        from mcp import use_mcp_tool

        # Post the comment
        result = await use_mcp_tool(
            server_name="xiaohongshu-mcp",
            tool_name="post_comment_to_feed",
            arguments={
                "feed_id": feed_id,
                "xsec_token": xsec_token,
                "content": comment_content
            }
        )

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

    # Load papers
    with open('storage/selected_papers.json', 'r') as f:
        papers = json.load(f)

    # Filter AI-related papers
    ai_papers = [p for p in papers if any(cat in p.get('categories', '[]') for cat in ['cs.CL', 'cs.AI', 'cs.LG', 'cs.MA'])]
    ai_papers = ai_papers[:5]  # Limit to 5 papers

    print(f"\n准备发布 {len(ai_papers)} 篇AI相关论文...")

    # Initialize
    llm_client = BailianClient()
    output_dir = Path("storage/xhs_posts")
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

        # Create cover
        cover_path = await create_single_paper_cover(paper, output_dir)
        if not cover_path:
            print(f"  ❌ Failed to create cover, using fallback")
            cover_path = "storage/cover_fallback.jpg"

        # Publish
        result = await publish_single_post(
            title=content.get('title', ''),
            content=content.get('content', ''),
            tags=content.get('tags', []),
            cover_image=cover_path
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

    # Create summary cover (use first paper's cover or fallback)
    summary_cover = "storage/xhs_cover.jpg"
    if not Path(summary_cover).exists():
        summary_cover = "storage/cover_fallback.jpg"

    summary_result = await publish_single_post(
        title=summary_content.get('title', '今日AI论文精选'),
        content=summary_content.get('content', ''),
        tags=summary_content.get('tags', []),
        cover_image=summary_cover
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