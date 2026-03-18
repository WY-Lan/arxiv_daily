"""
Publish XHS content with PDF cover images.
"""
import asyncio
import json
from pathlib import Path

from loguru import logger
from tools.llm_client import BailianClient
from tools.pdf_screenshot import batch_download_and_screenshot, create_xhs_cover
from config.prompts import load_prompt


async def generate_xhs_content(papers: list[dict], llm_client: BailianClient) -> dict:
    """Generate XHS content using LLM."""
    # Prepare paper info
    papers_info = []
    for p in papers[:5]:  # Limit to 5 papers
        authors = json.loads(p['authors']) if isinstance(p['authors'], str) else p['authors']
        papers_info.append({
            "title": p['title'],
            "arxiv_id": p['arxiv_id'],
            "authors": authors[:3] if authors else [],  # First 3 authors
            "summary": p.get('abstract', '')[:500]  # Truncate summary
        })

    # Load prompt template
    prompt_template = load_prompt("xhs_collection")

    # Create full prompt
    prompt = f"""{prompt_template}

## 今日论文数据

请根据以下论文信息生成小红书合集笔记：

{json.dumps(papers_info, ensure_ascii=False, indent=2)}
"""

    logger.info("Generating XHS content with LLM...")
    messages = [{"role": "user", "content": prompt}]
    result = await llm_client.generate_json(messages)

    return result


async def create_cover_images(papers: list[dict], output_path: str) -> str:
    """Create cover image from papers."""
    logger.info("Creating cover images...")

    # Download PDFs and create screenshots
    papers_with_urls = [
        {
            "arxiv_id": p['arxiv_id'],
            "pdf_url": p['pdf_url'],
            "title": p['title']
        }
        for p in papers[:3]  # Limit to 3 papers for cover
    ]

    # Create merged cover
    result = await create_xhs_cover(
        papers=papers_with_urls,
        output_path=output_path,
        title="AI论文精选",
        layout="grid"
    )

    return result


async def main():
    """Main function."""
    print("\n" + "=" * 60)
    print("XHS Publishing - AI Paper Collection")
    print("=" * 60)

    # Load papers
    with open('storage/selected_papers.json', 'r') as f:
        papers = json.load(f)

    # Filter AI-related papers
    ai_papers = [p for p in papers if any(cat in p.get('categories', '[]') for cat in ['cs.CL', 'cs.AI', 'cs.LG', 'cs.MA'])]
    ai_papers = ai_papers[:5]  # Limit to 5 papers

    print(f"\n准备发布 {len(ai_papers)} 篇AI相关论文...")

    # Initialize LLM client
    llm_client = BailianClient()

    # Generate XHS content
    xhs_content = await generate_xhs_content(ai_papers, llm_client)

    if not xhs_content:
        print("❌ Failed to generate XHS content")
        return

    print("\n✅ XHS content generated!")
    print(f"  Title: {xhs_content.get('title', 'N/A')}")
    print(f"  Content length: {len(xhs_content.get('content', ''))} chars")
    print(f"  Tags: {xhs_content.get('tags', [])}")

    # Create cover image
    cover_path = str(Path(__file__).parent.parent / "storage" / "xhs_cover.jpg")
    cover_result = await create_cover_images(ai_papers, cover_path)

    if not cover_result:
        print("\n❌ Failed to create cover image")
        return

    print(f"\n✅ Cover image created: {cover_result}")

    # Save content for publishing
    output_data = {
        "title": xhs_content.get('title', ''),
        "content": xhs_content.get('content', ''),
        "tags": xhs_content.get('tags', []),
        "cover_image": cover_result
    }

    output_file = Path(__file__).parent.parent / "storage" / "xhs_content.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Content saved to: {output_file}")
    print("\n" + "-" * 60)
    print("XHS CONTENT PREVIEW")
    print("-" * 60)
    print(f"\n【标题】{xhs_content.get('title', 'N/A')}")
    print(f"\n【正文】\n{xhs_content.get('content', 'N/A')[:500]}...")
    print(f"\n【标签】{', '.join(xhs_content.get('tags', []))}")

    return output_data


if __name__ == "__main__":
    result = asyncio.run(main())