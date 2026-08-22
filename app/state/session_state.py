"""In-memory state for a single conversation.

`chat_messages` is the single source of truth for everything that has
happened in this conversation. Nothing here is ever written to disk,
a database, or any store outside the current process — an instance
lives only as long as something (the session store) keeps a reference
to it, and is gone the moment the process restarts.
"""

from __future__ import annotations

from typing import Any


class SessionState:
    def __init__(self, session_id: str, tenant_id: str, system_prompt: str) -> None:
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.system_message: dict[str, str] = {"role": "system", "content": system_prompt}
        self.chat_messages: list[dict[str, Any]] = []

    def add_human_message(self, text: str) -> None:
        self.chat_messages.append({"role": "user", "content": text})

    def add_ai_message(self, message: Any) -> None:
        """Append an assistant turn as returned by the model, tool_calls included."""
        self.chat_messages.append(message.model_dump(exclude_none=True))

    def add_tool_output(self, tool_call_id: str, tool_name: str, content: str) -> None:
        """Append one tool-result message, matched back to the call that requested it.

        `tool_name` is kept alongside the standard OpenAI fields purely for our
        own bookkeeping (e.g. deciding whether a response tool just ran) —
        `get_base_messages` strips it back out before this is sent to the model.
        """
        self.chat_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": content,
            }
        )

    def get_base_messages(self) -> list[dict[str, Any]]:
        """Derive the flat, model-ready message list from `chat_messages`.

        This is the single seam where the system prompt is injected in
        front of the conversation, and where any bookkeeping-only fields
        get stripped before the messages are sent to the model.
        """
        messages: list[dict[str, Any]] = [self.system_message]
        for message in self.chat_messages:
            if message["role"] == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": message["tool_call_id"],
                        "content": message["content"],
                    }
                )
            else:
                messages.append(message)
        return messages
