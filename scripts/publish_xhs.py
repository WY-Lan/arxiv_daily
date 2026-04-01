#!/usr/bin/env python
"""
Publish selected papers to Xiaohongshu via MCP.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


async def publish_to_xhs():
    """Publish papers to XHS via MCP."""
    # Load selected papers
    papers_file = Path(__file__).parent.parent / "storage" / "selected_papers.json"
    with open(papers_file, 'r') as f:
        papers = json.load(f)

    print(f"Loaded {len(papers)} papers")

    # Load XHS content for first paper
    content_file = Path(__file__).parent.parent / "storage" / "xhs_content_1.json"
    with open(content_file, 'r') as f:
        content = json.load(f)

    # Prepare cover image
    cover_path = Path(__file__).parent.parent / "storage" / "covers" / "2603.26512.png"

    print("\n" + "=" * 60)
    print("准备发布到小红书")
    print("=" * 60)
    print(f"\n标题: {content['title']}")
    print(f"正文长度: {len(content['content'])} 字")
    print(f"标签: {content['tags']}")
    print(f"封面: {cover_path}")

    # Try to use MCP client
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # MCP server parameters
        server_params = StdioServerParameters(
            command="/Users/wuyang.lan/Downloads/arxiv_daily/mcp_servers/xiaohongshu-mcp/xiaohongshu-mcp-darwin-arm64",
            args=[],
            env=None
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                print(f"\n可用工具: {[t.name for t in tools.tools]}")

                # Call publish_content tool
                result = await session.call_tool(
                    "publish_content",
                    arguments={
                        "title": content["title"],
                        "content": content["content"],
                        "images": [str(cover_path)],
                        "tags": [t.lstrip("#") for t in content["tags"]],
                        "is_original": False
                    }
                )

                print(f"\n发布结果: {result}")
                return result

    except ImportError:
        print("\n❌ MCP 客户端库未安装")
        print("请运行: pip install mcp")
        return None
    except Exception as e:
        logger.error(f"发布失败: {e}")
        return None


if __name__ == "__main__":
    result = asyncio.run(publish_to_xhs())
    if result:
        print("\n✅ 发布成功!")
    else:
        print("\n❌ 发布失败，请手动发布")
        print(f"\n内容已保存到: storage/xhs_publish_content.md")