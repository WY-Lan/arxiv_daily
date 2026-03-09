#!/usr/bin/env python
"""
微信公众号素材上传和草稿创建完整测试
"""
import asyncio
import httpx
import json
import os
from datetime import datetime
from io import BytesIO


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


async def upload_image(token, image_data, filename="cover.jpg"):
    """上传图片素材"""
    url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
    params = {
        "access_token": token,
        "type": "thumb"  # 缩略图类型
    }

    files = {
        "media": (filename, image_data, "image/jpeg")
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, params=params, files=files)
        return response.json()


async def upload_img_url(token, image_url):
    """通过URL上传图片（图文消息内图片）"""
    url = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
    params = {"access_token": token}

    # 先下载图片
    async with httpx.AsyncClient(timeout=30.0) as client:
        img_response = await client.get(image_url)
        if img_response.status_code != 200:
            return {"error": "Failed to download image"}

        files = {
            "media": ("cover.jpg", img_response.content, "image/jpeg")
        }
        response = await client.post(url, params=params, files=files)
        return response.json()


def create_simple_cover_image():
    """创建一个简单的封面图片（使用纯色背景）"""
    from PIL import Image, ImageDraw, ImageFont

    # 创建 900x500 的图片（微信公众号推荐尺寸）
    width, height = 900, 500
    img = Image.new('RGB', (width, height), color='#1a73e8')  # 蓝色背景

    draw = ImageDraw.Draw(img)

    # 添加文字
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 48)
        small_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
    except:
        font = ImageFont.load_default()
        small_font = font

    # 绘制文字
    text = "AI Agent 论文推荐"
    subtitle = "每日精选高质量论文"

    # 计算文字位置（居中）
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

    # 保存到字节流
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)

    return buffer.getvalue()


async def add_draft(token, articles):
    """创建图文草稿"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/add"
    params = {"access_token": token}

    data = {"articles": articles}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, json=data)
        return response.json()


async def main():
    print("=" * 60)
    print("微信公众号草稿创建完整测试")
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

    # 2. 创建封面图片
    print("\n2️⃣ 创建封面图片...")
    try:
        image_data = create_simple_cover_image()
        print(f"✅ 封面图片创建成功 ({len(image_data)} bytes)")
    except ImportError:
        print("⚠️ PIL 未安装，使用在线图片...")
        # 使用一个在线图片作为封面
        online_image_url = "https://picsum.photos/900/500"
        img_result = await upload_img_url(access_token, online_image_url)
        if "url" in img_result:
            print(f"✅ 在线图片上传成功: {img_result['url']}")
        else:
            print(f"❌ 在线图片上传失败: {img_result}")
            return
        return
    except Exception as e:
        print(f"❌ 创建图片失败: {e}")
        return

    # 3. 上传封面图片
    print("\n3️⃣ 上传封面图片到微信...")
    upload_result = await upload_image(access_token, image_data)

    if "media_id" in upload_result:
        thumb_media_id = upload_result["media_id"]
        print(f"✅ 封面图片上传成功!")
        print(f"   Media ID: {thumb_media_id}")
    else:
        print(f"❌ 上传失败: {upload_result}")
        return

    # 4. 创建草稿
    print("\n4️⃣ 创建图文草稿...")

    article = {
        "title": "【测试】AI Agent 论文推荐系统",
        "author": "arxiv_daily",
        "digest": "每日精选 AI Agent 领域高质量论文，助您紧跟前沿研究动态。",
        "content": """
<section style="padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
<h1 style="color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">
🤖 AI Agent 论文推荐系统
</h1>

<p style="font-size: 16px; line-height: 1.8; color: #333;">
这是一个测试文章，用于验证微信公众号草稿创建功能。
</p>

<h2 style="color: #333; margin-top: 30px;">📋 系统功能</h2>
<ul style="line-height: 2; color: #555;">
<li>✅ 每日自动获取 arxiv 最新论文</li>
<li>✅ 多维度评估筛选高质量论文</li>
<li>✅ 自动生成内容摘要</li>
<li>✅ 推送到 Notion、飞书、微信等多个平台</li>
</ul>

<h2 style="color: #333; margin-top: 30px;">📊 四维评估体系</h2>
<table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
<tr style="background: #f5f5f5;">
<td style="padding: 10px; border: 1px solid #ddd;"><strong>评估维度</strong></td>
<td style="padding: 10px; border: 1px solid #ddd;"><strong>权重</strong></td>
<td style="padding: 10px; border: 1px solid #ddd;"><strong>数据来源</strong></td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #ddd;">引用数量</td>
<td style="padding: 10px; border: 1px solid #ddd;">25%</td>
<td style="padding: 10px; border: 1px solid #ddd;">Semantic Scholar</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #ddd;">作者影响力</td>
<td style="padding: 10px; border: 1px solid #ddd;">25%</td>
<td style="padding: 10px; border: 1px solid #ddd;">OpenAlex</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #ddd;">内容质量</td>
<td style="padding: 10px; border: 1px solid #ddd;">30%</td>
<td style="padding: 10px; border: 1px solid #ddd;">AI 评估</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #ddd;">社区热度</td>
<td style="padding: 10px; border: 1px solid #ddd;">20%</td>
<td style="padding: 10px; border: 1px solid #ddd;">Papers with Code</td>
</tr>
</table>

<h2 style="color: #333; margin-top: 30px;">✅ 测试结果</h2>
<p style="font-size: 16px; line-height: 1.8; color: #333;">
如果您看到这篇文章，说明微信公众号集成配置成功！
</p>

<hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;"/>
<p style="color: #999; font-size: 14px;">
<em>本文由 AI Agent 论文推荐系统自动生成</em><br/>
测试时间：""" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
</p>
</section>
""",
        "content_source_url": "https://arxiv.org",
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0
    }

    draft_result = await add_draft(access_token, [article])

    if "media_id" in draft_result:
        print(f"\n✅ 草稿创建成功!")
        print(f"   Media ID: {draft_result['media_id']}")
        print("\n" + "=" * 60)
        print("🎉 微信公众号集成测试完成!")
        print("=" * 60)
        print("""
📌 下一步操作:
   1. 登录微信公众平台: https://mp.weixin.qq.com
   2. 进入「素材管理」→「草稿箱」
   3. 查看刚创建的草稿
   4. 确认内容格式正确后手动发布
""")
    else:
        print(f"❌ 创建草稿失败: {draft_result}")


if __name__ == "__main__":
    asyncio.run(main())