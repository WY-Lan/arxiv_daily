#!/usr/bin/env python
"""
生成高质量封面图片

当 AI 图像生成不可用时，创建专业的自定义封面。
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
from io import BytesIO
from pathlib import Path


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
            if random.random() > 0.7:  # 30%概率连线
                draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 50), width=1)

    return nodes


def create_professional_cover(title: str, subtitle: str, output_path: str = None):
    """
    创建专业的封面图片

    Args:
        title: 主标题
        subtitle: 副标题
        output_path: 输出路径

    Returns:
        图片字节数据
    """
    width, height = 900, 500

    # 创建渐变背景
    img = create_gradient_background(
        width, height,
        color1=(26, 115, 232),   # 蓝色顶部
        color2=(13, 71, 161)     # 深蓝色底部
    )

    draw = ImageDraw.Draw(img)

    # 添加神经网络装饰
    random.seed(42)  # 固定随机种子，保持一致
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

    # 绘制标题背景（半透明）
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

    # 标题阴影
    draw.text((text_x + 2, text_y + 2), title, fill=(0, 0, 0, 128), font=title_font)
    # 标题正文
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


def main():
    print("生成专业封面图片...")

    image_data = create_professional_cover(
        title="AI Agent 论文推荐",
        subtitle="每日精选高质量论文",
        output_path="storage/cover.jpg"
    )

    print(f"✅ 封面图片已生成 ({len(image_data)} bytes)")
    print(f"   保存路径: storage/cover.jpg")


if __name__ == "__main__":
    main()