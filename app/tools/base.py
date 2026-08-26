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
from typing import ClassVar, Literal

from pydantic import BaseModel

from app.state.session_state import SessionState

TOOL_ERROR_PREFIX = "ERROR: "


class ToolSchema(BaseModel, ABC):
    TOOL_NAME: ClassVar[str]
    TOOL_DESCRIPTION: ClassVar[str]
    IS_RESPONSE_TOOL: ClassVar[bool] = False

    # Query-planning gate (Level 2.2): a tool that pulls evidence sets
    # REQUIRES_PLAN = True and declares which source it belongs to via
    # SOURCE_KIND. `plan_query` must run first, and its declared
    # needs_sql/needs_chat flags then gate which SOURCE_KIND is actually
    # callable -- see PlanQueryTool and the default validate() below.
    REQUIRES_PLAN: ClassVar[bool] = False
    SOURCE_KIND: ClassVar[Literal["sql", "chat"] | None] = None

    def validate(self, state: SessionState) -> list[str]:
        """Structural checks before `run()`. Empty list means proceed.

        Business-logic failures (not found, ambiguous match, etc.) are
        NOT reported here -- they stay inside `run()`, returned as a
        formatted string, exactly as before this class existed. This
        only exists for checks that must block `run()` from being
        called at all.
        """
        if self.REQUIRES_PLAN and state.query_plan is None:
            return [
                "You must call plan_query first, before using this tool, to state what evidence "
                "you need and where from."
            ]
        if self.SOURCE_KIND == "sql" and state.query_plan is not None and not state.needs_sql:
            return [
                "Your plan said this question doesn't need SQL. Call plan_query again if that's "
                "changed, or don't call this tool."
            ]
        if self.SOURCE_KIND == "chat" and state.query_plan is not None and not state.needs_chat:
            return [
                "Your plan said this question doesn't need chat retrieval. Call plan_query again "
                "if that's changed, or don't call this tool."
            ]
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
