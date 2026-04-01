"""
PDF Image Extractor - 从论文PDF中提取关键图片

提取论文中的架构图、实验结果图等关键图片，用于小红书多图发布。
"""
import asyncio
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import httpx
import pymupdf  # PyMuPDF
from PIL import Image
from loguru import logger

from config.settings import settings


# 图片存储目录
IMAGES_DIR = settings.STORAGE_DIR / "covers"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


class ImageType(Enum):
    """图片类型分类"""
    ARCHITECTURE = "architecture"  # 模型架构图/方法示意图
    EXPERIMENT = "experiment"       # 实验结果图/对比图
    TABLE = "table"                 # 表格截图
    UNKNOWN = "unknown"             # 未分类图片


@dataclass
class ExtractedImage:
    """提取的单张图片"""
    image_bytes: bytes
    ext: str
    width: int
    height: int
    page_num: int
    xref: int
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)  # 图片在页面上的位置
    surrounding_text: str = ""  # 图片周围的文本内容
    image_type: ImageType = ImageType.UNKNOWN
    score: float = 0.0  # 图片质量评分


@dataclass
class ClassifiedImage:
    """分类后的图片"""
    extracted: ExtractedImage
    image_type: ImageType
    confidence: float  # 分类置信度
    save_path: Optional[str] = None


class PDFImageExtractor:
    """从PDF中提取图片并根据section位置分类"""

    # 图片尺寸筛选标准（针对嵌入图片）
    MIN_WIDTH = 200
    MIN_HEIGHT = 150
    MAX_WIDTH = 3000  # 提高上限，允许更大的图片
    MAX_HEIGHT = 3000

    # 宽高比限制（排除极端比例）
    MIN_RATIO = 0.2
    MAX_RATIO = 5.0

    # 页面截图尺寸标准（用于提取完整图表）
    SCREENSHOT_MIN_WIDTH = 200  # 降低最小宽度，允许更多图表
    SCREENSHOT_MIN_HEIGHT = 50  # 降低最小高度，允许宽而矮的图表

    # Section标题模式（用于判断图片所在section）
    SECTION_PATTERNS = {
        'method': [
            r'(?i)(?:\d+\.?\s*)?(method|methodology|approach|model|architecture|proposed\s+method|our\s+approach|framework|system\s+design)',
            r'(?i)(?:\d+\.?\s*)?(method\s+overview|model\s+architecture|system\s+architecture)',
        ],
        'experiments': [
            r'(?i)(?:\d+\.?\s*)?(experiment|experimental|evaluation|results?|experiments\s+and\s+results|performance)',
            r'(?i)(?:\d+\.?\s*)?(empirical\s+study|case\s+study|benchmark)',
        ],
        'introduction': [
            r'(?i)(?:\d+\.?\s*)?introduction\s*$',
        ],
        'abstract': [
            r'(?i)abstract\s*$',
        ],
        'conclusion': [
            r'(?i)(?:\d+\.?\s*)?(conclusion|conclusions|summary|discussion)',
        ],
    }

    def __init__(self, min_width: int = None, min_height: int = None):
        """初始化图片提取器"""
        self.min_width = min_width or self.MIN_WIDTH
        self.min_height = min_height or self.MIN_HEIGHT

    async def download_pdf(self, arxiv_id: str, timeout: float = 60.0) -> Optional[bytes]:
        """
        下载PDF文件

        Args:
            arxiv_id: arXiv论文ID
            timeout: 下载超时时间

        Returns:
            PDF内容bytes，失败返回None
        """
        # 处理arxiv_id格式（去掉版本号）
        clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(pdf_url, follow_redirects=True)
                response.raise_for_status()
                logger.info(f"Downloaded PDF: {arxiv_id} ({len(response.content)} bytes)")
                return response.content
        except Exception as e:
            logger.warning(f"Failed to download PDF for {arxiv_id}: {e}")
            return None

    def extract_images(self, pdf_bytes: bytes) -> List[ExtractedImage]:
        """
        从PDF中提取所有图片

        Args:
            pdf_bytes: PDF文件内容

        Returns:
            提取的图片列表
        """
        images = []

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

            for page_num, page in enumerate(doc):
                # 获取页面上的所有图片
                page_images = self._extract_images_from_page(doc, page, page_num)
                images.extend(page_images)

            doc.close()

            logger.info(f"Extracted {len(images)} images from PDF")
            return images

        except Exception as e:
            logger.error(f"Failed to extract images from PDF: {e}")
            return []

    def _extract_images_from_page(
        self,
        doc: pymupdf.Document,
        page: pymupdf.Page,
        page_num: int
    ) -> List[ExtractedImage]:
        """从单页提取所有图片"""
        images = []

        try:
            # 获取页面文本用于确定section
            page_text = page.get_text()

            # 获取页面上的图片列表
            img_list = page.get_images(full=True)

            for img_info in img_list:
                xref = img_info[0]

                try:
                    # 提取图片数据
                    base_image = doc.extract_image(xref)

                    if not base_image:
                        continue

                    image_bytes = base_image["image"]
                    ext = base_image["ext"]
                    width = base_image["width"]
                    height = base_image["height"]

                    # 尺寸筛选
                    if not self._check_image_size(width, height):
                        continue

                    # 获取图片在页面上的位置
                    bbox = self._get_image_bbox(page, xref)

                    # 获取图片周围的文本
                    surrounding_text = self._get_surrounding_text(page, bbox, page_text)

                    extracted = ExtractedImage(
                        image_bytes=image_bytes,
                        ext=ext,
                        width=width,
                        height=height,
                        page_num=page_num,
                        xref=xref,
                        bbox=bbox,
                        surrounding_text=surrounding_text,
                    )

                    images.append(extracted)

                except Exception as e:
                    logger.debug(f"Failed to extract image xref={xref}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Failed to extract images from page {page_num}: {e}")

        return images

    def _check_image_size(self, width: int, height: int) -> bool:
        """检查图片尺寸是否符合要求"""
        # 尺寸限制
        if width < self.min_width or height < self.min_height:
            return False

        if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
            return False

        # 宽高比限制
        ratio = width / height if height > 0 else 0
        if ratio < self.MIN_RATIO or ratio > self.MAX_RATIO:
            return False

        return True

    def _get_image_bbox(self, page: pymupdf.Page, xref: int) -> Tuple[float, float, float, float]:
        """获取图片在页面上的位置"""
        try:
            # 查找图片在页面上的位置
            for info in page.get_images(full=True):
                if info[0] == xref:
                    # 尝试从页面内容中定位图片位置
                    # pymupdf的get_images不直接提供位置，需要其他方法
                    pass

            # 如果找不到精确位置，返回空bbox
            return (0, 0, 0, 0)

        except Exception:
            return (0, 0, 0, 0)

    def _get_surrounding_text(
        self,
        page: pymupdf.Page,
        bbox: Tuple[float, float, float, float],
        page_text: str
    ) -> str:
        """获取图片周围的文本内容"""
        # 如果bbox有效，获取附近的文本
        if bbox[2] > 0 and bbox[3] > 0:
            try:
                # 扩展bbox范围获取周围文本
                expand = 50
                text_rect = pymupdf.Rect(
                    bbox[0] - expand,
                    bbox[1] - expand,
                    bbox[2] + expand,
                    bbox[3] + expand
                )
                surrounding = page.get_text("text", clip=text_rect)
                return surrounding[:500]  # 限制长度
            except Exception:
                pass

        # 如果无法获取周围文本，返回页面文本片段
        return page_text[:500]

    def classify_by_section(
        self,
        images: List[ExtractedImage],
        pdf_bytes: bytes
    ) -> List[ClassifiedImage]:
        """
        根据section位置对图片进行分类

        Args:
            images: 提取的图片列表
            pdf_bytes: PDF内容（用于确定section边界）

        Returns:
            分类后的图片列表
        """
        # 获取section的页面范围
        section_pages = self._get_section_page_ranges(pdf_bytes)

        classified = []

        for img in images:
            # 根据图片所在页码判断所属section
            page_num = img.page_num

            # 确定图片类型
            img_type = self._determine_image_type(page_num, section_pages, img.surrounding_text)
            confidence = self._calculate_confidence(img_type, img.surrounding_text)

            classified.append(ClassifiedImage(
                extracted=img,
                image_type=img_type,
                confidence=confidence,
            ))

        logger.info(f"Classified {len(classified)} images: "
                    f"{sum(1 for c in classified if c.image_type == ImageType.ARCHITECTURE)} architecture, "
                    f"{sum(1 for c in classified if c.image_type == ImageType.EXPERIMENT)} experiment, "
                    f"{sum(1 for c in classified if c.image_type == ImageType.UNKNOWN)} unknown")

        return classified

    def _get_section_page_ranges(self, pdf_bytes: bytes) -> Dict[str, Tuple[int, int]]:
        """
        获取各个section的页面范围

        Returns:
            Dict: section名 -> (起始页码, 结束页码)
        """
        section_pages = {}

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

            current_section = "unknown"
            section_start_page = 0

            for page_num, page in enumerate(doc):
                text = page.get_text()

                # 检查是否出现section标题
                for section_name, patterns in self.SECTION_PATTERNS.items():
                    for pattern in patterns:
                        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                            # 保存上一个section的页码范围
                            if current_section != "unknown":
                                section_pages[current_section] = (section_start_page, page_num - 1)

                            current_section = section_name
                            section_start_page = page_num
                            break

            # 保存最后一个section
            if current_section != "unknown":
                section_pages[current_section] = (section_start_page, len(doc) - 1)

            doc.close()

        except Exception as e:
            logger.warning(f"Failed to get section page ranges: {e}")

        return section_pages

    def _determine_image_type(
        self,
        page_num: int,
        section_pages: Dict[str, Tuple[int, int]],
        surrounding_text: str
    ) -> ImageType:
        """根据页码和周围文本确定图片类型"""

        # 方法1：根据section位置判断
        for section_name, (start, end) in section_pages.items():
            if start <= page_num <= end:
                if section_name == 'method':
                    return ImageType.ARCHITECTURE
                elif section_name == 'experiments':
                    return ImageType.EXPERIMENT

        # 方法2：根据周围文本关键词判断
        text_lower = surrounding_text.lower()

        # 架构图关键词
        architecture_keywords = [
            'architecture', 'framework', 'model', 'pipeline', 'overview',
            'structure', 'diagram', 'schematic', 'system', 'design',
            'flow', 'block', 'layer', 'component', 'module'
        ]

        # 实验结果关键词
        experiment_keywords = [
            'result', 'performance', 'accuracy', 'comparison', 'benchmark',
            'table', 'figure', 'plot', 'chart', 'graph', 'score',
            'metric', 'evaluation', 'baseline', 'experiment'
        ]

        # 计算关键词匹配
        arch_score = sum(1 for kw in architecture_keywords if kw in text_lower)
        exp_score = sum(1 for kw in experiment_keywords if kw in text_lower)

        if arch_score > exp_score and arch_score >= 2:
            return ImageType.ARCHITECTURE
        elif exp_score > arch_score and exp_score >= 2:
            return ImageType.EXPERIMENT

        return ImageType.UNKNOWN

    def _calculate_confidence(self, img_type: ImageType, surrounding_text: str) -> float:
        """计算分类置信度"""
        if img_type == ImageType.UNKNOWN:
            return 0.3

        # 根据关键词数量计算置信度
        text_lower = surrounding_text.lower()

        if img_type == ImageType.ARCHITECTURE:
            keywords = ['architecture', 'framework', 'model', 'diagram', 'overview']
        else:
            keywords = ['result', 'performance', 'comparison', 'table', 'figure']

        match_count = sum(1 for kw in keywords if kw in text_lower)
        confidence = min(0.5 + match_count * 0.1, 0.9)

        return confidence

    def save_images(
        self,
        classified_images: List[ClassifiedImage],
        arxiv_id: str,
        output_dir: Path = None
    ) -> List[str]:
        """
        保存图片到本地

        Args:
            classified_images: 分类后的图片列表
            arxiv_id: 论文ID（用于命名）
            output_dir: 输出目录

        Returns:
            保存的图片路径列表
        """
        output_dir = output_dir or IMAGES_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # 处理arxiv_id（去掉版本号和特殊字符）
        safe_id = arxiv_id.replace("/", "_").replace("\\", "_").split("v")[0]

        saved_paths = []

        for i, classified in enumerate(classified_images):
            try:
                # 生成文件名
                img_type_suffix = classified.image_type.value
                filename = f"{safe_id}_img_{i+1}_{img_type_suffix}.{classified.extracted.ext}"
                filepath = output_dir / filename

                # 保存图片
                with open(filepath, "wb") as f:
                    f.write(classified.extracted.image_bytes)

                classified.save_path = str(filepath)
                saved_paths.append(str(filepath))

                logger.debug(f"Saved image: {filepath}")

            except Exception as e:
                logger.warning(f"Failed to save image {i}: {e}")

        logger.info(f"Saved {len(saved_paths)} images to {output_dir}")
        return saved_paths

    def extract_figure_regions(
        self,
        pdf_bytes: bytes,
        output_dir: Path = None,
        arxiv_id: str = ""
    ) -> List[str]:
        """
        提取PDF中的完整图表区域（包括图片和legend）

        策略：定位PDF中的图片位置，扩展截图区域来包含下方的legend文本。

        Args:
            pdf_bytes: PDF文件内容
            output_dir: 输出目录
            arxiv_id: 论文ID

        Returns:
            保存的图片路径列表
        """
        output_dir = output_dir or IMAGES_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_id = arxiv_id.replace("/", "_").replace("\\", "_").split("v")[0] if arxiv_id else "unknown"

        saved_paths = []

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

            figure_count = 0
            seen_positions = set()  # 避免重复截图

            for page_num, page in enumerate(doc):
                # 获取页面上的所有图片及其位置
                img_list = page.get_images(full=True)

                for img_info in img_list:
                    xref = img_info[0]

                    try:
                        # 获取图片在页面上的位置
                        rects = page.get_image_rects(xref)
                        if not rects:
                            continue

                        img_rect = rects[0]  # 取第一个位置

                        # 检查图片尺寸是否合适
                        img_width = img_rect.width
                        img_height = img_rect.height

                        # 跳过太小的图片（可能是图标等）
                        if img_width < self.SCREENSHOT_MIN_WIDTH or img_height < self.SCREENSHOT_MIN_HEIGHT:
                            continue

                        # 跳过页面顶部的大图（通常是论文标题图，但只在第1页）
                        if page_num == 0 and img_rect.y0 < 150 and img_width > 350 and img_height > 300:
                            continue

                        # 计算扩展后的截图区域（包含legend）
                        # 向上扩展一点，向下扩展更多（legend通常在图片下方）
                        page_rect = page.rect

                        expand_top = 30  # 向上扩展
                        expand_bottom = 300  # 向下扩展，包含完整legend文本

                        clip_rect = pymupdf.Rect(
                            max(20, img_rect.x0 - 10),  # 左边距
                            max(0, img_rect.y0 - expand_top),  # 上边距
                            min(page_rect.width - 20, img_rect.x1 + 10),  # 右边距
                            min(page_rect.height, img_rect.y1 + expand_bottom)  # 下边距，包含legend
                        )

                        # 检查是否和已有截图重叠太多
                        pos_key = (int(clip_rect.x0), int(clip_rect.y0))
                        if pos_key in seen_positions:
                            continue
                        seen_positions.add(pos_key)

                        # 渲染页面区域为图片
                        mat = pymupdf.Matrix(2.0, 2.0)  # 2倍放大提高清晰度
                        pix = page.get_pixmap(matrix=mat, clip=clip_rect)

                        # 保存图片
                        figure_count += 1
                        filename = f"{safe_id}_figure_{figure_count}.png"
                        filepath = output_dir / filename
                        pix.save(str(filepath))

                        saved_paths.append(str(filepath))
                        logger.info(f"Extracted figure region (page {page_num + 1}): {filepath}")

                        # 限制提取数量
                        if figure_count >= 6:
                            break

                    except Exception as e:
                        logger.debug(f"Failed to process image {xref}: {e}")
                        continue

                if figure_count >= 6:
                    break

            doc.close()

        except Exception as e:
            logger.error(f"Failed to extract figure regions: {e}")

        logger.info(f"Extracted {len(saved_paths)} figure regions")
        return saved_paths


class ImageSelector:
    """智能选择最适合小红书的图片组合"""

    def __init__(self, max_images: int = 4):
        """
        Args:
            max_images: 最大图片数量（不包括封面）
        """
        self.max_images = max_images

    def select_images(
        self,
        classified_images: List[ClassifiedImage],
        prefer_types: List[ImageType] = [ImageType.ARCHITECTURE, ImageType.EXPERIMENT]
    ) -> List[ClassifiedImage]:
        """
        智能选择图片

        Args:
            classified_images: 分类后的图片列表
            prefer_types: 优先选择的图片类型

        Returns:
            选择的图片列表
        """
        if not classified_images:
            return []

        # 按类型分组
        by_type: Dict[ImageType, List[ClassifiedImage]] = {}
        for img in classified_images:
            if img.image_type not in by_type:
                by_type[img.image_type] = []
            by_type[img.image_type].append(img)

        # 对每组按置信度和尺寸排序
        for img_type in by_type:
            by_type[img_type].sort(
                key=lambda x: (x.confidence, x.extracted.width * x.extracted.height),
                reverse=True
            )

        selected = []

        # 策略：优先架构图，其次实验图
        # 架构图最多2张，实验图最多2张
        for prefer_type in prefer_types:
            if prefer_type in by_type:
                # 该类型最多选几张
                max_for_type = 2 if prefer_type in [ImageType.ARCHITECTURE, ImageType.EXPERIMENT] else 1

                available = by_type[prefer_type]
                take = min(len(available), max_for_type, self.max_images - len(selected))

                selected.extend(available[:take])

        # 如果还没达到最大数量，从其他类型补充
        if len(selected) < self.max_images:
            remaining = []
            for img_type, imgs in by_type.items():
                if img_type not in prefer_types:
                    remaining.extend(imgs)

            remaining.sort(
                key=lambda x: (x.confidence, x.extracted.width * x.extracted.height),
                reverse=True
            )

            take = min(len(remaining), self.max_images - len(selected))
            selected.extend(remaining[:take])

        logger.info(f"Selected {len(selected)} images: "
                    f"{sum(1 for s in selected if s.image_type == ImageType.ARCHITECTURE)} architecture, "
                    f"{sum(1 for s in selected if s.image_type == ImageType.EXPERIMENT)} experiment")

        return selected

    def get_saved_paths(self, selected_images: List[ClassifiedImage]) -> List[str]:
        """获取选中图片的保存路径"""
        paths = []
        for img in selected_images:
            if img.save_path:
                paths.append(img.save_path)
        return paths


async def extract_key_images_for_paper(
    arxiv_id: str,
    pdf_url: str = None,
    max_images: int = 18,
    output_dir: Path = None,
    prefer_full_pages: bool = True
) -> List[str]:
    """
    为单篇论文提取关键图片的便捷函数

    Args:
        arxiv_id: arXiv论文ID
        pdf_url: PDF下载链接（可选，会自动构建）
        max_images: 最大图片数量
        output_dir: 输出目录
        prefer_full_pages: 是否截取PDF所有页面作为图片

    Returns:
        保存的图片路径列表
    """
    output_dir = output_dir or IMAGES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # 下载PDF
    extractor = PDFImageExtractor()
    pdf_bytes = await extractor.download_pdf(arxiv_id)
    if not pdf_bytes:
        logger.warning(f"Failed to download PDF for {arxiv_id}")
        return []

    # 截取PDF所有页面作为图片
    if prefer_full_pages:
        logger.info(f"Extracting all pages as images for {arxiv_id}...")
        page_paths = extract_all_pages_as_images(pdf_bytes, output_dir, arxiv_id, max_images)
        return page_paths

    # 备选方案：提取嵌入图片
    selector = ImageSelector(max_images=max_images)
    images = extractor.extract_images(pdf_bytes)
    if not images:
        logger.warning(f"No images extracted from {arxiv_id}")
        return []

    classified = extractor.classify_by_section(images, pdf_bytes)
    selected = selector.select_images(classified)
    saved_paths = extractor.save_images(selected, arxiv_id, output_dir)

    return saved_paths


def extract_all_pages_as_images(
    pdf_bytes: bytes,
    output_dir: Path,
    arxiv_id: str = "",
    max_pages: int = 18
) -> List[str]:
    """
    将PDF的每一页截取为图片

    Args:
        pdf_bytes: PDF文件内容
        output_dir: 输出目录
        arxiv_id: 论文ID
        max_pages: 最大页数限制

    Returns:
        保存的图片路径列表
    """
    safe_id = arxiv_id.replace("/", "_").replace("\\", "_").split("v")[0] if arxiv_id else "unknown"
    saved_paths = []

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        total_pages = min(len(doc), max_pages)
        logger.info(f"PDF has {len(doc)} pages, will extract {total_pages}")

        for page_num in range(total_pages):
            page = doc[page_num]

            # 渲染页面为图片（2倍放大提高清晰度）
            mat = pymupdf.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)

            # 保存图片
            filename = f"{safe_id}_page_{page_num + 1}.png"
            filepath = output_dir / filename
            pix.save(str(filepath))

            saved_paths.append(str(filepath))
            logger.debug(f"Saved page {page_num + 1}: {filepath}")

        doc.close()

    except Exception as e:
        logger.error(f"Failed to extract pages: {e}")

    logger.info(f"Extracted {len(saved_paths)} pages as images")
    return saved_paths


async def main():
    """测试函数"""
    import sys

    # 测试用的arxiv ID
    test_id = "2401.00100"  # 可以替换为实际的论文ID

    print(f"\n{'='*60}")
    print(f"Testing PDF Image Extractor with {test_id}")
    print(f"{'='*60}\n")

    paths = await extract_key_images_for_paper(test_id)

    if paths:
        print(f"\n✅ Extracted and saved {len(paths)} images:")
        for p in paths:
            print(f"   {p}")
    else:
        print(f"\n❌ No images extracted")


if __name__ == "__main__":
    asyncio.run(main())