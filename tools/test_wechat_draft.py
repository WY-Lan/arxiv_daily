#!/usr/bin/env python
"""
微信公众号草稿创建测试

测试创建图文消息草稿。
"""
import asyncio
import httpx
import json
from datetime import datetime


# 微信公众号凭证
APP_ID = "wx756a64cb5127a7b5"
APP_SECRET = "e2075f234a5d919e66d88cde89ade740"


async def get_access_token():
    """获取微信 Access Token"""
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": APP_ID,
        "secret": APP_SECRET
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        return response.json()


async def add_draft(token, articles):
    """创建图文草稿"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/add"
    params = {"access_token": token}

    data = {
        "articles": articles
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, json=data)
        return response.json()


async def get_draft_list(token, offset=0, count=10, no_content=0):
    """获取草稿列表"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/batchget"
    params = {"access_token": token}

    data = {
        "offset": offset,
        "count": count,
        "no_content": no_content
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, json=data)
        return response.json()


async def main():
    print("=" * 60)
    print("微信公众号草稿创建测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 获取 Access Token
    print("\n1️⃣ 获取 Access Token...")
    token_result = await get_access_token()

    if "access_token" not in token_result:
        print(f"❌ 获取 Token 失败: {token_result}")
        return

    access_token = token_result["access_token"]
    print(f"✅ Token 获取成功")

    # 2. 创建测试草稿
    print("\n2️⃣ 创建测试图文草稿...")

    # 测试文章内容
    test_article = {
        "title": "【测试】AI Agent 论文推荐系统",
        "author": "arxiv_daily",
        "digest": "这是一个测试文章，验证微信公众号草稿 API 是否正常工作。",
        "content": """
<h1>AI Agent 论文推荐系统测试</h1>

<p>这是一个测试文章，用于验证微信公众号草稿创建功能。</p>

<h2>系统功能</h2>
<ul>
<li>每日自动获取 arxiv 论文</li>
<li>多维度评估筛选高质量论文</li>
<li>自动生成内容摘要</li>
<li>推送到多个平台</li>
</ul>

<h2>测试结果</h2>
<p>如果您看到这篇文章，说明微信公众号集成配置成功！</p>

<hr/>
<p><em>本文由 AI Agent 论文推荐系统自动生成</em></p>
""",
        "content_source_url": "https://arxiv.org",
        "thumb_media_id": "",  # 需要先上传封面图
        "need_open_comment": 0,
        "only_fans_can_comment": 0
    }

    draft_result = await add_draft(access_token, [test_article])

    if "media_id" in draft_result:
        print(f"✅ 草稿创建成功!")
        print(f"   Media ID: {draft_result['media_id']}")

        # 3. 获取草稿列表确认
        print("\n3️⃣ 获取草稿列表...")
        list_result = await get_draft_list(access_token)

        if "item" in list_result:
            print(f"✅ 当前草稿数量: {list_result.get('total_count', 0)}")
            for item in list_result.get("item", []):
                print(f"   - {item.get('title', '无标题')} (media_id: {item.get('media_id', '')})")

        print("\n" + "=" * 60)
        print("✅ 微信公众号草稿功能测试通过!")
        print("=" * 60)
        print("""
📌 下一步:
   1. 登录微信公众平台查看草稿
   2. 确认内容格式正确
   3. 手动发布或继续开发自动发布功能
""")

    elif "errcode" in draft_result:
        errcode = draft_result["errcode"]
        errmsg = draft_result.get("errmsg", "")
        print(f"❌ 创建草稿失败!")
        print(f"   错误码: {errcode}")
        print(f"   错误信息: {errmsg}")

        # 常见错误说明
        if errcode == 40007:
            print("\n   可能原因: 需要上传封面图片 (thumb_media_id)")
            print("   解决方案: 先上传一张图片作为封面")
        elif errcode == 45009:
            print("\n   可能原因: 需要服务号权限")
        elif errcode == 40001:
            print("\n   可能原因: Access Token 无效")

    else:
        print(f"⚠️ 未知响应: {draft_result}")


if __name__ == "__main__":
    asyncio.run(main())