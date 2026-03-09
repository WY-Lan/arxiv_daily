#!/usr/bin/env python
"""
Test script for XHS MCP publishing.

This script tests the ability to publish a post to Xiaohongshu via MCP.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_xhs_mcp_publish():
    """Test publishing to XHS via MCP."""
    print("=" * 60)
    print("Testing XHS MCP Publish")
    print("=" * 60)

    # Test content
    title = "AI Agent 论文推荐测试"
    content = """今天测试一下论文推荐系统 🔥

这是一个自动化论文推送系统测试帖子。

功能特点：
📌 自动抓取 arxiv 论文
📌 智能筛选评分
📌 多平台发布

测试成功！感谢关注～"""

    images = ["/Users/wuyang.lan/Downloads/arxiv_daily/storage/cover.jpg"]

    print(f"\n准备发布内容:")
    print(f"  标题: {title}")
    print(f"  正文长度: {len(content)} 字")
    print(f"  图片: {len(images)} 张")

    # Check if image exists
    if not Path(images[0]).exists():
        print(f"\n❌ 图片文件不存在: {images[0]}")
        return False

    print(f"\n✅ 图片文件存在: {images[0]}")

    # Note: The actual MCP call needs to be done in the Claude Code environment
    # This script validates the data preparation
    print("\n" + "=" * 60)
    print("数据准备完成，需要在 Claude Code 环境中调用 MCP 发布")
    print("=" * 60)

    # Return prepared data
    return {
        "title": title,
        "content": content,
        "images": images,
        "tags": ["AI论文", "测试", "自动化"]
    }


if __name__ == "__main__":
    result = asyncio.run(test_xhs_mcp_publish())
    if result:
        print("\n✅ 测试脚本执行成功")
        print(f"准备发布的数据: {result}")
    else:
        print("\n❌ 测试脚本执行失败")
        sys.exit(1)