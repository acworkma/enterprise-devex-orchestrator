"""Copilot SDK Agent Runtime.

This module provides the core agent loop that drives the Enterprise DevEx
Orchestrator. It uses the GitHub Copilot SDK / OpenAI-compatible API to
perform multi-turn, tool-calling agent workflows.

Architecture:
    User Intent (string)
        -> Intent Parser Agent   -> IntentSpec
        -> Architecture Planner  -> PlanOutput
        -> Governance Reviewer   -> GovernanceReport (with feedback loop)
        -> Infrastructure Gen    -> Bicep files, CI/CD, app code, docs
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from openai import AzureOpenAI, OpenAI

from src.orchestrator.config import AppConfig, get_config
from src.orchestrator.llm_client import AnthropicAdapter, create_llm_client
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)

# Type alias for tool functions
ToolFunction = Callable[..., str]


@dataclass
class Tool:
    """Definition of a tool the agent can call."""

    name: str
    description: str
    parameters: dict[str, Any]
    function: ToolFunction

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class AgentContext:
    """Mutable context passed through the agent chain."""

    config: AppConfig
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 10


class AgentRuntime:
    """Core agent runtime powered by GitHub Copilot SDK / OpenAI API.

    Manages the agent loop: send messages -> receive tool calls -> execute
    tools -> append results -> repeat until the agent produces a final response.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or get_config()
        self._client = create_llm_client(self.config)
        self._tool_registry: dict[str, Tool] = {}

    def _create_client(self) -> OpenAI | AzureOpenAI | AnthropicAdapter:
        """Create the appropriate LLM client based on configuration."""
        return create_llm_client(self.config)

    def register_tool(self, tool: Tool) -> None:
        """Register a tool that the agent can call."""
        self._tool_registry[tool.name] = tool
        logger.info("agent.tool_registered", tool=tool.name)

    def register_tools(self, tools: list[Tool]) -> None:
        """Register multiple tools."""
        for tool in tools:
            self.register_tool(tool)

    async def run(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[Tool] | None = None,
        max_iterations: int = 10,
    ) -> str:
        """Execute the agent loop.

        Args:
            system_prompt: System instructions for the agent role.
            user_message: The user's input message.
            tools: Optional tools specific to this run (merged with registry).
            max_iterations: Maximum tool-calling iterations to prevent runaway loops.

        Returns:
            The agent's final text response.
        """
        # Merge run-specific tools with registered tools
        all_tools = dict(self._tool_registry)
        if tools:
            for t in tools:
                all_tools[t.name] = t

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        openai_tools = [t.to_openai_schema() for t in all_tools.values()] if all_tools else None

        for iteration in range(max_iterations):
            logger.info("agent.iteration", iteration=iteration, message_count=len(messages))

            try:
                response = self._client.chat.completions.create(
                    model=self.config.llm.model,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,  # type: ignore[arg-type]
                    temperature=self.config.llm.temperature,
                )
            except Exception as e:
                logger.error("agent.api_error", error=str(e), iteration=iteration)
                # Fall back to template-only mode
                return self._fallback_response(user_message)

            choice = response.choices[0]
            message = choice.message

            # If no tool calls, we have the final response
            if not message.tool_calls:
                logger.info("agent.complete", iteration=iteration)
                return message.content or ""

            # Process tool calls
            messages.append(message.model_dump())  # type: ignore[arg-type]

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args_str = tool_call.function.arguments

                logger.info("agent.tool_call", tool=fn_name, args=fn_args_str)

                if fn_name in all_tools:
                    try:
                        fn_args = json.loads(fn_args_str) if fn_args_str else {}
                        result = all_tools[fn_name].function(**fn_args)
                    except Exception as e:
                        result = f"Error executing tool {fn_name}: {e}"
                        logger.error("agent.tool_error", tool=fn_name, error=str(e))
                else:
                    result = f"Unknown tool: {fn_name}"
                    logger.warning("agent.unknown_tool", tool=fn_name)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    }
                )

        logger.warning("agent.max_iterations", max_iterations=max_iterations)
        return messages[-1].get("content", "Agent reached maximum iterations without a final response.")

    def _fallback_response(self, user_message: str) -> str:
        """Provide a template-based fallback when API is unavailable."""
        logger.info("agent.fallback", msg="Using template-only mode")
        return json.dumps(
            {
                "mode": "template-fallback",
                "message": "API unavailable -- using secure defaults",
                "input": user_message[:200],
            }
        )

    def run_sync(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[Tool] | None = None,
        max_iterations: int = 10,
    ) -> str:
        """Synchronous wrapper for the agent loop."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.run(system_prompt, user_message, tools, max_iterations),
                )
                return future.result()
        else:
            return asyncio.run(self.run(system_prompt, user_message, tools, max_iterations))
