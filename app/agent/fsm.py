"""The execution loop shared by every agent in this system.

Any agent — the top-level orchestrator or a sub-agent invoked as a
tool — is just: a `SessionState` plus a tool registry, run through
`run_workflow`. The loop itself has four responsibilities:

  invoke_llm                  call the model, append its turn
  has_tool_call                does that turn need any tool run?
  invoke_tools                 run each requested tool, append its result
  should_terminate_after_tools  did a *response* tool just succeed?

Termination is driven entirely by a response tool actually running
successfully — never by the model simply choosing not to call a tool.
That distinction matters: it means "the turn is over" is a fact the
code can check, not a behavior we're hoping the model exhibits.
"""

from __future__ import annotations

from app import config
from app.agent.openai_client import get_client
from app.state.session_state import SessionState
from app.tools.base import TOOL_ERROR_PREFIX, ToolRegistry, build_openai_tools


def has_tool_call(message: dict) -> bool:
    return bool(message.get("tool_calls"))


def should_terminate_after_tools(last_tool_message: dict, tool_registry: ToolRegistry) -> bool:
    tool_cls = tool_registry.get(last_tool_message.get("name", ""))
    if tool_cls is None or not tool_cls.IS_RESPONSE_TOOL:
        return False
    return not last_tool_message["content"].startswith(TOOL_ERROR_PREFIX)


def invoke_llm(state: SessionState, tool_registry: ToolRegistry) -> None:
    client = get_client()
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=state.get_base_messages(),
        tools=build_openai_tools(tool_registry),
    )
    state.add_ai_message(response.choices[0].message)


def invoke_tools(state: SessionState, tool_registry: ToolRegistry) -> None:
    last_message = state.chat_messages[-1]
    for call in last_message.get("tool_calls", []):
        function = call["function"]
        tool_name = function["name"]
        tool_cls = tool_registry.get(tool_name)

        if tool_cls is None:
            state.add_tool_output(
                call["id"], tool_name, f"{TOOL_ERROR_PREFIX}unknown tool '{tool_name}'"
            )
            continue

        try:
            instance = tool_cls.model_validate_json(function["arguments"])
        except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error, not raised
            state.add_tool_output(
                call["id"], tool_name, f"{TOOL_ERROR_PREFIX}invalid arguments: {exc}"
            )
            continue

        errors = instance.validate(state)
        if errors:
            state.add_tool_output(call["id"], tool_name, f"{TOOL_ERROR_PREFIX}{'; '.join(errors)}")
            continue

        result = instance.run(state)
        state.add_tool_output(call["id"], tool_name, result)


def run_workflow(state: SessionState, tool_registry: ToolRegistry) -> str:
    invoke_llm(state, tool_registry)
    llm_call_count = 1

    while has_tool_call(state.chat_messages[-1]):
        invoke_tools(state, tool_registry)

        if should_terminate_after_tools(state.chat_messages[-1], tool_registry):
            break

        if llm_call_count >= config.FSM_MAX_LLM_CALLS:
            raise RuntimeError(f"LLM call budget ({config.FSM_MAX_LLM_CALLS}) exceeded")

        invoke_llm(state, tool_registry)
        llm_call_count += 1

    return state.chat_messages[-1]["content"]
