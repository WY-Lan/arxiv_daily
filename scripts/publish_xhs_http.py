#!/usr/bin/env python
"""Publish to XHS via HTTP MCP"""
import asyncio
import json
import httpx

MCP_URL = "http://localhost:18060/mcp"

async def call_mcp(method: str, params: dict = None):
    """Call MCP via HTTP"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Initialize session
        init_response = await client.post(MCP_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "xhs-publisher", "version": "1.0"}
            }
        })
        print(f"Init: {init_response.status_code}")

        # Send initialized notification
        await client.post(MCP_URL, json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })

        # Call the actual method
        response = await client.post(MCP_URL, json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": method,
            "params": params or {}
        })

        return response.json()


async def publish_content(title: str, content: str, images: list, tags: list):
    """Publish content to XHS"""
    result = await call_mcp("tools/call", {
        "name": "publish_content",
        "arguments": {
            "title": title,
            "content": content,
            "images": images,
            "tags": tags,
            "is_original": False
        }
    })
    return result


async def main():
    # Load content
    with open("/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_all_content.json", "r") as f:
        all_content = json.load(f)

    # Publish first paper
    paper = all_content[0]
    print(f"\n发布论文: {paper['title']}")
    print(f"封面: {paper['cover']}")

    result = await publish_content(
        title=paper["title"],
        content=paper["content"],
        images=[paper["cover"]],
        tags=[t.lstrip("#") for t in paper["tags"]]
    )

    print(f"\n发布结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())