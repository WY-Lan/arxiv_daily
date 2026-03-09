#!/usr/bin/env python
"""
微信公众号草稿创建完整测试
- 使用高质量封面图片
- 添加正确的底部信息
"""
import asyncio
import httpx
import json
import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw, ImageFont
import random


# 微信公众号凭证
APP_ID = "wx756a64cb5127a7b5"
APP_SECRET = "e2075f234a5d919e66d88cde89ade740"


# ============ 封面图片生成 ============

def create_gradient_background(width, height, color1, color2):
    """创建渐变背景"""
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        r = int(color1[0] + (color2[0] - color1[0]) * y / height)
        g = int(color1[1] + (color2[1] - color1[1]) * y / height)
        b = int(color1[2] + (color2[2] - color1[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return img


def draw_network_nodes(draw, width, height, num_nodes=20):
    """绘制神经网络节点"""
    nodes = []
    for _ in range(num_nodes):
        x = random.randint(50, width - 50)
        y = random.randint(50, height - 50)
        r = random.randint(3, 8)
        alpha = random.randint(100, 200)
        nodes.append((x, y, r, alpha))

        # 绘制节点光晕
        for i in range(3):
            glow_r = r + i * 3
            glow_alpha = alpha - i * 30
            if glow_alpha > 0:
                draw.ellipse(
                    [x - glow_r, y - glow_r, x + glow_r, y + glow_r],
                    fill=(255, 255, 255, glow_alpha)
                )

    # 绘制连接线
    for i, (x1, y1, _, _) in enumerate(nodes):
        for x2, y2, _, _ in nodes[i+1:]:
            if random.random() > 0.7:
                draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 50), width=1)

    return nodes


def create_professional_cover(title: str, subtitle: str, output_path: str = None):
    """创建专业的封面图片"""
    width, height = 900, 500

    # 创建渐变背景
    img = create_gradient_background(
        width, height,
        color1=(26, 115, 232),
        color2=(13, 71, 161)
    )

    draw = ImageDraw.Draw(img)

    # 添加神经网络装饰
    random.seed(42)
    draw_network_nodes(draw, width, height, num_nodes=25)

    # 添加装饰线条
    for i in range(5):
        y = height - 50 - i * 20
        alpha = 255 - i * 40
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, alpha // 3), width=1)

    # 加载字体
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 56)
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 28)
        small_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 18)
    except:
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 56)
            subtitle_font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 28)
            small_font = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 18)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = title_font
            small_font = title_font

    # 绘制标题背景
    title_bg_height = 180
    draw.rectangle(
        [(0, height // 2 - title_bg_height // 2 - 20),
         (width, height // 2 + title_bg_height // 2 + 20)],
        fill=(0, 0, 0, 80)
    )

    # 绘制主标题
    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = height // 2 - 70

    draw.text((text_x + 2, text_y + 2), title, fill=(0, 0, 0, 128), font=title_font)
    draw.text((text_x, text_y), title, fill=(255, 255, 255), font=title_font)

    # 绘制副标题
    bbox2 = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    text_width2 = bbox2[2] - bbox2[0]
    text_x2 = (width - text_width2) // 2
    text_y2 = height // 2 + 30

    draw.text((text_x2, text_y2), subtitle, fill=(200, 230, 255), font=subtitle_font)

    # 添加装饰元素
    draw.rectangle([(50, height // 2 - 90), (55, height // 2 + 70)], fill=(255, 255, 255))
    draw.rectangle([(width - 55, height // 2 - 90), (width - 50, height // 2 + 70)], fill=(255, 255, 255))

    # 底部标签
    bottom_text = "arXiv Daily · AI Agent Research"
    bbox3 = draw.textbbox((0, 0), bottom_text, font=small_font)
    text_width3 = bbox3[2] - bbox3[0]
    draw.text(
        ((width - text_width3) // 2, height - 35),
        bottom_text,
        fill=(180, 200, 220),
        font=small_font
    )

    # 保存
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)
    image_data = buffer.getvalue()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)

    return image_data


# ============ 微信 API ============

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
        "type": "thumb"
    }

    files = {
        "media": (filename, image_data, "image/jpeg")
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, params=params, files=files)
        return response.json()


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

    # 2. 生成封面图片
    print("\n2️⃣ 生成封面图片...")
    image_data = create_professional_cover(
        title="AI Agent 论文推荐",
        subtitle="每日精选高质量论文",
        output_path="storage/cover.jpg"
    )
    print(f"✅ 封面图片已生成 ({len(image_data)} bytes)")

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

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    article = {
        "title": "【测试】AI Agent 论文推荐系统",
        "author": "arxiv_daily",
        "digest": "每日精选 AI Agent 领域高质量论文，助您紧跟前沿研究动态。",
        "content": f"""
<section style="padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa;">
<div style="max-width: 100%; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">

<!-- 头部 -->
<div style="background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%); padding: 30px; text-align: center;">
<h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600;">
🤖 AI Agent 论文推荐系统
</h1>
<p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">
每日精选 · 高质量论文 · 前沿研究
</p>
</div>

<!-- 内容区 -->
<div style="padding: 30px;">

<h2 style="color: #1a73e8; font-size: 22px; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #e8f0fe;">
📋 系统功能
</h2>
<ul style="line-height: 2.2; color: #333; font-size: 16px; padding-left: 20px;">
<li><strong>自动获取</strong> - 每日从 arxiv 获取最新论文</li>
<li><strong>智能筛选</strong> - 多维度评估筛选高质量论文</li>
<li><strong>内容生成</strong> - 自动生成结构化摘要</li>
<li><strong>多平台推送</strong> - 支持 Notion、飞书、微信等</li>
</ul>

<h2 style="color: #1a73e8; font-size: 22px; margin: 30px 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #e8f0fe;">
📊 四维评估体系
</h2>
<table style="width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px;">
<tr style="background: #1a73e8; color: white;">
<td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">评估维度</td>
<td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">权重</td>
<td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">数据来源</td>
</tr>
<tr style="background: #f8f9fa;">
<td style="padding: 12px; border: 1px solid #ddd;">📈 引用数量</td>
<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">25%</td>
<td style="padding: 12px; border: 1px solid #ddd;">Semantic Scholar</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #ddd;">👤 作者影响力</td>
<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">25%</td>
<td style="padding: 12px; border: 1px solid #ddd;">OpenAlex</td>
</tr>
<tr style="background: #f8f9fa;">
<td style="padding: 12px; border: 1px solid #ddd;">🤖 内容质量</td>
<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">30%</td>
<td style="padding: 12px; border: 1px solid #ddd;">AI 评估</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #ddd;">🔥 社区热度</td>
<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">20%</td>
<td style="padding: 12px; border: 1px solid #ddd;">Papers with Code</td>
</tr>
</table>

<h2 style="color: #1a73e8; font-size: 22px; margin: 30px 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #e8f0fe;">
✅ 测试结果
</h2>
<p style="font-size: 16px; line-height: 1.8; color: #333;">
如果您看到这篇文章，说明微信公众号集成配置成功！
</p>

<div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 20px 0; border-radius: 4px;">
<p style="margin: 0; color: #2e7d32; font-size: 14px;">
<strong>🎉 集成状态：</strong>
</p>
<ul style="margin: 10px 0 0 0; padding-left: 20px; color: #333; font-size: 14px;">
<li>✅ arxiv 论文获取</li>
<li>✅ Notion 数据库同步</li>
<li>✅ 微信公众号草稿创建</li>
<li>⏳ 飞书群消息推送（待配置）</li>
<li>⏳ 小红书内容生成（待配置）</li>
</ul>
</div>

</div>

<!-- 底部 -->
<div style="background: #f5f5f5; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
<p style="color: #999; font-size: 14px; margin: 0;">
本文由 <strong style="color: #1a73e8;">AI Agent 论文推荐系统</strong> 自动生成
</p>
<p style="color: #bbb; font-size: 12px; margin: 8px 0 0 0;">
生成时间：{current_time}
</p>
</div>

</div>
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