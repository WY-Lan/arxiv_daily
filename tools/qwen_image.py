#!/usr/bin/env python
"""
阿里云百炼图像生成工具

使用 qwen-image-2.0-pro 模型生成高质量封面图片。
"""
import asyncio
import httpx
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from PIL import Image


# API 配置 - 使用百炼 LLM API Key
BAILIAN_API_KEY = "sk-sp-5470bc325b4c45b789d703884c5ae09f"
BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"


async def generate_image_with_qwen(
    prompt: str,
    model: str = "wanx-v1",
    size: str = "1024*1024",
    save_path: str = None
) -> bytes:
    """
    使用阿里云百炼生成图像

    Args:
        prompt: 图像描述
        model: 模型名称 (wanx-v1, wanx-v2, 等)
        size: 图像尺寸
        save_path: 保存路径

    Returns:
        图像字节数据
    """
    headers = {
        "Authorization": f"Bearer {BAILIAN_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }

    data = {
        "model": model,
        "input": {
            "prompt": prompt
        },
        "parameters": {
            "size": size,
            "n": 1,
            "style": "<auto>"
        }
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        print(f"   🎨 正在生成图片...")
        print(f"   模型: {model}")
        print(f"   提示词: {prompt[:80]}...")

        response = await client.post(BAILIAN_BASE_URL, headers=headers, json=data)
        result = response.json()

        if "code" in result and result["code"] != "Success":
            print(f"   ❌ 请求失败: {result.get('message', result)}")
            return None

        if "output" not in result:
            print(f"   ⚠️ 响应异常: {result}")
            return None

        task_id = result["output"].get("task_id")
        if not task_id:
            print(f"   ⚠️ 未获取任务ID: {result}")
            return None

        print(f"   ✅ 任务已创建: {task_id}")

        # 轮询结果
        status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

        for i in range(60):
            await asyncio.sleep(3)

            status_response = await client.get(status_url, headers={
                "Authorization": f"Bearer {BAILIAN_API_KEY}"
            })
            status_result = status_response.json()

            task_status = status_result.get("output", {}).get("task_status", "UNKNOWN")

            if task_status == "SUCCEEDED":
                results = status_result.get("output", {}).get("results", [])
                if results:
                    image_url = results[0].get("url")
                    print(f"   ✅ 图片生成成功! (耗时 {(i+1)*3} 秒)")

                    img_response = await client.get(image_url)
                    image_data = img_response.content

                    if save_path:
                        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                        with open(save_path, "wb") as f:
                            f.write(image_data)
                        print(f"   图片已保存: {save_path}")

                    return image_data

            elif task_status == "FAILED":
                msg = status_result.get("output", {}).get("message", "未知错误")
                print(f"   ❌ 生成失败: {msg}")
                return None

            elif task_status in ["PENDING", "RUNNING"]:
                if (i + 1) % 5 == 0:
                    print(f"   等待中... {(i+1)*3}秒 状态: {task_status}")

        print(f"   ⚠️ 生成超时")
        return None


def resize_for_wechat(image_data: bytes, width: int = 900, height: int = 500) -> bytes:
    """将图片调整为微信公众号封面尺寸"""
    img = Image.open(BytesIO(image_data))

    target_ratio = width / height
    current_ratio = img.width / img.height

    if current_ratio > target_ratio:
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    img = img.resize((width, height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)

    return buffer.getvalue()


async def generate_cover_for_paper(
    paper_title: str = "",
    topic: str = "AI Agent",
    save_path: str = None
) -> bytes:
    """
    为论文生成封面图片

    Args:
        paper_title: 论文标题
        topic: 论文主题
        save_path: 保存路径

    Returns:
        微信封面尺寸的图片数据
    """
    prompt = f"""
A professional and elegant cover image for an academic research paper about {topic}.
Design elements:
- Modern minimalist style with clean lines
- Abstract neural network or AI-themed visualization
- Blue and white color palette with subtle gradients
- Professional technology-themed background
- Suitable for social media cover image
- High quality, 4K resolution
{f"Related to: {paper_title[:50]}" if paper_title else ""}
"""

    print("=" * 60)
    print("🎨 阿里云百炼图像生成")
    print("=" * 60)

    # 尝试不同的模型
    models_to_try = [
        "wanx-v1",           # 通义万相 v1
        "wanx-v2",           # 通义万相 v2
        "wanx-sketch-to-image-v1",  # 草图生图
    ]

    for model in models_to_try:
        print(f"\n📌 尝试模型: {model}")

        image_data = await generate_image_with_qwen(
            prompt=prompt.strip(),
            model=model,
            size="1024*1024",
            save_path=save_path
        )

        if image_data:
            # 调整为微信封面尺寸
            resized_data = resize_for_wechat(image_data)

            if save_path:
                resized_path = save_path.replace('.jpg', '_weixin.jpg')
                with open(resized_path, "wb") as f:
                    f.write(resized_data)
                print(f"\n✅ 微信封面已保存: {resized_path}")

            return resized_data

    print("\n❌ 所有模型尝试失败")
    return None


async def main():
    image_data = await generate_cover_for_paper(
        paper_title="Multi-Agent System for Autonomous Task Planning",
        topic="AI Agent, Machine Learning",
        save_path="storage/cover_qwen.jpg"
    )

    if image_data:
        print(f"\n🎉 封面图片生成完成! ({len(image_data)} bytes)")
    else:
        print("\n❌ 封面图片生成失败")


if __name__ == "__main__":
    asyncio.run(main())