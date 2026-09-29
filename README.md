# Site Manual Generator (SMG)

> 输入网站 URL，一键生成结构化操作手册（DOCX 格式）

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io/)

一个基于 AI 的网站操作手册自动生成工具。只需提供一个网站 URL，它会自动爬取网站内容，使用 LLM 分析功能结构，最终生成一份格式精美的 Word 操作手册（.docx）。

## ✨ 功能特性

### 核心能力
- 🌐 **智能爬取**：基于 Playwright，支持 JavaScript 渲染页面，自动提取正文与导航链接
- 🤖 **AI 分析**：使用 LLM 理解网站功能，自动生成三级结构手册大纲
- 📄 **精美 DOCX**：封面页、自动编号目录（1 / 1.1 / 1.1.1）、排版规范、表格支持
- 🖼️ **自动配图**：每个章节自动匹配最合适的页面截图
- 🚫 **自动清弹窗**：自动关闭 Cookie 提示、登录弹窗、广告等，截图干净
- 🔐 **手动登录模式**：`--login` 参数打开有头浏览器，手动登录后带着登录态爬取

### 使用方式
- 💻 **CLI 命令行**：一条命令生成手册
- 🔌 **MCP Server**：任何支持 MCP 的 AI 助手（Cursor、Trae、Claude Desktop）都能调用
- 🛠️ **TRAE Skill**：在 TRAE 中对话直接触发
- 🐍 **Python API**：集成到自己的项目

### LLM 支持
- OpenAI / DeepSeek / 通义千问 / 零一万物 等所有 OpenAI 兼容 API
- Ollama（本地模型，完全免费）
- 可配置代理

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Chromium 浏览器（Playwright 自动安装）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/site-manual-generator.git
cd site-manual-generator

# 2. 安装 Python 依赖
pip install -e .

# 3. 安装 Playwright 浏览器
playwright install chromium
```

### 配置 LLM

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

**DeepSeek 示例（国内推荐）：**

```env
SMG_LLM_PROVIDER=openai
SMG_LLM_BASE_URL=https://api.deepseek.com/v1
SMG_LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
SMG_LLM_MODEL=deepseek-chat
```

**OpenAI 示例：**

```env
SMG_LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
SMG_LLM_MODEL=gpt-4o-mini
```

**Ollama 本地模型：**

```env
SMG_LLM_PROVIDER=openai
SMG_LLM_BASE_URL=http://localhost:11434/v1
SMG_LLM_API_KEY=ollama
SMG_LLM_MODEL=qwen2.5:7b
```

## 📖 使用方法

### 1. 基础用法（最简单）

```bash
smg generate https://example.com
```

或：

```bash
python -m site_manual_generator.cli.main generate https://example.com
```

生成的手册在 `output/` 目录下。

### 2. 指定输出文件

```bash
smg generate https://example.com -o my_manual.docx
```

### 3. 控制爬取范围

```bash
# 最多爬 20 页，最多 2 层深度
smg generate https://example.com --max-pages 20 --max-depth 2
```

### 4. 手动登录模式（需要登录的网站）

```bash
smg generate https://example.com/dashboard --login
```

运行后会打开浏览器窗口，你手动完成登录，回到终端按回车，爬虫就会带着登录态继续爬取所有页面。

### 5. 显示浏览器（调试用）

```bash
smg generate https://example.com --show-browser
```

### 6. 完整参数列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 目标网站 URL（必填） | - |
| `-o, --output` | 输出文件路径 | 自动生成 |
| `-l, --language` | 输出语言 | `zh-CN` |
| `--max-pages` | 最大爬取页面数 | `30` |
| `--max-depth` | 最大爬取深度 | `3` |
| `--login` | 启用手动登录模式 | `False` |
| `--headless/--show-browser` | 是否无头模式 | 无头 |
| `--provider` | LLM 提供商 | `openai` |
| `--model` | 模型名称 | `gpt-4o-mini` |
| `--api-key` | API Key | 从环境变量读取 |
| `--base-url` | API 基础地址 | 从环境变量读取 |
| `-i, --interactive` | 交互式模式 | `False` |

## 📁 项目结构

```
site-manual-generator/
├── src/site_manual_generator/
│   ├── __init__.py
│   ├── config.py              # 配置管理（环境变量 / .env）
│   ├── models.py              # 数据模型
│   ├── crawler.py             # Playwright 爬虫（自动清弹窗）
│   ├── llm_client.py          # LLM 客户端（多提供商）
│   ├── analyzer.py            # AI 分析 + 手册生成
│   ├── annotator.py           # 图片标注工具
│   ├── docx_generator.py      # DOCX 文档生成
│   ├── pipeline.py            # 整合流水线
│   ├── cli/                   # 命令行入口
│   └── mcp/                   # MCP Server
├── .trae-plugin/              # TRAE 插件清单
├── skills/                    # TRAE Skill 定义
├── assets/                    # 图标等资源
├── examples/                  # 示例
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

## 🔌 MCP Server 用法

在 Cursor / Claude Desktop / Trae 等支持 MCP 的工具中配置：

```json
{
  "mcpServers": {
    "site-manual-generator": {
      "command": "python",
      "args": ["-m", "site_manual_generator.mcp.server"],
      "cwd": "/path/to/site-manual-generator"
    }
  }
}
```

可用工具：
- `generate_manual` — 生成完整操作手册
- `crawl_site` — 仅爬取网站
- `generate_outline` — 仅生成大纲

## 🛠️ 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest
```

## 📝 注意事项

1. **合法使用**：请遵守目标网站的 `robots.txt` 和服务条款，不要用于非法爬取
2. **速率控制**：默认单线程顺序爬取，不会给目标网站造成压力
3. **登录态安全**：手动登录模式下，浏览器上下文仅在本次运行中有效，不会保存到磁盘
4. **内容准确性**：AI 生成的内容可能存在误差，请以官方文档为准
5. **截图大小**：整页截图可能很大（长网页），可以调小 `--max-pages` 控制

## 📄 License

MIT License
