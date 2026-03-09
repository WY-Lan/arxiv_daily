#!/usr/bin/env python
"""
测试阿里云百炼的图像生成模型
"""
import asyncio
import httpx
import json


BAILIAN_API_KEY = "sk-sp-5470bc325b4c45b789d703884c5ae09f"


async def test_model(model_name: str):
    """测试单个模型"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"

    headers = {
        "Authorization": f"Bearer {BAILIAN_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }

    data = {
        "model": model_name,
        "input": {
            "prompt": "A beautiful sunset over the ocean"
        },
        "parameters": {
            "size": "1024*1024",
            "n": 1
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        print(f"\n测试模型: {model_name}")
        print("-" * 40)

        response = await client.post(url, headers=headers, json=data)
        result = response.json()

        print(f"状态码: {response.status_code}")

        if "output" in result and "task_id" in result["output"]:
            print(f"✅ 模型可用! 任务ID: {result['output']['task_id']}")
            return True
        elif "code" in result:
            print(f"❌ 错误: {result.get('code')} - {result.get('message', '')[:100]}")
        else:
            print(f"响应: {json.dumps(result, ensure_ascii=False)[:200]}")

        return False


async def main():
    print("=" * 60)
    print("测试阿里云百炼图像生成模型")
    print("=" * 60)

    # 测试多个模型名称
    models = [
        "qwen-image-2.0-pro",
        "wanx-v1",
        "wanx-v2",
        "flux-schnell",
        "flux.1-schnell",
    ]

    available = []

    for model in models:
        if await test_model(model):
            available.append(model)

    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    if available:
        print(f"✅ 可用模型: {', '.join(available)}")
    else:
        print("❌ 没有可用的图像生成模型")
        print("\n请检查:")
        print("1. 登录 https://bailian.console.aliyun.com")
        print("2. 查看已开通的模型")
        print("3. 确认模型名称")


if __name__ == "__main__":
    asyncio.run(main())