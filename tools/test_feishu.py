"""
Test script for Feishu webhook integration.

Usage:
    # Test with webhook URL from .env
    python tools/test_feishu.py

    # Test with custom webhook URL
    python tools/test_feishu.py --webhook https://open.feishu.cn/open-apis/bot/v2/hook/xxx
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config.settings import settings
from tools.feishu_webhook import FeishuWebhookClient, send_test_message


async def test_basic_message(webhook_url: str):
    """Test basic text message."""
    print("\n" + "="*50)
    print("Test 1: Basic Text Message")
    print("="*50)

    client = FeishuWebhookClient(webhook_url)
    result = await client.send_text("🎉 测试消息：飞书 Webhook 配置成功！")

    print(f"Result: {result}")
    return result.get("success", False)


async def test_post_message(webhook_url: str):
    """Test rich text post message."""
    print("\n" + "="*50)
    print("Test 2: Rich Text Post Message")
    print("="*50)

    client = FeishuWebhookClient(webhook_url)

    content = [
        [{"tag": "text", "text": "这是一条"}],
        [{"tag": "text", "text": "富文本消息，支持"},
         {"tag": "a", "text": "链接", "href": "https://arxiv.org"}],
        [{"tag": "text", "text": "测试完成！"}]
    ]

    result = await client.send_post(
        title="📝 富文本测试",
        content=content
    )

    print(f"Result: {result}")
    return result.get("success", False)


async def test_card_message(webhook_url: str):
    """Test interactive card message."""
    print("\n" + "="*50)
    print("Test 3: Interactive Card Message")
    print("="*50)

    client = FeishuWebhookClient(webhook_url)

    elements = [
        {
            "tag": "markdown",
            "content": "**📚 每日论文精选**\n今日推荐 3 篇 Agent 相关论文"
        },
        {"tag": "hr"},
        {
            "tag": "markdown",
            "content": "### 1. Tree of Thoughts\n👥 Shunyu Yao et al.\n💡 提出思维树框架提升推理能力"
        },
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看论文"},
                    "url": "https://arxiv.org/abs/2305.10601",
                    "type": "primary"
                }
            ]
        },
        {"tag": "hr"},
        {
            "tag": "markdown",
            "content": "🤖 由 Arxiv Daily Push 自动推送"
        }
    ]

    result = await client.send_card(
        title="每日论文精选",
        elements=elements,
        subtitle="2024-01-15"
    )

    print(f"Result: {result}")
    return result.get("success", False)


async def test_paper_digest(webhook_url: str):
    """Test paper digest format."""
    print("\n" + "="*50)
    print("Test 4: Paper Digest Format")
    print("="*50)

    client = FeishuWebhookClient(webhook_url)

    # Mock paper data
    papers = [
        {
            "title": "Tree of Thoughts: Deliberate Problem Solving with Large Language Models",
            "arxiv_id": "2305.10601",
            "authors": ["Shunyu Yao", "Dian Yu", "Jeffrey Zhao"],
            "summary": "提出了一种新的推理框架，通过探索多条推理路径来增强语言模型的问题解决能力。",
            "highlights": ["多路径推理", "思维树框架", "复杂问题求解"],
            "tags": ["Reasoning", "LLM", "Agent"],
            "code_url": "https://github.com/princeton-nlp/tree-of-thought-llm"
        },
        {
            "title": "ReAct: Synergizing Reasoning and Acting in Language Models",
            "arxiv_id": "2210.03629",
            "authors": ["Shunyu Yao", "Jeffrey Zhao", "Dian Yu"],
            "summary": "结合推理和行动，使语言模型能够更可靠地进行决策和任务执行。",
            "highlights": ["推理与行动结合", "交互式决策", "任务规划"],
            "tags": ["Agent", "Planning", "Reasoning"],
            "code_url": "https://github.com/ysymyth/ReAct"
        }
    ]

    result = await client.send_paper_digest(papers)

    print(f"Result: {result}")
    return result.get("success", False)


async def main():
    parser = argparse.ArgumentParser(description="Test Feishu webhook integration")
    parser.add_argument(
        "--webhook",
        type=str,
        help="Feishu webhook URL (uses .env setting if not provided)"
    )
    parser.add_argument(
        "--test",
        type=str,
        default="all",
        choices=["basic", "post", "card", "digest", "all"],
        help="Which test to run"
    )
    args = parser.parse_args()

    # Get webhook URL
    webhook_url = args.webhook or settings.FEISHU_WEBHOOK_URL

    if not webhook_url:
        print("❌ Error: No webhook URL provided")
        print("Please either:")
        print("  1. Set FEISHU_WEBHOOK_URL in .env file")
        print("  2. Pass --webhook argument")
        return

    print(f"Using webhook URL: {webhook_url[:50]}...")

    results = {}

    if args.test in ["basic", "all"]:
        results["basic"] = await test_basic_message(webhook_url)
        await asyncio.sleep(1)  # Rate limiting

    if args.test in ["post", "all"]:
        results["post"] = await test_post_message(webhook_url)
        await asyncio.sleep(1)

    if args.test in ["card", "all"]:
        results["card"] = await test_card_message(webhook_url)
        await asyncio.sleep(1)

    if args.test in ["digest", "all"]:
        results["digest"] = await test_paper_digest(webhook_url)

    # Summary
    print("\n" + "="*50)
    print("Test Summary")
    print("="*50)
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'✅ All tests passed' if all_passed else '❌ Some tests failed'}")


if __name__ == "__main__":
    asyncio.run(main())