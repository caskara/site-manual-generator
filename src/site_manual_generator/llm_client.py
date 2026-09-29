"""LLM 客户端封装。

支持多种 LLM 提供商：OpenAI 兼容 API、Ollama（本地模型）。

使用同步 requests 库（兼容性更好），通过 asyncio.to_thread 包装为异步调用。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import requests

from .config import LLMConfig


class LLMClient:
    """LLM 客户端。

    统一封装不同提供商的 API 调用。
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig()
        self._proxy = self._get_proxy()
        self._session = self._build_session()

    def _get_proxy(self) -> Optional[dict]:
        """获取代理设置。优先级：配置 > 环境变量 HTTPS_PROXY > HTTP_PROXY。"""
        proxy_url = None
        if self.config.proxy:
            proxy_url = self.config.proxy
        else:
            for env_var in ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"]:
                val = os.environ.get(env_var)
                if val:
                    proxy_url = val
                    break

        if proxy_url:
            return {"http": proxy_url, "https": proxy_url}
        return None

    def _build_session(self) -> requests.Session:
        """构建 requests session。"""
        session = requests.Session()
        if self._proxy:
            session.proxies.update(self._proxy)
        return session

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成文本（异步包装同步调用）。"""
        return await asyncio.to_thread(self._generate_sync, prompt, system_prompt)

    def _generate_sync(self, prompt: str, system_prompt: str) -> str:
        """同步生成文本。"""
        provider = self.config.provider.lower()

        if provider == "ollama":
            return self._call_ollama_sync(prompt, system_prompt)
        else:
            return self._call_openai_compatible_sync(prompt, system_prompt)

    async def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        """生成 JSON 格式输出。"""
        json_system = system_prompt + "\n\n请严格按照 JSON 格式输出，不要包含任何其他文字。"
        result = await self.generate(prompt, json_system)

        # 尝试提取 JSON
        result = result.strip()
        # 移除可能的代码块标记
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        result = result.strip()

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # 尝试找到第一个 { 和最后一个 }
            start = result.find("{")
            end = result.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(result[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"无法解析 LLM 输出为 JSON: {result[:200]}")

    def _call_openai_compatible_sync(self, prompt: str, system_prompt: str) -> str:
        """调用 OpenAI 兼容 API（同步）。"""
        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        proxy_info = f"（代理: {self._proxy['https']}）" if self._proxy else ""
        print(f"[LLM] 正在调用 API: {base_url} {proxy_info}")

        try:
            response = self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=(30, self.config.timeout),
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.ConnectionError as e:
            raise RuntimeError(
                f"无法连接到 LLM API ({base_url})。\n"
                f"请检查：\n"
                f"  1. 网络是否正常\n"
                f"  2. API 地址是否正确\n"
                f"  3. 是否需要配置代理（设置 SMG_LLM_PROXY 或 HTTPS_PROXY 环境变量）\n"
                f"原始错误: {e}"
            ) from e
        except requests.HTTPError as e:
            raise RuntimeError(
                f"LLM API 返回错误: HTTP {e.response.status_code}\n"
                f"响应内容: {e.response.text[:500]}"
            ) from e

    def _call_ollama_sync(self, prompt: str, system_prompt: str) -> str:
        """调用 Ollama 本地模型 API（同步）。"""
        base_url = self.config.base_url or "http://localhost:11434"
        url = f"{base_url.rstrip('/')}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
            },
        }

        response = self._session.post(
            url,
            json=payload,
            timeout=(10, self.config.timeout),
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    def is_configured(self) -> bool:
        """检查 LLM 是否已配置可用。"""
        provider = self.config.provider.lower()
        if provider == "ollama":
            return True
        return bool(self.config.api_key)
