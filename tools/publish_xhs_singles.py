"""
为每篇已选中论文生成单篇小红书深度解读并发布（5+1 中的「5」）
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from loguru import logger

from config.settings import settings
from config.prompts import load_prompt
from storage.database import db
from tools.llm_client import get_llm_client


MCP_URL = "http://localhost:18060/mcp"


async def init_mcp_session() -> str:
    """初始化 MCP 会话，返回 session_id"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "arxiv-daily-singles", "version": "1.0"}
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            MCP_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            session_id = resp.headers.get("mcp-session-id")
            if not session_id:
                raise RuntimeError("MCP 服务未返回 session_id，请确认 xiaohongshu-mcp 已在 18060 端口运行")
            logger.info(f"MCP session: {session_id}")
            return session_id


async def publish_via_mcp(session_id: str, title: str, content: str, images: list, tags: list) -> str:
    """调用 MCP publish_content 发布内容，返回结果文本"""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "publish_content",
            "arguments": {
                "title": title,
                "content": content,
                "images": images,
                "tags": tags,
                "is_original": False
            }
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            MCP_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "mcp-session-id": session_id
            },
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            result = await resp.json()

    if "error" in result:
        raise RuntimeError(f"MCP 错误: {result['error']}")

    content_list = result.get("result", {}).get("content", [])
    return content_list[0].get("text", "") if content_list else ""


async def generate_single_content(llm_client, paper: dict) -> dict:
    """用 LLM 为单篇论文生成小红书内容"""
    prompt_template = load_prompt("xhs_single_paper")

    messages = [
        {"role": "system", "content": prompt_template},
        {"role": "user", "content": f"""请为以下论文生成小红书深度解读笔记：

标题：{paper['title']}
作者：{paper['authors']}
摘要：{paper['abstract']}
arxiv链接：{paper.get('abs_url', '')}
"""}
    ]

    result = await llm_client.generate_json(
        messages=messages,
        model=settings.MODEL_PUBLISHER,
        temperature=0.7
    )
    return result


async def main():
    await db.init()
    llm_client = get_llm_client()

    # 获取已选中论文
    papers = await db.get_selected_papers()
    if not papers:
        logger.error("没有已选中的论文")
        return

    logger.info(f"共 {len(papers)} 篇论文需要发布")

    results = []
    for i, paper in enumerate(papers, 1):
        p = paper._asdict()
        arxiv_id = p["arxiv_id"]
        title = p["title"]

        logger.info(f"\n[{i}/{len(papers)}] 处理: {arxiv_id} - {title[:50]}")

        # 1. 生成内容
        logger.info("  生成小红书内容...")
        try:
            content = await generate_single_content(llm_client, p)
        except Exception as e:
            logger.error(f"  内容生成失败: {e}")
            results.append({"arxiv_id": arxiv_id, "status": "failed", "error": str(e)})
            continue

        xhs_title = content.get("title", title[:20])
        xhs_body = content.get("content", "")
        xhs_tags = content.get("tags", ["#AI论文", "#Agent", "#大模型"])

        # 标题限制 20 字
        if len(xhs_title) > 20:
            xhs_title = xhs_title[:20]

        logger.info(f"  标题: {xhs_title}")

        # 2. 确定图片（论文 PDF 封面截图，最多取所有页）
        images = []
        covers_dir = settings.STORAGE_DIR / "covers"

        # 优先用多页截图（arxiv_id_page_1.png, _page_2.png ...）
        page_imgs = sorted([
            str(covers_dir / f)
            for f in os.listdir(covers_dir)
            if f.startswith(f"{arxiv_id}_page_") and f.endswith(".png")
        ])
        if page_imgs:
            images = page_imgs[:18]  # 小红书最多 18 张
        else:
            # 退一步：单页封面
            single = covers_dir / f"{arxiv_id}.png"
            if single.exists():
                images = [str(single)]
            else:
                fallback = settings.STORAGE_DIR / "cover_fallback.jpg"
                if fallback.exists():
                    images = [str(fallback)]

        if not images:
            logger.warning(f"  无可用图片，跳过 {arxiv_id}")
            results.append({"arxiv_id": arxiv_id, "status": "skipped", "error": "no images"})
            continue

        logger.info(f"  使用 {len(images)} 张图片")

        # 3. 发布（每篇都重新建 session，确保新建 Chrome 实例）
        logger.info("  初始化新 MCP session...")
        try:
            session_id = await init_mcp_session()
        except Exception as e:
            logger.error(f"  MCP session 初始化失败: {e}")
            results.append({"arxiv_id": arxiv_id, "status": "failed", "error": str(e)})
            break

        logger.info("  发布到小红书...")
        try:
            result_text = await publish_via_mcp(session_id, xhs_title, xhs_body, images, xhs_tags)
            if "发布失败" in result_text or "没有找到" in result_text:
                logger.error(f"  发布失败: {result_text}")
                results.append({"arxiv_id": arxiv_id, "status": "failed", "error": result_text})
            else:
                logger.success(f"  ✓ 发布成功: {result_text[:100]}")
                results.append({"arxiv_id": arxiv_id, "status": "success", "title": xhs_title})
        except Exception as e:
            logger.error(f"  发布失败: {e}")
            results.append({"arxiv_id": arxiv_id, "status": "failed", "error": str(e)})

        # 每篇之间等待，避免触发限流
        if i < len(papers):
            logger.info("  等待 10 秒再发下一篇...")
            await asyncio.sleep(10)

    # 汇总
    print("\n" + "="*50)
    print("发布结果汇总：")
    for r in results:
        status = "✓" if r["status"] == "success" else "✗"
        print(f"  {status} {r['arxiv_id']}: {r.get('title', r.get('error', ''))}")
    success = sum(1 for r in results if r["status"] == "success")
    print(f"\n共发布 {success}/{len(papers)} 篇")


if __name__ == "__main__":
    asyncio.run(main())
