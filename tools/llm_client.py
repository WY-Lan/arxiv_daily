"""
LLM client for Alibaba Bailian API and other providers.

This module provides a unified interface for different LLM providers,
with primary support for Alibaba Bailian (阿里百炼).
"""
import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import httpx
from loguru import logger
from openai import AsyncOpenAI

from config.settings import settings, LLMProviderConfig


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    raw_response: Any = None


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    async def generate_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON response from LLM."""
        pass


class BailianClient(BaseLLMClient):
    """
    Client for Alibaba Bailian (阿里百炼) API.

    Uses OpenAI-compatible API format.
    API documentation: https://help.aliyun.com/zh/model-studio/
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or settings.BAILIAN_API_KEY
        self.base_url = base_url or settings.BAILIAN_BASE_URL

        if not self.api_key:
            logger.warning("Bailian API key not configured. Set BAILIAN_API_KEY in .env")

        # Use OpenAI SDK with Bailian endpoint
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from Bailian API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to qwen-plus)
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse object
        """
        model = model or settings.MODEL_SUMMARY

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )
        except Exception as e:
            logger.error(f"Bailian API error: {e}")
            raise

    async def generate_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate JSON response from Bailian API.

        Adds system instruction to return valid JSON.
        """
        # Add JSON instruction to the last user message or as system message
        json_instruction = "\n\n请以有效的JSON格式返回结果，不要包含其他文字。"

        modified_messages = messages.copy()
        if modified_messages and modified_messages[-1]["role"] == "user":
            modified_messages[-1] = {
                "role": "user",
                "content": modified_messages[-1]["content"] + json_instruction
            }
        else:
            modified_messages.append({
                "role": "user",
                "content": "请以JSON格式返回结果。"
            })

        response = await self.generate(
            messages=modified_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Parse JSON from response
        import json
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw content: {content}")
            return {"error": "Failed to parse JSON", "raw_content": content}

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ):
        """
        Generate streaming response from Bailian API.

        Yields chunks of content.
        """
        model = model or settings.MODEL_SUMMARY

        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY

        if not self.api_key:
            logger.warning("Anthropic API key not configured")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Generate response from Anthropic API."""
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        model = model or "claude-sonnet-4-6"

        # Convert messages format for Anthropic
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append(msg)

        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=anthropic_messages,
        )

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            raw_response=response,
        )

    async def generate_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON response from Anthropic API."""
        import json

        json_instruction = "\n\nPlease return the result as valid JSON. Do not include any other text."

        modified_messages = messages.copy()
        if modified_messages and modified_messages[-1]["role"] == "user":
            modified_messages[-1] = {
                "role": "user",
                "content": modified_messages[-1]["content"] + json_instruction
            }

        response = await self.generate(
            messages=modified_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        content = response.content.strip()

        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw_content": content}


class LLMClientFactory:
    """Factory for creating LLM clients."""

    @staticmethod
    def create(provider: str = None) -> BaseLLMClient:
        """
        Create LLM client based on provider.

        Args:
            provider: Provider name ('bailian', 'anthropic')

        Returns:
            LLM client instance
        """
        provider = provider or settings.LLM_PROVIDER

        if provider == "bailian":
            return BailianClient()
        elif provider == "anthropic":
            return AnthropicClient()
        else:
            logger.warning(f"Unknown provider: {provider}, defaulting to bailian")
            return BailianClient()


# Convenience function
def get_llm_client(provider: str = None) -> BaseLLMClient:
    """Get LLM client instance."""
    return LLMClientFactory.create(provider)


# Default client instance
llm_client = get_llm_client()