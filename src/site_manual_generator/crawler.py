"""网页爬虫模块。

基于 Playwright 实现，支持 JavaScript 渲染页面的爬取，
并将页面内容转换为干净的 Markdown 格式。
"""
from __future__ import annotations

import asyncio
import re
import urllib.parse
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright, Browser, Page

from .config import CrawlerConfig
from .models import PageContent, SiteStructure


class SiteCrawler:
    """网站爬虫。

    从指定 URL 开始，广度优先爬取站内页面，提取正文内容并转换为 Markdown。
    """

    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.config = config or CrawlerConfig()
        self.output_dir = output_dir or Path("./output")
        self.screenshot_dir = self.output_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._visited: set[str] = set()
        self._pages: list[PageContent] = []
        self._base_domain: str = ""
        self._browser: Optional[Browser] = None
        self._context = None  # 浏览器上下文（保存登录态）

    async def _manual_login(self, url: str) -> None:
        """打开有头浏览器，让用户手动登录。

        用户在浏览器中完成登录后，在控制台按回车，
        爬虫会带着登录态继续爬取。
        """
        # 创建持久化上下文（保存 cookies/localStorage）
        self._context = await self._browser.new_context(
            user_agent=self.config.user_agent,
            viewport={"width": 1440, "height": 900},
        )
        page = await self._context.new_page()

        print("\n" + "=" * 60)
        print("🔐 手动登录模式")
        print("=" * 60)
        print(f"正在打开：{url}")
        print("请在打开的浏览器窗口中完成登录操作。")
        print("登录完成后，回到这里按回车键继续...")
        print("=" * 60 + "\n")

        await page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout)

        # 等待用户确认（在异步线程里等待输入）
        import sys
        await asyncio.to_thread(sys.stdin.readline)

        print("✅ 登录确认，继续爬取...\n")

    async def crawl(self, url: str) -> SiteStructure:
        """爬取整个网站，返回结构化结果。

        Args:
            url: 起始 URL

        Returns:
            SiteStructure: 网站结构与所有页面内容
        """
        self._base_domain = urlparse(url).netloc
        self._visited.clear()
        self._pages.clear()

        # 手动登录模式强制使用有头浏览器
        headless = self.config.headless and not self.config.manual_login

        async with async_playwright() as p:
            self._browser = await p.chromium.launch(headless=headless)

            try:
                # 如果启用手动登录，先让用户登录
                if self.config.manual_login:
                    await self._manual_login(url)

                # BFS 爬取
                queue: list[tuple[str, int]] = [(url, 0)]

                while queue and len(self._pages) < self.config.max_pages:
                    current_url, depth = queue.pop(0)

                    if depth > self.config.max_depth:
                        continue

                    normalized = self._normalize_url(current_url)
                    if normalized in self._visited:
                        continue
                    if not self._is_internal(current_url):
                        continue
                    if self._is_excluded(current_url):
                        continue

                    self._visited.add(normalized)

                    page_content = await self._crawl_page(current_url, depth)
                    if page_content.status == "success":
                        self._pages.append(page_content)

                        # 提取链接加入队列（从页面 HTML 中提取的所有链接）
                        if depth < self.config.max_depth:
                            for link in page_content.links:
                                normalized_link = self._normalize_url(link)
                                if normalized_link not in self._visited:
                                    queue.append((link, depth + 1))
            finally:
                await self._browser.close()
                self._browser = None

        # 构建网站结构
        structure = self._build_structure(url)
        return structure

    async def _crawl_page(self, url: str, depth: int) -> PageContent:
        """爬取单个页面。"""
        try:
            # 如果有共享上下文（如手动登录模式），复用它以保持登录态
            if self._context is not None:
                context = self._context
                page = await context.new_page()
            else:
                context = await self._browser.new_context(  # type: ignore[union-attr]
                    user_agent=self.config.user_agent,
                )
                page = await context.new_page()

            page.set_default_timeout(self.config.timeout)

            await page.goto(url, wait_until=self.config.wait_until)

            # 等待页面稳定
            await page.wait_for_timeout(1500)

            # 自动关闭弹窗（Cookie、登录提示、广告等）
            await self._dismiss_popups(page)

            title = await page.title()
            html_content = await page.content()

            # 提取正文
            soup = BeautifulSoup(html_content, "html.parser")

            # 移除不需要的元素
            for element in soup.select("script, style, noscript, iframe, svg"):
                element.decompose()

            # 尝试找到主要内容区域
            main_content = soup.find("main") or soup.find("article") or soup.find(
                "div", class_=re.compile(r"(content|main|article)", re.I)
            )
            if main_content is None:
                main_content = soup.body or soup

            # 转换为 Markdown
            content_md = md(
                str(main_content),
                heading_style="ATX",
                strip=["a", "img"],
            )
            content_md = re.sub(r"\n{3,}", "\n\n", content_md).strip()

            # 纯文本
            content_text = main_content.get_text(separator="\n", strip=True)
            content_text = re.sub(r"\n{3,}", "\n\n", content_text).strip()

            # 截图（所有页面都截，内容更丰富）
            screenshot_path: Optional[str] = None
            try:
                safe_name = re.sub(r"[^\w\-]", "_", urlparse(url).path.strip("/")) or "index"
                # 加上深度和序号避免重名
                safe_name = f"{depth}_{safe_name}_{len(self._pages)}"
                screenshot_file = self.screenshot_dir / f"{safe_name}.png"

                # 截图前再清一遍弹窗（有些弹窗延迟出现）
                await self._clean_all_popups(page)

                await page.screenshot(path=str(screenshot_file), full_page=True)
                screenshot_path = str(screenshot_file)
            except Exception:
                pass  # 截图失败不影响主流程

            # 从 HTML 中提取所有站内链接（包括导航栏、侧边栏等）
            page_links = self._extract_links_from_html(html_content, url)

            # 共享上下文（手动登录模式）不关闭，保持登录态
            if self._context is None:
                await context.close()
            else:
                await page.close()

            return PageContent(
                url=url,
                title=title,
                content_markdown=content_md,
                content_text=content_text,
                depth=depth,
                screenshot_path=screenshot_path,
                status="success",
                links=page_links,
            )

        except Exception as e:
            return PageContent(
                url=url,
                title="",
                content_markdown="",
                content_text="",
                depth=depth,
                status="failed",
                error_message=str(e),
            )

    async def _dismiss_popups(self, page: Page) -> None:
        """尝试自动关闭页面上的弹窗（温柔版：点关闭按钮）。

        策略（依次尝试）：
        1. 按 ESC 键
        2. 点击常见的关闭按钮
        """
        try:
            # 1. 先按 ESC
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            # 2. 点击常见的关闭按钮/链接
            close_selectors = [
                'button[aria-label*="close" i]',
                'button[aria-label*="关闭"]',
                'button.close',
                '.close-btn',
                '.close-button',
                '.popup-close',
                '.modal-close',
                '[class*="close" i][role="button"]',
                'button:has-text("×")',
                'button:has-text("✕")',
                'button:has-text("✖")',
                'button:has-text("Accept")',
                'button:has-text("接受")',
                'button:has-text("同意")',
                'button:has-text("Got it")',
                'button:has-text("知道了")',
                'button:has-text("我知道了")',
                'button:has-text("确认")',
                'button:has-text("确定")',
                '.cookie-popup button',
                '.cookie-banner button',
                '.gdpr button',
            ]

            for selector in close_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        is_visible = await el.is_visible()
                        if is_visible:
                            await el.click(timeout=1000)
                            await page.wait_for_timeout(200)
                except Exception:
                    continue

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)

        except Exception:
            pass

    async def _clean_all_popups(self, page: Page) -> None:
        """暴力清除所有弹窗/遮罩（截图前调用）。

        用 JS 直接移除常见的弹窗元素，确保截图干净。
        """
        try:
            await page.evaluate("""() => {
                // 1. 移除所有 fixed 定位的遮罩层（overlay / mask / backdrop）
                const overlaySelectors = [
                    '.modal-overlay', '.modal-mask', '.modal-backdrop',
                    '.popup-overlay', '.popup-mask',
                    '.dialog-overlay', '.dialog-mask',
                    '.mask', '.overlay', '.backdrop',
                    '[class*="overlay" i]', '[class*="mask" i]', '[class*="backdrop" i]',
                    '[class*="modal" i][style*="fixed"]',
                    '[class*="popup" i][style*="fixed"]',
                    '[class*="dialog" i][style*="fixed"]',
                ];

                overlaySelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' && style.zIndex > 100) {
                            el.remove();
                        }
                    });
                });

                // 2. 移除常见的弹窗容器
                const popupSelectors = [
                    '.modal', '.popup', '.dialog', '.modal-content',
                    '.cookie-banner', '.cookie-popup', '.gdpr-banner',
                    '.subscribe-popup', '.newsletter-popup',
                    '.login-modal', '.register-modal',
                    '.advertisement', '.ad-banner', '.ad-popup',
                    '[class*="Modal" i]', '[class*="Popup" i]', '[class*="Dialog" i]',
                    '[class*="cookie" i][class*="banner" i]',
                    '[class*="promotion" i]', '[class*="promo" i]',
                ];

                popupSelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' || style.position === 'absolute') {
                            if (style.zIndex > 100 || style.display === 'block' || style.display === 'flex') {
                                el.remove();
                            }
                        }
                    });
                });

                // 3. 移除 body 上的 overflow: hidden（弹窗锁住滚动条的情况）
                document.body.style.overflow = '';
                document.documentElement.style.overflow = '';

                // 4. 移除所有 role="dialog" 的元素
                document.querySelectorAll('[role="dialog"]').forEach(el => {
                    const parent = el.parentElement;
                    if (parent && parent.classList.contains('MuiModal-root')) {
                        parent.remove();
                    } else {
                        el.remove();
                    }
                });
            }""")
            await page.wait_for_timeout(300)

        except Exception:
            pass  # 失败不影响截图

    def _extract_links(self, markdown: str, base_url: str) -> list[str]:
        """从 Markdown 内容中提取链接（保留备用）。"""
        links: list[str] = []
        pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(pattern, markdown):
            link_url = match.group(2)
            if link_url.startswith("#") or link_url.startswith("mailto:"):
                continue
            absolute_url = urljoin(base_url, link_url)
            if self._is_internal(absolute_url) and not self._is_excluded(absolute_url):
                links.append(absolute_url)
        return links

    def _extract_links_from_html(self, html: str, base_url: str) -> list[str]:
        """从 HTML 中提取所有站内链接（包括导航栏、侧边栏、正文等）。"""
        links: list[str] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                # 跳过锚点、邮件、JS、外链
                if not href or href.startswith("#"):
                    continue
                if href.startswith("mailto:") or href.startswith("javascript:"):
                    continue
                if href.startswith("http") and not self._is_internal(href):
                    continue
                # 转换为绝对链接
                absolute_url = urljoin(base_url, href)
                # 去掉锚点部分（# 后面的），避免重复
                normalized = absolute_url.split("#")[0].rstrip("/")
                if self._is_internal(absolute_url) and not self._is_excluded(absolute_url):
                    if normalized not in links:
                        links.append(normalized)
        except Exception:
            pass
        return links

    def _is_internal(self, url: str) -> bool:
        """判断是否为站内链接。"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self._base_domain
        except Exception:
            return False

    def _is_excluded(self, url: str) -> bool:
        """判断 URL 是否在排除列表中。"""
        for pattern in self.config.exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _normalize_url(self, url: str) -> str:
        """规范化 URL，用于去重。"""
        parsed = urlparse(url)
        # 移除 fragment，统一小写域名
        normalized = urllib.parse.urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                parsed.params,
                parsed.query,
                "",  # 移除 fragment
            )
        )
        return normalized

    def _build_structure(self, base_url: str) -> SiteStructure:
        """从爬取结果构建网站结构。"""
        if not self._pages:
            return SiteStructure(base_url=base_url)

        # 首页信息
        home_page = self._pages[0]
        site_name = home_page.title or urlparse(base_url).netloc

        # 提取导航项（从首页内容中分析）
        nav_items = self._extract_nav_items(home_page.content_markdown)

        # 简单分类：按 URL 路径的第一级目录
        categories: set[str] = set()
        for page in self._pages:
            path = urlparse(page.url).path.strip("/")
            if path:
                first_level = path.split("/")[0]
                categories.add(first_level)

        return SiteStructure(
            base_url=base_url,
            site_name=site_name,
            description=home_page.content_text[:200] if home_page.content_text else "",
            total_pages=len(self._pages),
            pages=self._pages,
            nav_items=nav_items,
            categories=sorted(list(categories)),
        )

    def _extract_nav_items(self, markdown: str) -> list[str]:
        """从首页 Markdown 中提取可能的导航项。"""
        items: list[str] = []
        # 提取所有链接文本
        pattern = r"\[([^\]]+)\]\([^)]+\)"
        for match in re.finditer(pattern, markdown):
            text = match.group(1).strip()
            # 过滤掉太短或太长的，以及明显不是导航的
            if 2 <= len(text) <= 20 and text not in items:
                items.append(text)
        # 取前 15 个作为候选导航
        return items[:15]


def crawl_site(url: str, config: Optional[CrawlerConfig] = None) -> SiteStructure:
    """同步入口：爬取网站。

    Args:
        url: 起始 URL
        config: 爬虫配置

    Returns:
        SiteStructure: 网站结构
    """
    return asyncio.run(SiteCrawler(config).crawl(url))
