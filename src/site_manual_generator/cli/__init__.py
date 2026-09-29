"""CLI 命令行入口。

使用 Typer 构建交互式命令行工具。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..config import AppConfig, CrawlerConfig, LLMConfig, OutputConfig
from ..pipeline import ManualPipeline

app = typer.Typer(
    name="smg",
    help="Site Manual Generator - 自动生成网站操作手册",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


@app.command()
def generate(
    url: str = typer.Argument(..., help="目标网站 URL"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="输出文件路径"),
    language: str = typer.Option("zh-CN", "-l", "--language", help="输出语言"),
    max_pages: int = typer.Option(30, "--max-pages", help="最大爬取页面数"),
    max_depth: int = typer.Option(3, "--max-depth", help="最大爬取深度"),
    provider: str = typer.Option("openai", "--provider", help="LLM 提供商: openai/ollama/deepseek/qwen"),
    model: str = typer.Option("gpt-4o-mini", "--model", help="模型名称"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API Key"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API 基础地址"),
    interactive: bool = typer.Option(False, "-i", "--interactive", help="交互式模式"),
    headless: bool = typer.Option(True, "--headless/--show-browser", help="是否无头模式"),
    login: bool = typer.Option(False, "--login", help="启用手动登录模式（打开浏览器让你手动登录）"),
):
    """生成网站操作手册。"""

    # 欢迎信息
    console.print(
        Panel.fit(
            "[bold blue]Site Manual Generator[/bold blue]\n"
            "[dim]自动生成网站操作手册[/dim]",
            border_style="blue",
        )
    )

    # 构建配置：只传用户显式指定的参数，让未指定的参数从环境变量/.env读取
    llm_kwargs = {}
    if provider != "openai":
        llm_kwargs["provider"] = provider
    if model != "gpt-4o-mini":
        llm_kwargs["model"] = model
    if api_key is not None:
        llm_kwargs["api_key"] = api_key
    if base_url is not None:
        llm_kwargs["base_url"] = base_url
    llm_config = LLMConfig(**llm_kwargs)

    crawler_kwargs = {}
    if max_pages != 30:
        crawler_kwargs["max_pages"] = max_pages
    if max_depth != 3:
        crawler_kwargs["max_depth"] = max_depth
    if not headless:
        crawler_kwargs["headless"] = headless
    if login:
        crawler_kwargs["manual_login"] = True
        crawler_kwargs["headless"] = False  # 登录模式强制有头
    crawler_config = CrawlerConfig(**crawler_kwargs)

    output_kwargs = {}
    if language != "zh-CN":
        output_kwargs["language"] = language
    output_config = OutputConfig(**output_kwargs)
    config = AppConfig(llm=llm_config, crawler=crawler_config, output=output_config)

    pipeline = ManualPipeline(config)

    async def run():
        # 交互式模式
        if interactive:
            return await _run_interactive(pipeline, url, output)

        # 非交互式：直接完整生成
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: 爬取网站
            task = progress.add_task("[cyan]正在爬取网站...", total=None)
            site_structure = await pipeline.crawl_site(url)
            progress.update(
                task,
                description=f"[green]✓ 爬取完成（{site_structure.total_pages} 个页面）",
            )

            # Step 2: 生成大纲
            task = progress.add_task("[cyan]正在生成手册大纲...", total=None)
            outline = await pipeline.generate_outline(site_structure)
            progress.update(task, description="[green]✓ 大纲生成完成")

            # Step 3: 生成内容
            task = progress.add_task("[cyan]正在撰写手册内容...", total=None)
            full_outline = await pipeline.generate_content(site_structure, outline)
            progress.update(task, description="[green]✓ 内容生成完成")

            # Step 4: 配图 + 标注
            task = progress.add_task("[cyan]正在配图并生成标注...", total=None)
            pipeline.add_screenshots_and_annotations(site_structure, full_outline)
            progress.update(task, description="[green]✓ 配图与标注完成")

            # Step 5: 生成 DOCX
            task = progress.add_task("[cyan]正在生成 DOCX 文档...", total=None)
            output_path = pipeline.generate_docx(full_outline, output)
            progress.update(task, description="[green]✓ DOCX 生成完成")

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]🎉 手册生成完成！[/bold green]\n\n"
                f"📄 文件路径：[cyan]{output_path}[/cyan]\n"
                f"📊 页面数：{site_structure.total_pages}\n"
                f"📝 章节数：{len(outline.sections)}",
                border_style="green",
            )
        )

        return output_path

    asyncio.run(run())


async def _run_interactive(
    pipeline: ManualPipeline,
    url: str,
    output: Optional[str],
) -> Path:
    """交互式生成流程。"""

    # Step 1: 爬取
    console.print("\n[bold cyan]第 1 步：爬取网站[/bold cyan]")
    with console.status("[cyan]正在爬取网站..."):
        site_structure = await pipeline.crawl_site(url)

    console.print(f"  [green]✓[/green] 爬取完成，共 {site_structure.total_pages} 个页面")
    console.print(f"  [green]✓[/green] 网站名称：{site_structure.site_name}")

    # 显示发现的功能模块
    table = Table(title="发现的功能模块/导航", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("名称")
    for i, item in enumerate(site_structure.nav_items[:15], 1):
        table.add_row(str(i), item)
    console.print(table)

    # 让用户选择重点模块
    console.print("\n[dim]请输入要重点关注的模块编号（用逗号分隔，直接回车表示全部）：[/dim]")
    selection = typer.prompt("选择", default="")

    focus_areas = None
    if selection.strip():
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(",")]
            focus_areas = [
                site_structure.nav_items[i]
                for i in indices
                if 0 <= i < len(site_structure.nav_items)
            ]
            console.print(f"  [green]✓[/green] 已选择 {len(focus_areas)} 个重点模块")
        except ValueError:
            console.print("  [yellow]⚠[/yellow] 输入格式有误，将包含全部模块")

    # Step 2: 生成大纲
    console.print("\n[bold cyan]第 2 步：生成手册大纲[/bold cyan]")
    with console.status("[cyan]正在生成大纲..."):
        outline = await pipeline.generate_outline(site_structure, focus_areas)

    console.print(f"  [green]✓[/green] 大纲标题：{outline.title}")

    # 显示大纲
    console.print("\n[bold]手册大纲：[/bold]")
    for section in outline.sections:
        console.print(f"  📌 {section.title}")
        for child in section.children[:5]:
            console.print(f"     └─ {child.title}")
        if len(section.children) > 5:
            console.print(f"     └─ ...（还有 {len(section.children) - 5} 个子章节）")

    # 确认是否继续
    if not typer.confirm("\n是否继续生成完整内容？", default=True):
        console.print("[yellow]已取消。[/yellow]")
        raise typer.Exit(0)

    # Step 3: 生成内容
    console.print("\n[bold cyan]第 3 步：生成完整内容[/bold cyan]")
    with console.status("[cyan]AI 正在撰写手册内容，请稍候..."):
        full_outline = await pipeline.generate_content(site_structure, outline)
    console.print("  [green]✓[/green] 内容生成完成")

    # Step 4: 生成 DOCX
    console.print("\n[bold cyan]第 4 步：生成 DOCX 文档[/bold cyan]")
    with console.status("[cyan]正在生成 Word 文档..."):
        output_path = pipeline.generate_docx(full_outline, output)
    console.print(f"  [green]✓[/green] 文档已生成：{output_path}")

    console.print()
    console.print(
        Panel.fit(
            "[bold green]🎉 全部完成！[/bold green]\n\n"
            f"📄 文件：[cyan]{output_path}[/cyan]",
            border_style="green",
        )
    )

    return output_path


@app.command()
def crawl(
    url: str = typer.Argument(..., help="目标网站 URL"),
    max_pages: int = typer.Option(30, "--max-pages", help="最大爬取页面数"),
    max_depth: int = typer.Option(3, "--max-depth", help="最大爬取深度"),
    output_dir: str = typer.Option("./output", "--output-dir", help="输出目录"),
):
    """仅爬取网站，查看网站结构。"""
    from ..crawler import SiteCrawler
    from ..config import CrawlerConfig

    config = CrawlerConfig(max_pages=max_pages, max_depth=max_depth)
    crawler = SiteCrawler(config, Path(output_dir))

    console.print(f"[cyan]开始爬取：[/cyan]{url}")

    async def run():
        structure = await crawler.crawl(url)
        return structure

    structure = asyncio.run(run())

    table = Table(title="爬取结果", show_header=True, header_style="bold magenta")
    table.add_column("属性")
    table.add_column("值")
    table.add_row("网站名称", structure.site_name)
    table.add_row("页面总数", str(structure.total_pages))
    table.add_row("功能分类", ", ".join(structure.categories[:10]))
    console.print(table)

    console.print("\n[bold]页面列表：[/bold]")
    for i, page in enumerate(structure.pages[:20], 1):
        console.print(f"  {i:2d}. [{page.depth}] {page.title} - {page.url}")

    if structure.total_pages > 20:
        console.print(f"\n  ... 还有 {structure.total_pages - 20} 个页面")


@app.command()
def version():
    """显示版本信息。"""
    from .. import __version__

    console.print(f"Site Manual Generator v{__version__}")


def main():
    """CLI 入口函数。"""
    app()


if __name__ == "__main__":
    main()
