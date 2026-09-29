"""数据模型定义。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PageContent(BaseModel):
    """单个页面的爬取结果。"""

    url: str = Field(description="页面 URL")
    title: str = Field(default="", description="页面标题")
    content_markdown: str = Field(default="", description="Markdown 格式的正文内容")
    content_text: str = Field(default="", description="纯文本内容")
    depth: int = Field(default=0, description="爬取深度")
    screenshot_path: Optional[str] = Field(default=None, description="截图文件路径")
    crawled_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="success", description="爬取状态: success / failed / skipped")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    links: list[str] = Field(default_factory=list, description="页面上提取到的站内链接")


class SiteStructure(BaseModel):
    """网站结构分析结果。"""

    base_url: str = Field(description="网站根 URL")
    site_name: str = Field(default="", description="网站名称")
    description: str = Field(default="", description="网站描述")
    total_pages: int = Field(default=0, description="总页面数")
    pages: list[PageContent] = Field(default_factory=list, description="所有页面内容")
    nav_items: list[str] = Field(default_factory=list, description="主导航项目")
    categories: list[str] = Field(default_factory=list, description="功能分类")


class AnnotationInfo(BaseModel):
    """截图上的一个标注。"""

    type: str = Field(default="number", description="标注类型: number(编号) / box(框) / arrow(箭头) / text(文字)")
    x: float = Field(default=0, description="标注位置 X（百分比 0-100）")
    y: float = Field(default=0, description="标注位置 Y（百分比 0-100）")
    text: str = Field(default="", description="标注文字/编号")
    description: str = Field(default="", description="说明文字")
    color: str = Field(default="red", description="颜色: red / yellow / green / blue")
    end_x: Optional[float] = Field(default=None, description="箭头终点 X（百分比）")
    end_y: Optional[float] = Field(default=None, description="箭头终点 Y（百分比）")
    width: float = Field(default=15, description="框宽度（百分比）")
    height: float = Field(default=8, description="框高度（百分比）")
    target_element: str = Field(default="", description="目标元素描述，如'右上角登录按钮'")


class ManualSection(BaseModel):
    """手册中的一个章节。"""

    title: str = Field(description="章节标题")
    level: int = Field(default=1, description="章节层级: 1=一级标题, 2=二级, 以此类推")
    content: str = Field(default="", description="章节内容（Markdown 格式）")
    children: list["ManualSection"] = Field(default_factory=list, description="子章节")
    screenshot: Optional[str] = Field(default=None, description="章节配图路径")
    screenshot_page_url: Optional[str] = Field(default=None, description="截图对应的页面 URL")
    annotations: list[AnnotationInfo] = Field(default_factory=list, description="截图上的标注列表")
    annotated_screenshot: Optional[str] = Field(default=None, description="加了标注的截图路径")


class ManualOutline(BaseModel):
    """手册大纲。"""

    title: str = Field(description="手册标题")
    site_name: str = Field(description="网站名称")
    site_url: str = Field(description="网站 URL")
    language: str = Field(default="zh-CN", description="语言")
    generated_at: datetime = Field(default_factory=datetime.now)
    sections: list[ManualSection] = Field(default_factory=list, description="所有章节")
    summary: str = Field(default="", description="手册摘要")
