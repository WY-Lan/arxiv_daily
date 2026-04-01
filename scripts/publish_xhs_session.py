#!/usr/bin/env python
"""Publish to XHS via MCP HTTP with persistent session"""
import asyncio
import json

import httpx


async def main():
    # Load content
    with open("/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_all_content.json", "r") as f:
        all_content = json.load(f)

    paper = all_content[0]
    print(f"准备发布: {paper['title']}")

    # Use a persistent HTTP client
    async with httpx.AsyncClient(timeout=120.0, base_url="http://localhost:18060") as client:
        # Step 1: Initialize
        print("\n1. 初始化会话...")
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
        init_result = init_response.json()
        print(f"   结果: {init_result.get('result', {}).get('serverInfo', {})}")

        # Step 2: Send initialized notification
        print("\n2. 发送初始化完成通知...")
        await client.post("/mcp", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })

        # Step 3: List tools
        print("\n3. 列出可用工具...")
        tools_response = await client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        })
        tools_result = tools_response.json()
        if "result" in tools_result:
            tools = tools_result["result"].get("tools", [])
            print(f"   可用工具: {[t['name'] for t in tools]}")
        else:
            print(f"   错误: {tools_result}")

        # Step 4: Call publish_content
        print("\n4. 发布内容...")
        publish_response = await client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 3,
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
        })
        publish_result = publish_response.json()
        print(f"   发布结果: {json.dumps(publish_result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())