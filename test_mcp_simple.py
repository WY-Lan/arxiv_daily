#!/usr/bin/env python
"""
Simple test script for XHS MCP publishing.

This script tests if we can publish to XHS via MCP without the full arxiv pipeline.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_mcp_publish():
    """Test MCP publishing directly."""
    print("=" * 60)
    print("测试小红书 MCP 发布功能")
    print("=" * 60)

    # 检查图片是否存在
    image_path = "/Users/wuyang.lan/Downloads/arxiv_daily/storage/cover.jpg"
    if Path(image_path).exists():
        print(f"✅ 图片存在: {image_path}")
    else:
        print(f"❌ 图片不存在: {image_path}")
        return False

    # 测试内容
    content = {
        "title": "论文推荐系统测试",
        "content": """这是一条来自 AI Agent 论文推荐系统的测试帖子 🔥

系统功能：
📌 自动抓取 arxiv 最新论文
📌 智能筛选高质量内容
📌 多平台自动发布

测试成功！感谢关注～""",
        "images": [image_path],
        "tags": ["AI论文", "测试", "自动化"]
    }

    print(f"\n准备发布:")
    print(f"  标题: {content['title']}")
    print(f"  正文: {len(content['content'])} 字")
    print(f"  图片: {len(content['images'])} 张")
    print(f"  标签: {content['tags']}")

    print("\n" + "=" * 60)
    print("请在 Claude Code 环境中调用 MCP 发布")
    print("调用示例:")
    print("  mcp__xiaohongshu-mcp__publish_content(")
    print(f"    title=\"{content['title']}\",")
    print(f"    content=\"{content['content']}\",")
    print(f"    images={content['images']},")
    print(f"    tags={content['tags']}")
    print("  )")
    print("=" * 60)

    return content


if __name__ == "__main__":
    result = asyncio.run(test_mcp_publish())
    if result:
        print("\n✅ 数据准备完成，可以进行 MCP 发布测试")
    else:
        print("\n❌ 测试失败")
        sys.exit(1)