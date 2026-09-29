"""MCP Server 模块。

通过 Model Context Protocol 暴露网站操作手册生成能力，
使任何支持 MCP 的 AI 助手（Cursor、Claude Desktop、Trae 等）都能调用。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..config import AppConfig, LLMConfig, CrawlerConfig, OutputConfig
from ..pipeline import ManualPipeline

# 创建 MCP Server
mcp_server = Server("site-manual-generator")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用的工具。"""
    return [
        Tool(
            name="generate_manual",
            description="为指定网站生成操作手册（DOCX 格式）。"
            "输入网站 URL，自动爬取网站内容并生成结构化的 Word 操作手册。",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网站的 URL，例如 https://example.com",
                    },
                    "language": {
                        "type": "string",
                        "description": "手册输出语言，默认为 zh-CN",
                        "default": "zh-CN",
                    },
                    "focus_areas": {
                        "type": "string",
                        "description": "重点关注的功能模块，用逗号分隔，留空表示全部",
                        "default": "",
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "输出文件名，例如 my_manual.docx，留空则自动生成",
                        "default": "",
                    },
                    "max_pages": {
                        "type": "number",
                        "description": "最大爬取页面数，默认 30",
                        "default": 30,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="crawl_site_only",
            description="仅爬取网站并返回网站结构信息（不生成手册）。"
            "用于了解网站有哪些功能模块，再决定是否生成完整手册。",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网站的 URL",
                    },
                    "max_pages": {
                        "type": "number",
                        "description": "最大爬取页面数，默认 20",
                        "default": 20,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="generate_from_outline",
            description="根据用户提供的大纲生成操作手册。"
            "适合用户已经知道网站结构，想要自定义手册大纲的场景。",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "网站 URL（用于爬取内容）",
                    },
                    "outline_json": {
                        "type": "string",
                        "description": "手册大纲的 JSON 字符串，格式：[{\"title\":\"章节名\",\"level\":1,\"children\":[...]}]",
                    },
                    "language": {
                        "type": "string",
                        "description": "输出语言，默认 zh-CN",
                        "default": "zh-CN",
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "输出文件名",
                        "default": "",
                    },
                },
                "required": ["url", "outline_json"],
            },
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """调用工具。"""
    if name == "generate_manual":
        return await _tool_generate_manual(arguments)
    elif name == "crawl_site_only":
        return await _tool_crawl_site(arguments)
    elif name == "generate_from_outline":
        return await _tool_generate_from_outline(arguments)
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]


async def _tool_generate_manual(arguments: dict) -> list[TextContent]:
    """generate_manual 工具实现。"""
    url = arguments.get("url", "")
    if not url:
        return [TextContent(type="text", text="错误：请提供网站 URL")]

    language = arguments.get("language", "zh-CN")
    focus_str = arguments.get("focus_areas", "")
    focus_areas = [x.strip() for x in focus_str.split(",") if x.strip()] if focus_str else None
    output_filename = arguments.get("output_filename", "") or None
    max_pages = int(arguments.get("max_pages", 30))

    # 从环境变量读取 LLM 配置
    config = _build_config(language=language, max_pages=max_pages)
    pipeline = ManualPipeline(config)

    try:
        output_path = await pipeline.run_full(
            url=url,
            focus_areas=focus_areas,
            output_filename=output_filename,
        )
        return [
            TextContent(
                type="text",
                text=f"✅ 操作手册生成成功！\n\n"
                f"📄 文件路径：{output_path.absolute()}\n"
                f"🌐 网站：{url}\n"
                f"📝 语言：{language}",
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"❌ 生成失败：{str(e)}\n\n"
                f"请检查：\n"
                f"1. 网站 URL 是否正确且可访问\n"
                f"2. LLM API Key 是否已配置（环境变量 SMG_LLM_API_KEY）\n"
                f"3. Playwright 浏览器是否已安装（运行 playwright install chromium）",
            )
        ]


async def _tool_crawl_site(arguments: dict) -> list[TextContent]:
    """crawl_site_only 工具实现。"""
    url = arguments.get("url", "")
    if not url:
        return [TextContent(type="text", text="错误：请提供网站 URL")]

    max_pages = int(arguments.get("max_pages", 20))
    config = _build_config(max_pages=max_pages)
    pipeline = ManualPipeline(config)

    try:
        structure = await pipeline.crawl_site(url)

        nav_list = "\n".join(
            f"  {i+1}. {item}" for i, item in enumerate(structure.nav_items[:20])
        )
        cat_list = "\n".join(
            f"  - {cat}" for cat in structure.categories[:15]
        )

        return [
            TextContent(
                type="text",
                text=f"🕸️ 网站爬取完成\n\n"
                f"**网站名称**：{structure.site_name}\n"
                f"**页面总数**：{structure.total_pages}\n\n"
                f"**发现的导航/功能模块**：\n{nav_list}\n\n"
                f"**功能分类**：\n{cat_list}\n\n"
                f"可以根据以上信息，调用 generate_manual 生成完整操作手册，"
                f"或指定 focus_areas 关注特定模块。",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ 爬取失败：{str(e)}")]


async def _tool_generate_from_outline(arguments: dict) -> list[TextContent]:
    """generate_from_outline 工具实现。"""
    import json

    url = arguments.get("url", "")
    outline_json = arguments.get("outline_json", "")
    language = arguments.get("language", "zh-CN")
    output_filename = arguments.get("output_filename", "") or None

    if not url or not outline_json:
        return [TextContent(type="text", text="错误：请提供 url 和 outline_json")]

    try:
        outline_data = json.loads(outline_json)
    except json.JSONDecodeError:
        return [TextContent(type="text", text="错误：outline_json 格式无效")]

    config = _build_config(language=language)
    pipeline = ManualPipeline(config)

    try:
        # 先爬取
        site_structure = await pipeline.crawl_site(url)

        # 构建自定义大纲
        from ..models import ManualOutline, ManualSection

        def build_sections(data: list[dict]) -> list[ManualSection]:
            sections = []
            for item in data:
                sections.append(
                    ManualSection(
                        title=item.get("title", "未命名"),
                        level=item.get("level", 1),
                        children=build_sections(item.get("children", [])),
                    )
                )
            return sections

        outline = ManualOutline(
            title=f"{site_structure.site_name} 操作手册",
            site_name=site_structure.site_name,
            site_url=url,
            language=language,
            sections=build_sections(outline_data),
        )

        # 生成内容
        full_outline = await pipeline.generate_content(site_structure, outline)

        # 生成 DOCX
        output_path = pipeline.generate_docx(full_outline, output_filename)

        return [
            TextContent(
                type="text",
                text=f"✅ 自定义手册生成成功！\n\n📄 文件路径：{output_path.absolute()}",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ 生成失败：{str(e)}")]


def _build_config(
    language: str = "zh-CN",
    max_pages: int = 30,
) -> AppConfig:
    """从环境变量构建配置。"""
    llm_config = LLMConfig()

    crawler_config = CrawlerConfig(
        max_pages=max_pages,
    )

    output_dir = Path(os.environ.get("SMG_OUTPUT_DIR", "./output"))
    output_config = OutputConfig(
        output_dir=output_dir,
        language=language,
    )

    return AppConfig(llm=llm_config, crawler=crawler_config, output=output_config)


async def _run_server():
    """运行 MCP Server。"""
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


def run_mcp_server():
    """同步入口：启动 MCP Server。"""
    asyncio.run(_run_server())


if __name__ == "__main__":
    run_mcp_server()
