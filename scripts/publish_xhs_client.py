#!/usr/bin/env python
"""Publish to XHS via MCP HTTP client"""
import asyncio
import json
from contextlib import asynccontextmanager

import httpx


class MCPClient:
    def __init__(self, url: str):
        self.url = url
        self.session_id = None
        self.request_id = 0

    async def initialize(self):
        """Initialize MCP session"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.url, json={
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xhs-publisher", "version": "1.0"}
                }
            })
            result = response.json()
            print(f"Initialize result: {result}")

            # Send initialized notification
            await client.post(self.url, json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            })

            return result

    def _next_id(self):
        self.request_id += 1
        return self.request_id

    async def list_tools(self):
        """List available tools"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Re-initialize for each request
            await client.post(self.url, json={
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xhs-publisher", "version": "1.0"}
                }
            })

            response = await client.post(self.url, json={
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list"
            })
            return response.json()

    async def call_tool(self, name: str, arguments: dict):
        """Call a tool"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Re-initialize for each request
            await client.post(self.url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xhs-publisher", "version": "1.0"}
                }
            })

            # Call tool
            response = await client.post(self.url, json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                }
            })
            return response.json()


async def main():
    client = MCPClient("http://localhost:18060/mcp")

    # List tools first
    print("Listing tools...")
    tools_result = await client.list_tools()
    print(f"Tools: {json.dumps(tools_result, ensure_ascii=False, indent=2)}")

    # Load content
    with open("/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_all_content.json", "r") as f:
        all_content = json.load(f)

    paper = all_content[0]
    print(f"\n发布: {paper['title']}")

    # Publish
    result = await client.call_tool("publish_content", {
        "title": paper["title"],
        "content": paper["content"],
        "images": [paper["cover"]],
        "tags": [t.lstrip("#") for t in paper["tags"]],
        "is_original": False
    })

    print(f"\n发布结果: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())