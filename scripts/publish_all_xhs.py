#!/usr/bin/env python
"""Publish to XHS via MCP HTTP with session management"""
import asyncio
import json

import httpx


async def main():
    # Load all papers
    with open("/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_all_content.json", "r") as f:
        all_content = json.load(f)

    async with httpx.AsyncClient(timeout=300.0, base_url="http://localhost:18060") as client:
        # Initialize and get session ID
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

        # Send initialized notification
        await client.post("/mcp",
            headers={"Mcp-Session-Id": session_id},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )

        # Check login status first
        print("\n检查登录状态...")
        login_response = await client.post("/mcp",
            headers={"Mcp-Session-Id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "check_login_status", "arguments": {}}
            }
        )
        login_result = login_response.json()
        print(f"登录状态: {json.dumps(login_result, ensure_ascii=False, indent=2)}")

        # Publish each paper
        for i, paper in enumerate(all_content, 1):
            print(f"\n{'='*60}")
            print(f"发布第 {i} 篇: {paper['title']}")
            print(f"{'='*60}")

            publish_response = await client.post("/mcp",
                headers={"Mcp-Session-Id": session_id},
                json={
                    "jsonrpc": "2.0",
                    "id": 10 + i,
                    "method": "tools/call",
                    "params": {
                        "name": "publish_content",
                        "arguments": {
                            "title": paper["title"],
                            "content": paper["content"],
                            "images": [paper["cover"]],
                            "tags": [t.lstrip("#") for t in paper["tags"]],
                            "is_original": False
                        }
                    }
                }
            )
            result = publish_response.json()
            print(f"发布结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

            # Wait between publishes
            if i < len(all_content):
                print("\n等待 5 秒后发布下一篇...")
                await asyncio.sleep(5)

        print(f"\n{'='*60}")
        print(f"完成！共发布 {len(all_content)} 篇论文")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())