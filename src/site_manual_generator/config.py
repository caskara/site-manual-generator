"""配置管理模块。

支持从环境变量、配置文件、命令行参数加载配置。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM 相关配置。"""

    model_config = SettingsConfigDict(env_prefix="SMG_LLM_", env_file=".env", extra="ignore")

    provider: str = Field(
        default="openai",
        description="LLM 提供商: openai / anthropic / ollama / deepseek / qwen",
    )
    api_key: Optional[str] = Field(default=None, description="API Key")
    base_url: Optional[str] = Field(default=None, description="API 基础地址（兼容自定义端点）")
    model: str = Field(default="gpt-4o-mini", description="模型名称")
    temperature: float = Field(default=0.3, description="生成温度")
    max_tokens: int = Field(default=4000, description="最大输出 token 数")
    timeout: int = Field(default=120, description="请求超时时间（秒）")
    proxy: Optional[str] = Field(
        default=None,
        description="HTTP 代理地址，例如 http://127.0.0.1:7890",
    )


class CrawlerConfig(BaseSettings):
    """爬虫相关配置。"""

    model_config = SettingsConfigDict(env_prefix="SMG_CRAWLER_", env_file=".env", extra="ignore")

    max_pages: int = Field(default=30, description="最大爬取页面数")
    max_depth: int = Field(default=3, description="最大爬取深度")
    headless: bool = Field(default=True, description="是否无头模式运行浏览器")
    manual_login: bool = Field(default=False, description="是否启用手动登录模式（打开有头浏览器让用户手动登录）")
    wait_until: str = Field(default="networkidle", description="页面等待策略")
    timeout: int = Field(default=30000, description="页面加载超时（毫秒）")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 SiteManualGenerator/0.1",
        description="User-Agent",
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\.(pdf|jpg|jpeg|png|gif|svg|ico|css|js|zip|rar|docx|xlsx)$",
            r"/login",
            r"/logout",
            r"/signup",
            r"/register",
            r"#",
        ],
        description="排除的 URL 模式（正则）",
    )


class OutputConfig(BaseSettings):
    """输出相关配置。"""

    model_config = SettingsConfigDict(env_prefix="SMG_OUTPUT_", env_file=".env", extra="ignore")

    output_dir: Path = Field(default=Path("./output"), description="输出目录")
    format: str = Field(default="docx", description="输出格式: docx / markdown")
    language: str = Field(default="zh-CN", description="输出语言")
    include_screenshots: bool = Field(default=True, description="是否包含截图")
    template: Optional[str] = Field(default=None, description="自定义模板路径")


class AppConfig:
    """应用总配置。"""

    def __init__(
        self,
        llm: Optional[LLMConfig] = None,
        crawler: Optional[CrawlerConfig] = None,
        output: Optional[OutputConfig] = None,
    ) -> None:
        self.llm = llm or LLMConfig()
        self.crawler = crawler or CrawlerConfig()
        self.output = output or OutputConfig()

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量加载配置。"""
        return cls(
            llm=LLMConfig(),
            crawler=CrawlerConfig(),
            output=OutputConfig(),
        )
