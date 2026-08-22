"""Tool registration: how a tool advertises itself to the model and how
its arguments get validated and executed once the model calls it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from app.state.session_state import SessionState

TOOL_ERROR_PREFIX = "ERROR: "


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[[BaseModel, SessionState], str]
    is_response_tool: bool = False

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }


ToolRegistry = dict[str, Tool]


def build_tool_registry(tools: list[Tool]) -> ToolRegistry:
    return {tool.name: tool for tool in tools}


def build_openai_tools(registry: ToolRegistry) -> list[dict]:
    return [tool.to_openai_schema() for tool in registry.values()]
