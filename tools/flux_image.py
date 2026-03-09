#!/usr/bin/env python
"""
阿里云百炼 Flux 图像生成工具

支持阿里云百炼平台的 Flux 模型进行图像生成。
FLUX.1-merged 结合了 DEV 的深度特性和 Schnell 的高速执行优势。
"""
import asyncio
import httpx
import json
import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
from PIL import Image


# API 配置
FLUX_API_KEY = "sk-e3504f36c29043119c58f6a9c4079656"


async def generate_with_bailian_flux(prompt: str, save_path: str = None) -> bytes:
    """
    使用阿里云百炼 Flux 模型生成图片

    文档: https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api
    """
    # 可能的 API 端点
    endpoints = [
        {
            "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            "model": "flux-schnell"
        },
        {
            "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            "model": "FLUX.1-schnell"
        },
        {
            "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            "model": "flux-merged"
        },
        {
            "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/images/generations",
            "model": "flux-schnell"
        }
    ]

    headers = {
        "Authorization": f"Bearer {FLUX_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        for endpoint in endpoints:
            url = endpoint["url"]
            model = endpoint["model"]

            print(f"\n   🎨 尝试模型: {model}")
            print(f"   端点: {url}")

            # 请求数据格式1: 标准格式
            data_formats = [
                # 格式1: 标准格式
                {
                    "model": model,
                    "input": {
                        "prompt": prompt
                    },
                    "parameters": {
                        "size": "1024*1024",
                        "n": 1
                    }
                },
                # 格式2: 简化格式
                {
                    "model": model,
                    "prompt": prompt,
                    "size": "1024x1024",
                    "n": 1
                },
                # 格式3: OpenAI 兼容格式
                {
                    "model": model,
                    "prompt": prompt,
                    "size": "1024x1024",
                    "response_format": "url"
                }
            ]

            for i, data in enumerate(data_formats):
                try:
                    print(f"   尝试格式 {i+1}...")

                    # 对于异步任务，添加 header
                    headers_with_async = headers.copy()
                    headers_with_async["X-DashScope-Async"] = "enable"

                    response = await client.post(url, headers=headers_with_async, json=data, timeout=60)

                    print(f"   状态码: {response.status_code}")
                    result = response.json()

                    if response.status_code == 200:
                        # 检查是否是异步任务
                        if "output" in result and "task_id" in result["output"]:
                            task_id = result["output"]["task_id"]
                            print(f"   ✅ 任务创建成功: {task_id}")

                            # 轮询获取结果
                            image_data = await poll_for_result(client, task_id, save_path)
                            if image_data:
                                return image_data

                        # 检查是否直接返回结果
                        elif "output" in result and "results" in result["output"]:
                            results = result["output"]["results"]
                            if results and "url" in results[0]:
                                image_url = results[0]["url"]
                                print(f"   ✅ 图片生成成功!")

                                img_response = await client.get(image_url)
                                image_data = img_response.content

                                if save_path:
                                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                                    with open(save_path, "wb") as f:
                                        f.write(image_data)

                                return image_data

                        # 检查 data 字段（OpenAI 格式）
                        elif "data" in result:
                            if result["data"] and "url" in result["data"][0]:
                                image_url = result["data"][0]["url"]
                                print(f"   ✅ 图片生成成功!")

                                img_response = await client.get(image_url)
                                image_data = img_response.content

                                if save_path:
                                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                                    with open(save_path, "wb") as f:
                                        f.write(image_data)

                                return image_data

                        print(f"   响应: {json.dumps(result, ensure_ascii=False)[:200]}")

                    elif response.status_code == 400:
                        print(f"   错误: {result.get('message', result.get('error', 'Unknown'))}")

                    elif response.status_code == 401:
                        print(f"   认证失败: {result.get('message', 'Invalid API key')}")

                    else:
                        print(f"   响应: {json.dumps(result, ensure_ascii=False)[:200]}")

                except Exception as e:
                    print(f"   异常: {str(e)[:100]}")

    return None


async def poll_for_result(client: httpx.AsyncClient, task_id: str, save_path: str = None) -> bytes:
    """轮询异步任务结果"""
    status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

    headers = {
        "Authorization": f"Bearer {FLUX_API_KEY}"
    }

    for i in range(60):
        await asyncio.sleep(3)

        response = await client.get(status_url, headers=headers)
        result = response.json()

        task_status = result.get("output", {}).get("task_status", "UNKNOWN")

        if task_status == "SUCCEEDED":
            results = result.get("output", {}).get("results", [])
            if results:
                image_url = results[0].get("url")
                print(f"   ✅ 图片生成成功! (等待 {(i+1)*3} 秒)")

                img_response = await client.get(image_url)
                image_data = img_response.content

                if save_path:
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(image_data)

                return image_data

        elif task_status == "FAILED":
            print(f"   ❌ 任务失败: {result}")
            return None

        elif task_status in ["PENDING", "RUNNING"]:
            if (i + 1) % 10 == 0:
                print(f"   等待中... {(i+1)*3}秒 状态: {task_status}")

    print(f"   ⚠️ 任务超时")
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


async def generate_cover(prompt: str, save_path: str = None) -> bytes:
    """生成封面图片"""
    print("=" * 60)
    print("🎨 阿里云百炼 Flux 图像生成")
    print("=" * 60)
    print(f"\n提示词: {prompt[:100]}...")

    image_data = await generate_with_bailian_flux(prompt, save_path)

    if image_data:
        print(f"\n✅ 原始图片生成成功! ({len(image_data)} bytes)")

        # 调整为微信封面尺寸
        resized_data = resize_for_wechat(image_data)

        if save_path:
            resized_path = save_path.replace('.jpg', '_weixin.jpg')
            with open(resized_path, "wb") as f:
                f.write(resized_data)
            print(f"✅ 微信封面已保存: {resized_path}")

        return resized_data

    return None


async def main():
    prompt = """
Professional cover image for AI Agent research paper newsletter.
Modern, clean, minimalist design with abstract neural network visualization.
Blue and white color scheme with subtle gradients.
Technology-themed background with geometric patterns.
High quality, professional, suitable for social media cover.
"""

    image_data = await generate_cover(
        prompt=prompt.strip(),
        save_path="storage/cover_flux.jpg"
    )

    if image_data:
        print(f"\n🎉 封面图片生成完成!")
    else:
        print(f"\n❌ 封面图片生成失败")


if __name__ == "__main__":
    asyncio.run(main())