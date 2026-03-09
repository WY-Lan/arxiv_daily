#!/usr/bin/env python
"""
使用阿里百炼 API 生成封面图片

支持的模型：
- wanx-v1: 通义万相（文生图）
- flux-schnell: 快速高质量图像生成
"""
import asyncio
import httpx
import json
import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path


# 阿里百炼 API 配置
BAILIAN_API_KEY = "sk-sp-5470bc325b4c45b789d703884c5ae09f"
BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"


async def generate_cover_image_with_bailian(prompt: str, save_path: str = None):
    """
    使用阿里百炼生成封面图片

    Args:
        prompt: 图像描述提示词
        save_path: 保存路径（可选）

    Returns:
        图片字节数据
    """
    headers = {
        "Authorization": f"Bearer {BAILIAN_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"  # 启用异步模式
    }

    # 请求数据
    data = {
        "model": "wanx-v1",  # 通义万相模型
        "input": {
            "prompt": prompt
        },
        "parameters": {
            "style": "<auto>",  # 自动选择风格
            "size": "1024*1024",  # 正方形尺寸，后续可裁剪
            "n": 1  # 生成1张图片
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. 发起生成请求
        print(f"   正在生成图片...")
        response = await client.post(BAILIAN_BASE_URL, headers=headers, json=data)
        result = response.json()

        if "output" not in result:
            print(f"   ⚠️ 生成请求失败: {result}")
            return None

        task_id = result["output"].get("task_id")
        if not task_id:
            print(f"   ⚠️ 未获取到任务ID: {result}")
            return None

        print(f"   任务ID: {task_id}")

        # 2. 轮询获取结果
        status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

        for i in range(30):  # 最多等待30次
            await asyncio.sleep(2)  # 等待2秒

            status_response = await client.get(status_url, headers={
                "Authorization": f"Bearer {BAILIAN_API_KEY}"
            })
            status_result = status_response.json()

            task_status = status_result.get("output", {}).get("task_status")

            if task_status == "SUCCEEDED":
                # 获取图片URL
                results = status_result.get("output", {}).get("results", [])
                if results:
                    image_url = results[0].get("url")
                    print(f"   图片生成成功!")

                    # 下载图片
                    img_response = await client.get(image_url)
                    image_data = img_response.content

                    if save_path:
                        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                        with open(save_path, "wb") as f:
                            f.write(image_data)
                        print(f"   图片已保存: {save_path}")

                    return image_data

            elif task_status == "FAILED":
                print(f"   ❌ 图片生成失败: {status_result}")
                return None

            elif task_status in ["PENDING", "RUNNING"]:
                print(f"   等待中... ({i+1}/30) 状态: {task_status}")
            else:
                print(f"   未知状态: {task_status}")

        print(f"   ⚠️ 生成超时")
        return None


async def generate_cover_with_flux(prompt: str):
    """
    使用 flux-schnell 模型生成图片（更快）

    Args:
        prompt: 图像描述

    Returns:
        图片字节数据
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"

    headers = {
        "Authorization": f"Bearer {BAILIAN_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "flux-schnell",  # 快速生成模型
        "input": {
            "prompt": prompt
        },
        "parameters": {
            "size": "1024*1024",
            "n": 1
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=data)
        result = response.json()

        # flux-schnell 可能直接返回结果或需要轮询
        if "output" in result:
            # 检查是否直接返回图片
            if "results" in result["output"]:
                results = result["output"]["results"]
                if results:
                    image_url = results[0].get("url")
                    img_response = await client.get(image_url)
                    return img_response.content

            # 需要轮询
            task_id = result["output"].get("task_id")
            if task_id:
                status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

                for i in range(30):
                    await asyncio.sleep(2)
                    status_response = await client.get(status_url, headers=headers)
                    status_result = status_response.json()

                    if status_result.get("output", {}).get("task_status") == "SUCCEEDED":
                        results = status_result.get("output", {}).get("results", [])
                        if results:
                            image_url = results[0].get("url")
                            img_response = await client.get(image_url)
                            return img_response.content

        return None


def create_fallback_cover():
    """创建备用封面图片（当 AI 生成失败时）"""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 900, 500
    img = Image.new('RGB', (width, height), color='#1a73e8')

    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 48)
        small_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
    except:
        font = ImageFont.load_default()
        small_font = font

    text = "AI Agent 论文推荐"
    subtitle = "每日精选高质量论文"

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = height // 2 - 60

    draw.text((text_x, text_y), text, fill='white', font=font)

    bbox2 = draw.textbbox((0, 0), subtitle, font=small_font)
    text_width2 = bbox2[2] - bbox2[0]
    text_x2 = (width - text_width2) // 2
    text_y2 = height // 2 + 30

    draw.text((text_x2, text_y2), subtitle, fill='white', font=small_font)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)

    return buffer.getvalue()


async def main():
    print("=" * 60)
    print("阿里百炼封面图片生成测试")
    print("=" * 60)

    # 封面图片提示词
    prompt = """
A professional and modern cover image for an AI research paper newsletter.
The image should feature:
- Abstract neural network or AI agent visualization
- Blue and white color scheme
- Technology-themed background
- Clean, professional, minimalist style
- Text space in the center
High quality, 4K resolution, suitable for social media cover.
"""

    print("\n🎨 使用阿里百炼生成封面图片...")
    print(f"   提示词: {prompt[:100]}...")

    image_data = await generate_cover_image_with_bailian(
        prompt=prompt.strip(),
        save_path="storage/cover_ai.jpg"
    )

    if image_data:
        print(f"\n✅ AI 生成封面成功! ({len(image_data)} bytes)")
        print(f"   保存路径: storage/cover_ai.jpg")
    else:
        print("\n⚠️ AI 生成失败，使用备用封面")
        fallback_data = create_fallback_cover()
        with open("storage/cover_fallback.jpg", "wb") as f:
            f.write(fallback_data)
        print(f"   备用封面已保存: storage/cover_fallback.jpg")


if __name__ == "__main__":
    asyncio.run(main())