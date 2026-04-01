#!/usr/bin/env python
"""Publish summary post to XHS"""
import asyncio
import json
import httpx


async def main():
    # Load summary content
    with open("/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_summary.json", "r") as f:
        content = json.load(f)

    cover_path = "/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_summary_cover.jpg"

    print(f"发布合集笔记: {content['title']}")
    print(f"封面: {cover_path}")

    async with httpx.AsyncClient(timeout=120.0, base_url="http://localhost:18060") as client:
        # Initialize session
        init_response = await client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "xhs-publisher", "version": "1.0"}
            }
        })
        session_id = init_response.headers.get("Mcp-Session-Id")
        print(f"Session ID: {session_id}")

        # Send initialized
        await client.post("/mcp",
            headers={"Mcp-Session-Id": session_id},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )

        # Publish
        print("\n发布中...")
        publish_response = await client.post("/mcp",
            headers={"Mcp-Session-Id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "publish_content",
                    "arguments": {
                        "title": content["title"],
                        "content": content["content"],
                        "images": [cover_path],
                        "tags": [t.lstrip("#") for t in content["tags"]],
                        "is_original": False
                    }
                }
            }
        )
        result = publish_response.json()

        if "result" in result:
            print("\n✅ 合集笔记发布成功!")
            text = result["result"]["content"][0]["text"]
            print(f"结果: {text[:100]}...")
        else:
            print(f"\n❌ 发布失败: {result}")


if __name__ == "__main__":
    asyncio.run(main())