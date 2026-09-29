"""图片标注模块。

在截图上绘制操作指引标注：编号圆圈、箭头、矩形框、文字说明等。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


# ─── 颜色常量 ───────────────────────────────────────────────
COLOR_RED = (231, 76, 60)        # 主标注色：亮红
COLOR_RED_DARK = (192, 57, 43)  # 深红（描边）
COLOR_YELLOW = (241, 196, 15)   # 高亮黄
COLOR_GREEN = (46, 204, 113)    # 绿色
COLOR_BLUE = (52, 152, 219)     # 蓝色
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_SHADOW = (0, 0, 0, 100)   # 半透明阴影


class Annotation:
    """单个标注。"""

    def __init__(
        self,
        type: str = "number",       # number | arrow | box | text
        x: int = 0,                  # 标注位置 x（百分比 0-100 或像素）
        y: int = 0,                  # 标注位置 y
        text: str = "",              # 标注文字/编号
        description: str = "",       # 说明文字
        color: str = "red",          # 颜色：red / yellow / green / blue
        end_x: Optional[int] = None, # 箭头终点 x
        end_y: Optional[int] = None, # 箭头终点 y
        width: int = 0,              # 框宽度
        height: int = 0,             # 框高度
        use_percent: bool = True,    # 是否使用百分比坐标
    ) -> None:
        self.type = type
        self.x = x
        self.y = y
        self.text = text
        self.description = description
        self.color = color
        self.end_x = end_x
        self.end_y = end_y
        self.width = width
        self.height = height
        self.use_percent = use_percent

    def _get_color(self) -> tuple:
        mapping = {
            "red": COLOR_RED,
            "yellow": COLOR_YELLOW,
            "green": COLOR_GREEN,
            "blue": COLOR_BLUE,
        }
        return mapping.get(self.color, COLOR_RED)

    def _to_px(self, val: float, img_size: int) -> int:
        """百分比转像素。"""
        if self.use_percent:
            return int(val * img_size / 100)
        return int(val)

    def draw(self, draw: ImageDraw.ImageDraw, img_w: int, img_h: int, font_small: ImageFont.FreeTypeFont, font_big: ImageFont.FreeTypeFont) -> None:
        """在图上绘制这个标注。"""
        color = self._get_color()
        x_px = self._to_px(self.x, img_w)
        y_px = self._to_px(self.y, img_h)

        if self.type == "number":
            self._draw_number(draw, x_px, y_px, font_big, color)
        elif self.type == "box":
            self._draw_box(draw, x_px, y_px, img_w, img_h, color)
        elif self.type == "arrow":
            self._draw_arrow(draw, x_px, y_px, img_w, img_h, color)
        elif self.type == "text":
            self._draw_text(draw, x_px, y_px, font_small, color)

    def _draw_number(self, draw: ImageDraw.ImageDraw, x: int, y: int, font: ImageFont.FreeTypeFont, color: tuple) -> None:
        """绘制编号圆圈。"""
        r = 22  # 半径
        # 外圈（描边）
        draw.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], fill=COLOR_WHITE, outline=COLOR_RED_DARK, width=2)
        # 内圈
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
        # 数字
        text = str(self.text) if self.text else "1"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((x - tw / 2, y - th / 2 - 2), text, fill=COLOR_WHITE, font=font)
        except Exception:
            draw.text((x - 8, y - 10), text, fill=COLOR_WHITE, font=font)

    def _draw_box(self, draw: ImageDraw.ImageDraw, x: int, y: int, img_w: int, img_h: int, color: tuple) -> None:
        """绘制矩形框。"""
        w_px = self._to_px(self.width, img_w) if self.use_percent else self.width
        h_px = self._to_px(self.height, img_h) if self.use_percent else self.height
        if w_px <= 0:
            w_px = 100
        if h_px <= 0:
            h_px = 40
        # 外发光效果（多层）
        for i in range(3, 0, -1):
            alpha_color = (*color[:3], 80) if i < 3 else (*color[:3], 255)
            # 简化：直接画多层边框
            draw.rectangle(
                [x - w_px // 2 - i, y - h_px // 2 - i, x + w_px // 2 + i, y + h_px // 2 + i],
                outline=color,
                width=2,
            )

    def _draw_arrow(self, draw: ImageDraw.ImageDraw, x: int, y: int, img_w: int, img_h: int, color: tuple) -> None:
        """绘制箭头。"""
        end_x = self._to_px(self.end_x, img_w) if self.end_x is not None else x + 80
        end_y = self._to_px(self.end_y, img_h) if self.end_y is not None else y
        # 箭身
        draw.line([(x, y), (end_x, end_y)], fill=color, width=4)
        # 箭头（三角形）
        import math
        angle = math.atan2(end_y - y, end_x - x)
        arrow_len = 18
        arrow_angle = math.pi / 6
        p1x = end_x - arrow_len * math.cos(angle - arrow_angle)
        p1y = end_y - arrow_len * math.sin(angle - arrow_angle)
        p2x = end_x - arrow_len * math.cos(angle + arrow_angle)
        p2y = end_y - arrow_len * math.sin(angle + arrow_angle)
        draw.polygon([(end_x, end_y), (p1x, p1y), (p2x, p2y)], fill=color)

    def _draw_text(self, draw: ImageDraw.ImageDraw, x: int, y: int, font: ImageFont.FreeTypeFont, color: tuple) -> None:
        """绘制文字标注（带半透明背景）。"""
        text = self.text or self.description
        if not text:
            return
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * 12, 20
        padding = 8
        # 背景框
        draw.rectangle(
            [x - padding, y - padding, x + tw + padding, y + th + padding],
            fill=(*color[:3], 230),
        )
        # 文字
        draw.text((x, y), text, fill=COLOR_WHITE, font=font)


class ImageAnnotator:
    """图片标注器。"""

    def __init__(self) -> None:
        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """获取字体（优先系统中文字体）。"""
        if size in self._font_cache:
            return self._font_cache[size]

        # 尝试常见中文字体
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",       # 微软雅黑
            "C:/Windows/Fonts/msyhbd.ttc",     # 微软雅黑粗体
            "C:/Windows/Fonts/simhei.ttf",     # 黑体
            "/System/Library/Fonts/PingFang.ttc",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
        ]
        font = None
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()

        self._font_cache[size] = font
        return font

    def annotate(
        self,
        image_path: Path,
        annotations: list[Annotation],
        output_path: Optional[Path] = None,
    ) -> Path:
        """给图片添加标注。

        Args:
            image_path: 原图路径
            annotations: 标注列表
            output_path: 输出路径（默认在原图同目录，加 _annotated 后缀）

        Returns:
            标注后的图片路径
        """
        if output_path is None:
            output_path = image_path.parent / f"{image_path.stem}_annotated{image_path.suffix}"

        # 打开图片
        img = Image.open(image_path).convert("RGBA")
        # 创建绘图层
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        img_w, img_h = img.size
        font_small = self._get_font(14)
        font_big = self._get_font(20)

        # 绘制所有标注
        for ann in annotations:
            ann.draw(draw, img_w, img_h, font_small, font_big)

        # 合并图层
        result = Image.alpha_composite(img, overlay)
        result = result.convert("RGB")

        # 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(str(output_path), quality=95)
        return output_path


def annotate_image(
    image_path: str | Path,
    annotations: list[dict],
    output_path: str | Path | None = None,
) -> str:
    """便捷函数：给图片加标注。

    Args:
        image_path: 图片路径
        annotations: 标注字典列表
        output_path: 输出路径

    Returns:
        标注后图片路径字符串
    """
    annotator = ImageAnnotator()
    ann_objs = [Annotation(**a) for a in annotations]
    result = annotator.annotate(Path(image_path), ann_objs, Path(output_path) if output_path else None)
    return str(result)
