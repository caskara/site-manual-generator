"""生成流水线：整合爬虫、分析、输出。"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Optional

from .analyzer import ManualAnalyzer
from .config import AppConfig
from .crawler import SiteCrawler
from .docx_generator import generate_docx
from .models import ManualOutline, ManualSection, SiteStructure


class ManualPipeline:
    """操作手册生成流水线。

    整合爬取 → 分析 → 配图标注 → 生成 的完整流程。
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or AppConfig.from_env()
        self.crawler = SiteCrawler(self.config.crawler, self.config.output.output_dir)
        self.analyzer = ManualAnalyzer(self.config.llm)

    async def crawl_site(self, url: str) -> SiteStructure:
        """第一步：爬取网站。"""
        return await self.crawler.crawl(url)

    async def generate_outline(
        self,
        site_structure: SiteStructure,
        focus_areas: Optional[list[str]] = None,
    ) -> ManualOutline:
        """第二步：生成手册大纲。"""
        return await self.analyzer.generate_outline(
            site_structure,
            language=self.config.output.language,
            focus_areas=focus_areas,
        )

    async def generate_content(
        self,
        site_structure: SiteStructure,
        outline: ManualOutline,
    ) -> ManualOutline:
        """第三步：生成完整内容。"""
        return await self.analyzer.generate_full_manual(site_structure, outline)

    def add_screenshots_and_annotations(
        self,
        site_structure: SiteStructure,
        outline: ManualOutline,
    ) -> ManualOutline:
        """第四步：为章节匹配合适的页面截图。

        基于章节标题与页面标题、URL 的相似度，为每个章节匹配最合适的页面截图。
        """
        self._match_screenshots(site_structure, outline)
        return outline

    def _match_screenshots(self, site_structure: SiteStructure, outline: ManualOutline) -> None:
        """为每个章节匹配最合适的页面截图。

        匹配策略（优先级从高到低）：
        1. URL 路径精确匹配（章节标题关键词出现在 URL 路径中）
        2. 页面标题精确匹配（章节标题是页面标题的子集或反之）
        3. 关键词重合度（章节和页面共享的关键词数量）
        4. 一级章节兜底用首页
        """
        pages_with_screenshots = [p for p in site_structure.pages if p.screenshot_path]

        if not pages_with_screenshots:
            return

        # 构建页面索引
        def page_keywords(page) -> set[str]:
            """提取页面关键词集合（来自标题和 URL 路径）。"""
            words: set[str] = set()
            # 标题分词（简单按中英文边界切）
            title_words = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z0-9]+", page.title.lower())
            words.update(title_words)
            # URL 路径分词
            url_path = page.url.split("?")[0].split("#")[0]
            path_parts = [p for p in url_path.split("/") if p and p not in ("http:", "https:", "")]
            for part in path_parts[-3:]:  # 取最后 3 段路径
                words.update(re.findall(r"[a-zA-Z0-9]+", part.lower()))
            return words

        page_index = [(p, page_keywords(p)) for p in pages_with_screenshots]

        def match_score(section_title: str, page, page_kw: set[str]) -> int:
            score = 0
            title_lower = section_title.lower()
            page_title_lower = page.title.lower()
            url_lower = page.url.lower()

            # 1. 完全包含（标题互相包含）
            if title_lower == page_title_lower:
                score += 100
            elif title_lower in page_title_lower or page_title_lower in title_lower:
                score += 50

            # 2. URL 路径包含章节关键词
            section_words = set(re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z0-9]+", title_lower))
            # 去掉常见无意义词
            stop_words = {"的", "和", "与", "及", "使用", "如何", "怎么", "怎样", "什么", "介绍", "功能", "说明", "指南"}
            section_words -= stop_words

            # 关键词重合度
            common = section_words & page_kw
            score += len(common) * 8

            # URL 路径命中
            url_path = url_lower.split("?")[0]
            for w in section_words:
                if len(w) >= 2 and w in url_path:
                    score += 15

            return score

        def match_section(section: ManualSection, depth: int = 0) -> None:
            best_page = None
            best_score = -1

            for page, page_kw in page_index:
                s = match_score(section.title, page, page_kw)
                if s > best_score:
                    best_score = s
                    best_page = page

            if best_page and best_score >= 15:  # 有一定匹配度才配图
                section.screenshot = best_page.screenshot_path
                section.screenshot_page_url = best_page.url
            elif depth == 0 and pages_with_screenshots:
                # 一级章节兜底：用首页或第一个页面
                home_page = pages_with_screenshots[0]
                section.screenshot = home_page.screenshot_path
                section.screenshot_page_url = home_page.url

            for child in section.children:
                match_section(child, depth + 1)

        for section in outline.sections:
            match_section(section)

    def generate_docx(
        self,
        outline: ManualOutline,
        output_filename: Optional[str] = None,
    ) -> Path:
        """第五步：生成 DOCX 文件。"""
        if output_filename:
            output_path = self.config.output.output_dir / output_filename
        else:
            output_path = None
        return generate_docx(outline, output_path=output_path)

    async def run_full(
        self,
        url: str,
        focus_areas: Optional[list[str]] = None,
        output_filename: Optional[str] = None,
    ) -> Path:
        """运行完整流水线：爬取 → 大纲 → 内容 → 配图标注 → DOCX。"""
        # 1. 爬取网站
        site_structure = await self.crawl_site(url)

        # 2. 生成大纲
        outline = await self.generate_outline(site_structure, focus_areas)

        # 3. 生成完整内容
        full_outline = await self.generate_content(site_structure, outline)

        # 4. 配图 + 标注
        self.add_screenshots_and_annotations(site_structure, full_outline)

        # 5. 生成 DOCX
        output_path = self.generate_docx(full_outline, output_filename)

        return output_path


def generate_manual(
    url: str,
    config: Optional[AppConfig] = None,
    focus_areas: Optional[list[str]] = None,
    output_filename: Optional[str] = None,
) -> Path:
    """同步入口：一键生成操作手册。"""
    pipeline = ManualPipeline(config)
    return asyncio.run(pipeline.run_full(url, focus_areas, output_filename))
