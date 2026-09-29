"""DOCX 文档生成模块。

将手册大纲转换为格式精美的 Word 文档（.docx）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from .models import ManualOutline, ManualSection


# ─── 颜色常量 ───────────────────────────────────────────────
COLOR_H1 = RGBColor(0x1F, 0x4E, 0x79)      # 深蓝
COLOR_H2 = RGBColor(0x2E, 0x75, 0xB6)      # 中蓝
COLOR_H3 = RGBColor(0x44, 0x72, 0xC4)      # 浅蓝
COLOR_H4 = RGBColor(0x5B, 0x9B, 0xD5)      # 更浅蓝
COLOR_BODY = RGBColor(0x33, 0x33, 0x33)     # 正文深灰
COLOR_MUTED = RGBColor(0x88, 0x88, 0x88)    # 辅助浅灰
COLOR_CODE = RGBColor(0xC7, 0x25, 0x4E)     # 代码红
COLOR_ACCENT = RGBColor(0x00, 0x78, 0xD4)   # 强调蓝


class DocxGenerator:
    """DOCX 文档生成器。"""

    def __init__(self) -> None:
        self.doc = Document()
        self._setup_page()
        self._setup_styles()

    def _setup_page(self) -> None:
        """设置页面边距。"""
        for section in self.doc.sections:
            section.top_margin = Cm(2.54)
            section.bottom_margin = Cm(2.54)
            section.left_margin = Cm(2.8)
            section.right_margin = Cm(2.8)

    def _setup_styles(self) -> None:
        """设置文档默认样式。"""
        # 默认正文字体
        style = self.doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        style.font.color.rgb = COLOR_BODY
        style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        # 正文行距 1.5 倍
        pf = style.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = Pt(6)
        pf.space_before = Pt(0)

        # ── 标题 1：大号 + 底部蓝色装饰线 ──
        h1 = self.doc.styles["Heading 1"]
        h1.font.name = "Calibri"
        h1.font.size = Pt(24)
        h1.font.bold = True
        h1.font.color.rgb = COLOR_H1
        h1.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        h1.paragraph_format.space_before = Pt(24)
        h1.paragraph_format.space_after = Pt(12)
        # 加底部边框线
        pPr = h1.element.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "12")
        bottom.set(qn("w:space"), "6")
        bottom.set(qn("w:color"), "2E75B6")
        pBdr.append(bottom)
        pPr.append(pBdr)

        # ── 标题 2：中号，左竖线装饰 ──
        h2 = self.doc.styles["Heading 2"]
        h2.font.name = "Calibri"
        h2.font.size = Pt(17)
        h2.font.bold = True
        h2.font.color.rgb = COLOR_H2
        h2.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        h2.paragraph_format.space_before = Pt(18)
        h2.paragraph_format.space_after = Pt(8)
        # 左边框装饰
        pPr = h2.element.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "18")
        left.set(qn("w:space"), "8")
        left.set(qn("w:color"), "2E75B6")
        pBdr.append(left)
        pPr.append(pBdr)
        # 左缩进
        h2.paragraph_format.left_indent = Pt(10)

        # ── 标题 3：稍小，加粗 ──
        h3 = self.doc.styles["Heading 3"]
        h3.font.name = "Calibri"
        h3.font.size = Pt(14)
        h3.font.bold = True
        h3.font.color.rgb = COLOR_H3
        h3.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        h3.paragraph_format.space_before = Pt(12)
        h3.paragraph_format.space_after = Pt(6)

        # ── 标题 4：更小，斜体加粗 ──
        h4 = self.doc.styles["Heading 4"]
        h4.font.name = "Calibri"
        h4.font.size = Pt(12)
        h4.font.bold = True
        h4.font.italic = True
        h4.font.color.rgb = COLOR_H4
        h4.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        h4.paragraph_format.space_before = Pt(8)
        h4.paragraph_format.space_after = Pt(4)

    # ═══════════════════════════════════════════════════════
    #  主入口
    # ═══════════════════════════════════════════════════════

    def generate(self, outline: ManualOutline, output_path: Path) -> Path:
        """生成 DOCX 文档。"""
        self._add_cover_page(outline)
        self._add_toc(outline)

        # 正文
        for i, section in enumerate(outline.sections, 1):
            self._add_section(section, str(i), heading_level=1)
        self._add_footer(outline)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(output_path))
        return output_path

    # ═══════════════════════════════════════════════════════
    #  封面
    # ═══════════════════════════════════════════════════════

    def _add_cover_page(self, outline: ManualOutline) -> None:
        """添加封面页。"""
        for _ in range(5):
            self.doc.add_paragraph()

        # 装饰线
        line_para = self.doc.add_paragraph()
        line_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line_para.add_run("━" * 30)
        run.font.color.rgb = COLOR_ACCENT
        run.font.size = Pt(12)

        # 主标题
        title_para = self.doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_para.paragraph_format.space_before = Pt(20)
        title_para.paragraph_format.space_after = Pt(8)
        run = title_para.add_run(outline.title)
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = COLOR_H1

        # 副标题
        subtitle_para = self.doc.add_paragraph()
        subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_para.paragraph_format.space_after = Pt(20)
        run = subtitle_para.add_run(f"{outline.site_name} 操作指南")
        run.font.size = Pt(16)
        run.font.color.rgb = COLOR_MUTED

        # 装饰线
        line_para2 = self.doc.add_paragraph()
        line_para2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line_para2.add_run("━" * 30)
        run.font.color.rgb = COLOR_ACCENT
        run.font.size = Pt(12)

        # 空行
        for _ in range(6):
            self.doc.add_paragraph()

        # 网站信息
        info_para = self.doc.add_paragraph()
        info_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = info_para.add_run(f"官方网站：{outline.site_url}")
        run.font.size = Pt(11)
        run.font.color.rgb = COLOR_MUTED

        # 生成日期
        date_para = self.doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = date_para.add_run(f"生成日期：{outline.generated_at.strftime('%Y-%m-%d')}")
        run.font.size = Pt(11)
        run.font.color.rgb = COLOR_MUTED

        self.doc.add_page_break()

    # ═══════════════════════════════════════════════════════
    #  目录
    # ═══════════════════════════════════════════════════════

    def _add_toc(self, outline: ManualOutline) -> None:
        """添加目录页。"""
        toc_title = self.doc.add_paragraph()
        toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        toc_title.paragraph_format.space_after = Pt(18)
        run = toc_title.add_run("目  录")
        run.font.size = Pt(22)
        run.font.bold = True
        run.font.color.rgb = COLOR_H1

        for i, section in enumerate(outline.sections, 1):
            self._add_toc_item(section, str(i), level=0)

        self.doc.add_page_break()

    def _add_toc_item(self, section: ManualSection, num_prefix: str, level: int = 0) -> None:
        """添加目录项（带编号，紧凑布局，层级缩进明显）。"""
        para = self.doc.add_paragraph()
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(2)
        para.paragraph_format.line_spacing = 1.2

        # 缩进：每级 0.5 厘米
        para.paragraph_format.left_indent = Cm(0.5 * level)

        # 编号 + 标题
        run = para.add_run(f"{num_prefix}  {section.title}")
        run.font.size = Pt(11)
        if level == 0:
            run.font.bold = True
            run.font.color.rgb = COLOR_H1
            run.font.size = Pt(12)
        elif level == 1:
            run.font.color.rgb = COLOR_H2
        else:
            run.font.color.rgb = COLOR_BODY

        for i, child in enumerate(section.children, 1):
            child_num = f"{num_prefix}.{i}"
            self._add_toc_item(child, child_num, level + 1)

    # ═══════════════════════════════════════════════════════
    #  章节
    # ═══════════════════════════════════════════════════════

    def _add_section(self, section: ManualSection, num_prefix: str = "", heading_level: int = 1) -> None:
        """添加一个章节（递归，带编号）。"""
        # 标题（带编号）
        heading_text = f"{num_prefix}  {section.title}" if num_prefix else section.title
        self.doc.add_heading(heading_text, level=heading_level)

        # 截图
        if section.screenshot and Path(section.screenshot).exists():
            try:
                self.doc.add_picture(str(section.screenshot), width=Inches(5.8))
                last_para = self.doc.paragraphs[-1]
                last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                last_para.paragraph_format.space_before = Pt(8)
                last_para.paragraph_format.space_after = Pt(2)
                # 图注
                caption = self.doc.add_paragraph()
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption.paragraph_format.space_after = Pt(12)
                run = caption.add_run(f"图：{section.title}")
                run.font.size = Pt(9)
                run.font.italic = True
                run.font.color.rgb = COLOR_MUTED
            except Exception:
                pass  # 截图失败不影响文档生成

        # 内容
        if section.content:
            self._add_markdown_content(section.content)

        # 子章节
        next_level = min(heading_level + 1, 4)
        for i, child in enumerate(section.children, 1):
            child_num = f"{num_prefix}.{i}" if num_prefix else str(i)
            self._add_section(child, child_num, next_level)

    # ═══════════════════════════════════════════════════════
    #  Markdown 解析
    # ═══════════════════════════════════════════════════════

    def _add_markdown_content(self, markdown: str) -> None:
        """将 Markdown 内容转换为 Word 段落。"""
        lines = markdown.split("\n")

        # 清理：合并连续空行
        cleaned = []
        prev_empty = False
        for line in lines:
            stripped = line.rstrip()
            if not stripped.strip():
                if not prev_empty:
                    cleaned.append("")
                prev_empty = True
            else:
                cleaned.append(stripped)
                prev_empty = False
        # 去首尾空行
        while cleaned and not cleaned[0].strip():
            cleaned.pop(0)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()

        i = 0
        while i < len(cleaned):
            line = cleaned[i]
            stripped = line.strip()

            # 空行 → 跳过（不生成空段落）
            if not stripped:
                i += 1
                continue

            # ── 表格 ──
            if "|" in stripped and i + 1 < len(cleaned) and "|" in cleaned[i + 1]:
                next_line = cleaned[i + 1].strip()
                if re.match(r"^[\s|\-:]+$", next_line) and "-" in next_line:
                    table_lines = [stripped]
                    j = i + 2
                    while j < len(cleaned) and cleaned[j].strip() and "|" in cleaned[j]:
                        table_lines.append(cleaned[j].strip())
                        j += 1
                    self._add_table(table_lines)
                    i = j
                    continue

            # ── 代码块（```）──
            if stripped.startswith("```"):
                code_lines = []
                j = i + 1
                while j < len(cleaned) and not cleaned[j].strip().startswith("```"):
                    code_lines.append(cleaned[j])
                    j += 1
                self._add_code_block("\n".join(code_lines))
                i = j + 1 if j < len(cleaned) else j
                continue

            # ── 子标题（## ### 等，转成加粗小标题）──
            if re.match(r"^#{2,6}\s", stripped):
                level = len(re.match(r"^#+", stripped).group())
                text = re.sub(r"^#{2,6}\s+", "", stripped)
                para = self.doc.add_paragraph()
                para.paragraph_format.space_before = Pt(8)
                para.paragraph_format.space_after = Pt(4)
                run = para.add_run(text)
                run.font.bold = True
                if level <= 3:
                    run.font.size = Pt(12)
                    run.font.color.rgb = COLOR_H3
                else:
                    run.font.size = Pt(11)
                    run.font.color.rgb = COLOR_H4
                i += 1
                continue

            # ── 引用 ──
            if stripped.startswith(">"):
                text = stripped.lstrip(">").strip()
                para = self.doc.add_paragraph()
                para.paragraph_format.left_indent = Cm(0.5)
                para.paragraph_format.space_before = Pt(4)
                para.paragraph_format.space_after = Pt(4)
                # 左边框
                pPr = para._p.get_or_add_pPr()
                pBdr = OxmlElement("w:pBdr")
                left = OxmlElement("w:left")
                left.set(qn("w:val"), "single")
                left.set(qn("w:sz"), "12")
                left.set(qn("w:space"), "6")
                left.set(qn("w:color"), "5B9BD5")
                pBdr.append(left)
                pPr.append(pBdr)
                run = para.add_run(f"💡 {text}")
                run.font.italic = True
                run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
                i += 1
                continue

            # ── 有序列表（手动编号，支持嵌套）──
            ol_match = re.match(r"^(\s*)(\d+)[.、)]\s+(.+)", line)
            if ol_match:
                indent_spaces = len(ol_match.group(1))
                text = ol_match.group(3)
                level = indent_spaces // 2  # 每 2 个空格算一级

                para = self.doc.add_paragraph()
                para.paragraph_format.space_after = Pt(2)
                para.paragraph_format.left_indent = Cm(0.7 + level * 0.6)
                para.paragraph_format.first_line_indent = Cm(-0.4)

                # 手动加编号
                prefix = f"{ol_match.group(2)}. "
                run = para.add_run(prefix)
                run.font.bold = True
                run.font.color.rgb = COLOR_ACCENT
                self._add_formatted_text(para, text)
                i += 1
                continue

            # ── 无序列表 ──
            ul_match = re.match(r"^(\s*)[-*+]\s+(.+)", line)
            if ul_match:
                indent_spaces = len(ul_match.group(1))
                text = ul_match.group(2)
                level = indent_spaces // 2

                para = self.doc.add_paragraph()
                para.paragraph_format.space_after = Pt(2)
                para.paragraph_format.left_indent = Cm(0.7 + level * 0.6)
                para.paragraph_format.first_line_indent = Cm(-0.4)

                bullet = "● " if level == 0 else ("○ " if level == 1 else "▪ ")
                run = para.add_run(bullet)
                run.font.color.rgb = COLOR_ACCENT
                run.font.size = Pt(9) if level > 0 else Pt(11)
                self._add_formatted_text(para, text)
                i += 1
                continue

            # ── 普通段落 ──
            para = self.doc.add_paragraph()
            para.paragraph_format.space_after = Pt(6)
            para.paragraph_format.line_spacing = 1.5
            self._add_formatted_text(para, stripped)
            i += 1

    # ═══════════════════════════════════════════════════════
    #  表格
    # ═══════════════════════════════════════════════════════

    def _add_table(self, table_lines: list[str]) -> None:
        """添加 Markdown 表格。"""
        if len(table_lines) < 2:
            return

        headers = self._parse_table_row(table_lines[0])
        rows = []
        for line in table_lines[2:]:
            rows.append(self._parse_table_row(line))

        if not headers:
            return

        # 创建表格
        table = self.doc.add_table(rows=len(rows) + 1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Light Grid Accent 1"
        table.autofit = True

        # 表头
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = ""
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(header.strip())
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        # 数据
        for row_idx, row_data in enumerate(rows):
            for col_idx, cell_text in enumerate(row_data):
                if col_idx < len(headers):
                    cell = table.rows[row_idx + 1].cells[col_idx]
                    cell.text = ""
                    para = cell.paragraphs[0]
                    para.paragraph_format.space_after = Pt(2)
                    self._add_formatted_text(para, cell_text.strip())

        # 表格后间距
        self.doc.add_paragraph()

    def _parse_table_row(self, line: str) -> list[str]:
        """解析表格行。"""
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        return [c.strip() for c in stripped.split("|")]

    # ═══════════════════════════════════════════════════════
    #  代码块
    # ═══════════════════════════════════════════════════════

    def _add_code_block(self, code: str) -> None:
        """添加代码块。"""
        para = self.doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.3)
        para.paragraph_format.space_before = Pt(4)
        para.paragraph_format.space_after = Pt(4)
        # 背景色（浅灰底）
        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F5F5F5")
        pPr.append(shd)

        run = para.add_run(code)
        run.font.name = "Consolas"
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    # ═══════════════════════════════════════════════════════
    #  行内格式
    # ═══════════════════════════════════════════════════════

    def _add_formatted_text(self, paragraph, text: str) -> None:
        """添加带格式的文本。"""
        pattern = r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))"
        parts = re.split(pattern, text)

        for part in parts:
            if not part:
                continue

            run = paragraph.add_run()

            # 粗体
            if part.startswith("**") and part.endswith("**"):
                run.text = part[2:-2]
                run.font.bold = True
            # 斜体
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                run.text = part[1:-1]
                run.font.italic = True
            # 行内代码
            elif part.startswith("`") and part.endswith("`"):
                run.text = part[1:-1]
                run.font.name = "Consolas"
                run.font.color.rgb = COLOR_CODE
                run.font.size = Pt(10)
            # 链接 [text](url)
            elif part.startswith("[") and "](" in part and part.endswith(")"):
                m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
                if m:
                    run.text = m.group(1)
                    run.font.color.rgb = COLOR_ACCENT
                    run.font.underline = True
                else:
                    run.text = part
            else:
                run.text = part

    # ═══════════════════════════════════════════════════════
    #  页脚声明
    # ═══════════════════════════════════════════════════════

    def _add_footer(self, outline: ManualOutline) -> None:
        """添加页脚说明。"""
        self.doc.add_page_break()

        footer_title = self.doc.add_paragraph()
        footer_title.paragraph_format.space_after = Pt(6)
        run = footer_title.add_run("版权声明")
        run.font.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = COLOR_H1

        line_para = self.doc.add_paragraph()
        run = line_para.add_run("─" * 40)
        run.font.color.rgb = COLOR_ACCENT
        run.font.size = Pt(10)

        footer_text = self.doc.add_paragraph()
        footer_text.paragraph_format.space_before = Pt(8)
        run = footer_text.add_run(
            "本操作手册由 Site Manual Generator 自动生成，基于网站公开信息整理，"
            "仅供学习和参考使用。手册内容可能与网站最新版本存在差异，"
            "请以官方网站最新内容为准。"
        )
        run.font.size = Pt(10)
        run.font.color.rgb = COLOR_MUTED

        source_para = self.doc.add_paragraph()
        run = source_para.add_run(f"信息来源：{outline.site_url}")
        run.font.size = Pt(10)
        run.font.color.rgb = COLOR_MUTED


def generate_docx(
    outline: ManualOutline,
    output_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """同步入口：生成 DOCX 文档。"""
    if output_path is None:
        if output_dir is None:
            output_dir = Path("./output")
        safe_name = re.sub(r"[^\w\-]", "_", outline.site_name)
        output_path = output_dir / f"{safe_name}_操作手册.docx"

    generator = DocxGenerator()
    return generator.generate(outline, output_path)
