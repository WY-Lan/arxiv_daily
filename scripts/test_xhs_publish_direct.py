#!/usr/bin/env python
"""
Direct XHS publishing test using existing content.
Bypasses LLM generation and uses pre-generated content.
"""
import asyncio
import json
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


async def extract_pdf_pages(arxiv_id: str, max_pages: int = 18) -> list[str]:
    """Extract all pages from PDF as images."""
    from tools.pdf_image_extractor import extract_key_images_for_paper

    output_dir = PROJECT_ROOT / "storage/xhs_posts"
    output_dir.mkdir(exist_ok=True)

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    print(f"  📷 Extracting PDF pages for {arxiv_id}...")
    images = await extract_key_images_for_paper(
        arxiv_id=arxiv_id,
        pdf_url=pdf_url,
        max_images=max_pages,
        output_dir=output_dir,
        prefer_full_pages=True
    )

    return images


async def publish_to_xhs(title: str, content: str, images: list[str], tags: list[str]) -> dict:
    """Publish content to XHS via MCP."""
    async with streamablehttp_client("http://localhost:18060/mcp") as (read, write, session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Clean tags - remove # prefix
            clean_tags = [t.lstrip('#') for t in tags]

            result = await session.call_tool("publish_content", {
                "title": title[:20],  # XHS title limit
                "content": content,
                "images": images,
                "tags": clean_tags,
                "is_original": False
            })

            return result


async def main():
    print("\n" + "=" * 60)
    print("XHS Direct Publishing Test")
    print("=" * 60)

    # Load pre-generated content
    content_file = PROJECT_ROOT / "storage/xhs_all_content.json"
    if not content_file.exists():
        print(f"❌ Content file not found: {content_file}")
        return

    with open(content_file, 'r') as f:
        contents = json.load(f)

    print(f"\n找到 {len(contents)} 篇预生成内容")

    # Test with first paper
    paper = contents[0]
    arxiv_id = paper.get('arxiv_id', 'unknown')

    print(f"\n发布论文: {arxiv_id}")
    print(f"  标题: {paper['title']}")

    # Extract PDF pages
    images = await extract_pdf_pages(arxiv_id, max_pages=18)

    if not images:
        print(f"  ❌ 无法提取PDF页面")
        return

    print(f"  ✅ 提取了 {len(images)} 页图片")

    # Publish
    print(f"\n  🚀 正在发布到小红书...")

    result = await publish_to_xhs(
        title=paper['title'],
        content=paper['content'],
        images=images,
        tags=paper['tags']
    )

    print(f"\n发布结果:")
    for c in result.content:
        if c.type == 'text':
            print(f"  {c.text}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())