"""AI 内容分析模块。

使用 LLM 分析爬取的网站内容，生成操作手册的大纲和完整内容。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from .config import LLMConfig
from .llm_client import LLMClient
from .models import ManualOutline, ManualSection, SiteStructure


class ManualAnalyzer:
    """手册内容分析器。

    基于爬取的网站内容，使用 LLM 生成结构化操作手册。
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.llm = llm_client or LLMClient(llm_config)

    async def generate_outline(
        self,
        site_structure: SiteStructure,
        language: str = "zh-CN",
        focus_areas: Optional[list[str]] = None,
    ) -> ManualOutline:
        """生成手册大纲。

        Args:
            site_structure: 网站结构
            language: 输出语言
            focus_areas: 重点关注的功能模块

        Returns:
            手册大纲
        """
        # 准备网站信息摘要
        site_info = self._build_site_summary(site_structure)
        focus_text = ", ".join(focus_areas) if focus_areas else "全部核心功能"

        system_prompt = self._get_system_prompt(language)
        user_prompt = f"""
请根据以下网站信息，生成一份操作手册的大纲。

【网站信息】
{site_info}

【要求】
- 重点关注：{focus_text}
- 手册语言：{language}
- 结构要清晰，包含：概述、快速入门、功能详解（按模块）、常见问题、帮助支持
- 功能详解部分应根据网站实际功能划分模块
- 输出 JSON 格式，包含 title、summary、sections 数组
- ⚠️ 各章节主题要明确区分，避免内容重叠
- 一级章节 4-6 个为宜，不要太多
- 如果网站内容较少（如单页站），生成简洁的结构，不要强行拆很多章节
- ⚠️ 重要：使用嵌套 children 结构表示层级，不要用扁平数组
  - 一级章节放在顶层 sections，level=1
  - 二级章节放在一级的 children 里，level=2
  - 三级章节放在二级的 children 里，level=3
  - 最多 3 级就够了

【输出 JSON 格式示例（完整三级结构）】
{{
  "title": "XX 平台操作手册",
  "summary": "本手册介绍 XX 平台的使用方法...",
  "sections": [
    {{
      "title": "产品概述",
      "level": 1,
      "children": [
        {{ "title": "产品简介", "level": 2, "children": [] }},
        {{ "title": "核心功能", "level": 2, "children": [
          {{ "title": "功能 A", "level": 3, "children": [] }},
          {{ "title": "功能 B", "level": 3, "children": [] }}
        ]}},
        {{ "title": "适用人群", "level": 2, "children": [] }}
      ]
    }},
    {{
      "title": "快速入门",
      "level": 1,
      "children": [
        {{ "title": "注册与登录", "level": 2, "children": [] }},
        {{ "title": "首次使用指南", "level": 2, "children": [] }}
      ]
    }},
    {{
      "title": "功能详解",
      "level": 1,
      "children": [
        {{ "title": "模块一", "level": 2, "children": [] }},
        {{ "title": "模块二", "level": 2, "children": [] }}
      ]
    }},
    {{
      "title": "常见问题",
      "level": 1,
      "children": []
    }}
  ]
}}
"""

        result = await self.llm.generate_json(user_prompt, system_prompt)

        # 解析为 ManualOutline
        raw_sections = result.get("sections", [])
        # 兜底：如果是扁平结构（有 level 字段但没有正确的 children 嵌套），自动转树状
        tree_sections = self._ensure_tree_structure(raw_sections)
        outline = ManualOutline(
            title=result.get("title", f"{site_structure.site_name} 操作手册"),
            site_name=site_structure.site_name,
            site_url=site_structure.base_url,
            language=language,
            summary=result.get("summary", ""),
            sections=self._parse_sections(tree_sections),
        )

        return outline

    async def generate_full_manual(
        self,
        site_structure: SiteStructure,
        outline: ManualOutline,
    ) -> ManualOutline:
        """根据大纲生成完整手册内容。

        Args:
            site_structure: 网站结构
            outline: 手册大纲（仅有标题结构）

        Returns:
            填充了内容的完整手册大纲
        """
        site_info = self._build_site_summary(site_structure)
        system_prompt = self._get_system_prompt(outline.language)

        # 逐个章节生成内容
        for section in outline.sections:
            await self._generate_section_content(
                section, site_info, system_prompt, outline.language
            )

        return outline

    async def _generate_section_content(
        self,
        section: ManualSection,
        site_info: str,
        system_prompt: str,
        language: str,
        parent_context: str = "",
    ) -> str:
        """递归生成章节内容。返回本章节的简要摘要，用于避免子章节重复。"""
        # 生成当前章节内容
        user_prompt = f"""
请根据以下网站信息，为操作手册的「{section.title}」章节撰写详细内容。

【网站信息】
{site_info}

【当前章节】
- 章节标题：{section.title}
- 章节层级：第 {section.level} 级

【上级章节内容摘要】
{parent_context if parent_context else "(无，这是一级章节)"}

【写作要求】
- 语言：{language}
- 内容要详细、实用、有操作性
- 功能类章节要包含：功能说明、操作步骤（分点编号）、注意事项
- 概述类章节要包含：产品简介、核心功能、适用人群
- 使用 Markdown 格式，支持表格
- 字数：300-800 字（根据章节重要性调整）
- 步骤类内容用有序列表（1. 2. 3.）
- 按钮、菜单名称用【】标注
- ⚠️ 重要：不要重复上级章节已经讲过的内容，聚焦于本章节的特定主题
- 如果内容适合用表格展示，请用 Markdown 表格格式

请直接输出章节内容，不要包含章节标题本身。
"""

        content = await self.llm.generate(user_prompt, system_prompt)
        section.content = content.strip()

        # 生成简要摘要（用于子章节避免重复）
        section_summary = f"{section.title}：{section.content[:150]}..."

        # 递归生成子章节
        for child in section.children:
            child_summary = await self._generate_section_content(
                child, site_info, system_prompt, language, section_summary
            )
            section_summary += "\n" + child_summary

        return section_summary

    def _build_site_summary(self, site_structure: SiteStructure) -> str:
        """构建网站信息摘要（用于 LLM 输入）。"""
        lines = [
            f"网站名称：{site_structure.site_name}",
            f"网站地址：{site_structure.base_url}",
            f"网站描述：{site_structure.description}",
            f"爬取页面数：{site_structure.total_pages}",
            "",
            "【主要导航/功能】",
        ]
        for item in site_structure.nav_items[:20]:
            lines.append(f"- {item}")

        lines.append("")
        lines.append("【功能分类】")
        for cat in site_structure.categories[:15]:
            lines.append(f"- {cat}")

        # 添加部分页面的内容摘要
        lines.append("")
        lines.append("【页面内容摘要】")
        for page in site_structure.pages[:10]:  # 只取前 10 页
            content_preview = page.content_text[:300]
            lines.append(f"### {page.title}")
            lines.append(f"URL: {page.url}")
            lines.append(f"内容摘要: {content_preview}...")
            lines.append("")

        return "\n".join(lines)

    def _parse_sections(self, sections_data: list[dict]) -> list[ManualSection]:
        """递归解析章节数据。"""
        sections = []
        for item in sections_data:
            section = ManualSection(
                title=item.get("title", "未命名章节"),
                level=item.get("level", 1),
                content="",
                children=self._parse_sections(item.get("children", [])),
            )
            sections.append(section)
        return sections

    def _ensure_tree_structure(self, sections: list[dict]) -> list[dict]:
        """将扁平结构转为树状（兜底逻辑）。

        如果 AI 返回的是扁平数组（各章节有 level 但没有正确 children 嵌套），
        自动根据 level 字段构建树状结构。
        """
        if not sections:
            return []

        # 检查是否已经是树状结构（一级章节有 children 且子章节有内容）
        has_tree = any(
            isinstance(s.get("children"), list) and len(s.get("children", [])) > 0
            for s in sections
        )
        if has_tree:
            return sections  # 已经是树状，不用转

        # 扁平转树状：基于 level 字段
        # 先确保每个 section 有 level
        for s in sections:
            if "level" not in s:
                s["level"] = 1
            if "children" not in s:
                s["children"] = []

        # 用栈来构建
        result: list[dict] = []
        stack: list[tuple[int, list[dict]]] = []  # (level, children_list)

        for s in sections:
            level = s.get("level", 1)
            s["children"] = []

            # 弹出栈中 level >= 当前的
            while stack and stack[-1][0] >= level:
                stack.pop()

            if not stack:
                # 根级
                result.append(s)
            else:
                # 添加到父级的 children
                parent_children = stack[-1][1]
                parent_children.append(s)

            stack.append((level, s["children"]))

        return result

    def _get_system_prompt(self, language: str) -> str:
        """获取系统提示词。"""
        if language.startswith("zh"):
            return """你是一位专业的技术文档工程师，擅长撰写清晰、实用、易于理解的操作手册。
你的写作风格：
1. 清晰简洁：用最少的文字说明白问题
2. 结构分明：善用标题、列表、表格组织内容
3. 操作性强：每个步骤都是一个明确的动作
4. 细节到位：按钮名称、菜单位置都标注清楚
5. 友好实用：适当加入提示和注意事项"""
        else:
            return """You are a professional technical documentation engineer, skilled at writing clear, practical, and easy-to-understand operation manuals.
Your writing style:
1. Clear and concise: explain things with minimal text
2. Well-structured: use headings, lists, and tables effectively
3. Actionable: each step is a clear action
4. Detailed: clearly label button names and menu locations
5. Friendly and practical: add tips and notes where appropriate"""


def analyze_and_generate(
    site_structure: SiteStructure,
    llm_config: Optional[LLMConfig] = None,
    language: str = "zh-CN",
    focus_areas: Optional[list[str]] = None,
) -> ManualOutline:
    """同步入口：分析网站并生成完整手册。

    Args:
        site_structure: 网站结构
        llm_config: LLM 配置
        language: 输出语言
        focus_areas: 重点关注区域

    Returns:
        完整的手册大纲（含内容）
    """
    analyzer = ManualAnalyzer(llm_config)

    async def _run() -> ManualOutline:
        outline = await analyzer.generate_outline(site_structure, language, focus_areas)
        full_manual = await analyzer.generate_full_manual(site_structure, outline)
        return full_manual

    return asyncio.run(_run())
