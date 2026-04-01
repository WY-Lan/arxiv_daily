#!/usr/bin/env python
"""Publish to XHS via MCP stdio"""
import asyncio
import json
import os
import sys

async def publish_via_mcp():
    # Load content
    with open("/Users/wuyang.lan/Downloads/arxiv_daily/storage/xhs_all_content.json", "r") as f:
        all_content = json.load(f)

    paper = all_content[0]
    print(f"\n准备发布: {paper['title']}")

    # Prepare publish params
    params = {
        "title": paper["title"],
        "content": paper["content"],
        "images": [paper["cover"]],
        "tags": [t.lstrip("#") for t in paper["tags"]],
        "is_original": False
    }

    print(f"封面: {paper['cover']}")
    print(f"标签: {params['tags']}")

    # Create MCP commands
    commands = [
        # Initialize
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "xhs-publisher", "version": "1.0"}
        }},
        # Initialized notification
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        # List tools
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        # Call publish_content
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "publish_content",
            "arguments": params
        }}
    ]

    # Write commands to file
    with open("/tmp/mcp_commands.jsonl", "w") as f:
        for cmd in commands:
            f.write(json.dumps(cmd) + "\n")

    print("\n命令已写入 /tmp/mcp_commands.jsonl")
    print("正在调用 MCP...")

    # Run MCP process
    import subprocess
    proc = subprocess.Popen(
        ["/Users/wuyang.lan/Downloads/arxiv_daily/mcp_servers/xiaohongshu-mcp/xiaohongshu-mcp-darwin-arm64"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy()
    )

    # Send commands
    for cmd in commands:
        proc.stdin.write((json.dumps(cmd) + "\n").encode())
        proc.stdin.flush()
        await asyncio.sleep(0.5)

    # Read output
    await asyncio.sleep(2)

    stdout, stderr = proc.communicate(timeout=5)

    print("\n=== STDOUT ===")
    for line in stdout.decode().strip().split("\n"):
        if line:
            try:
                data = json.loads(line)
                print(json.dumps(data, ensure_ascii=False, indent=2))
            except:
                print(line)

    if stderr:
        print("\n=== STDERR ===")
        print(stderr.decode())


if __name__ == "__main__":
    asyncio.run(publish_via_mcp())