"""Multi-provider LLM client abstraction.

Supports Azure OpenAI, OpenAI, Anthropic (Claude), GitHub Copilot SDK,
and a template-only fallback mode.

Usage:
    from src.orchestrator.llm_client import create_llm_client

    client = create_llm_client(config)
    response = client.chat_completion(
        model="claude-opus-4-20250514",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.0,
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import AzureOpenAI, OpenAI

from src.orchestrator.config import AppConfig, LLMConfig, get_config
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatMessage:
    """Normalized chat completion message."""

    role: str
    content: str | None
    tool_calls: list[Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        result: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [
                tc if isinstance(tc, dict) else tc.model_dump() for tc in self.tool_calls
            ]
        return result


@dataclass
class ChatChoice:
    """Normalized chat completion choice."""

    message: ChatMessage


@dataclass
class ChatCompletionResponse:
    """Normalized chat completion response."""

    choices: list[ChatChoice]


class AnthropicAdapter:
    """Adapter that wraps the Anthropic SDK to match the OpenAI chat completion interface.

    This lets the AgentRuntime work with Claude models using the same code path
    as OpenAI models.
    """

    def __init__(self, api_key: str) -> None:
        try:
            import anthropic  # noqa: F811
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for Claude support. "
                "Install it with: pip install anthropic"
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self.chat = self  # Allow client.chat.completions.create() call pattern
        self.completions = self

    def create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ChatCompletionResponse:
        """Call Anthropic API and return a normalized response."""
        # Separate system message from conversation messages
        system_prompt = ""
        conversation: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            elif msg.get("role") == "tool":
                # Convert OpenAI tool result format to Anthropic format
                conversation.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": msg.get("content", ""),
                        }
                    ],
                })
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Convert assistant tool call messages to Anthropic format
                content_blocks: list[dict[str, Any]] = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    tc_data = tc if isinstance(tc, dict) else tc.model_dump() if hasattr(tc, "model_dump") else tc
                    fn = tc_data.get("function", {})
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc_data.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {}),
                    })
                conversation.append({"role": "assistant", "content": content_blocks})
            else:
                conversation.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # Convert OpenAI tool schemas to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for tool in tools:
                fn = tool.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                })

        # Build API call kwargs
        api_kwargs: dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_prompt:
            api_kwargs["system"] = system_prompt
        if anthropic_tools:
            api_kwargs["tools"] = anthropic_tools

        response = self._client.messages.create(**api_kwargs)

        # Convert Anthropic response to OpenAI-compatible format
        return self._convert_response(response)

    def _convert_response(self, response: Any) -> ChatCompletionResponse:
        """Convert Anthropic API response to normalized format."""
        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    _AnthropicToolCall(
                        id=block.id,
                        function=_AnthropicFunction(
                            name=block.name,
                            arguments=json.dumps(block.input),
                        ),
                    )
                )

        message = ChatMessage(
            role="assistant",
            content=text_content if text_content else None,
            tool_calls=tool_calls if tool_calls else None,
        )

        return ChatCompletionResponse(choices=[ChatChoice(message=message)])


@dataclass
class _AnthropicToolCall:
    """Mimics OpenAI tool call structure."""

    id: str
    function: _AnthropicFunction
    type: str = "function"

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments,
            },
        }


@dataclass
class _AnthropicFunction:
    """Mimics OpenAI function call structure."""

    name: str
    arguments: str


def create_llm_client(config: AppConfig | None = None) -> OpenAI | AzureOpenAI | AnthropicAdapter:
    """Create the appropriate LLM client based on configuration.

    Provider priority:
        1. Explicit LLM_PROVIDER env var
        2. Auto-detect from available credentials
        3. Template-only fallback

    Returns:
        An OpenAI, AzureOpenAI, or AnthropicAdapter client instance.
    """
    cfg = config or get_config()
    provider = cfg.llm.provider
    model = cfg.llm.model

    if provider == "azure_openai":
        logger.info("llm.client", backend="azure_openai", model=model)
        return AzureOpenAI(
            azure_endpoint=cfg.llm.azure_openai_endpoint,
            api_key=cfg.llm.azure_openai_api_key,
            api_version="2024-10-21",
        )

    if provider == "openai":
        logger.info("llm.client", backend="openai", model=model)
        kwargs: dict[str, Any] = {"api_key": cfg.llm.openai_api_key}
        if cfg.llm.openai_org_id:
            kwargs["organization"] = cfg.llm.openai_org_id
        return OpenAI(**kwargs)

    if provider == "anthropic":
        logger.info("llm.client", backend="anthropic", model=model)
        return AnthropicAdapter(api_key=cfg.llm.anthropic_api_key)

    if provider == "copilot_sdk":
        logger.info("llm.client", backend="copilot_sdk", model=model)
        return OpenAI(
            base_url="https://api.githubcopilot.com",
            api_key=cfg.copilot.github_token,
        )

    # Fallback: template-only mode
    logger.warning("llm.client", backend="template-only", msg="No API credentials -- running in template-only mode")
    return OpenAI(api_key="mock-key", base_url="http://localhost:11434/v1")  # noqa: S106
