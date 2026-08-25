"""Tool registration: how a tool advertises itself to the model and how
its arguments get validated and executed once the model calls it.

One class = one tool: its own Pydantic fields ARE its arguments, so
there's no separate Args class or handler function to hunt down --
`validate()` runs first (structural checks; empty list = proceed) and
`run()` does the actual work. Mirrors the pattern from meritic/darwin_new's
`ToolArgsSchema`, minus the generator/step-status machinery this app has
no status-streaming UI to feed -- `run()` here is a single synchronous
string return.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from app.state.session_state import SessionState

TOOL_ERROR_PREFIX = "ERROR: "


class ToolSchema(BaseModel, ABC):
    TOOL_NAME: ClassVar[str]
    TOOL_DESCRIPTION: ClassVar[str]
    IS_RESPONSE_TOOL: ClassVar[bool] = False

    def validate(self, state: SessionState) -> list[str]:
        """Structural checks before `run()`. Empty list means proceed.

        Business-logic failures (not found, ambiguous match, etc.) are
        NOT reported here -- they stay inside `run()`, returned as a
        formatted string, exactly as before this class existed. This
        only exists for checks that must block `run()` from being
        called at all.
        """
        return []

    @abstractmethod
    def run(self, state: SessionState) -> str:
        """Execute the tool and return its result string."""
        ...

    @classmethod
    def to_openai_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.TOOL_NAME,
                "description": cls.TOOL_DESCRIPTION,
                "parameters": cls.model_json_schema(),
            },
        }


ToolRegistry = dict[str, type[ToolSchema]]


def build_tool_registry(tools: list[type[ToolSchema]]) -> ToolRegistry:
    return {tool.TOOL_NAME: tool for tool in tools}


def build_openai_tools(registry: ToolRegistry) -> list[dict]:
    return [tool.to_openai_schema() for tool in registry.values()]
