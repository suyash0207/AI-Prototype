"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.orchestrator import handle_message

app = FastAPI(title="Prototype")


class ChatRequest(BaseModel):
    session_id: str
    tenant_id: str = "default"
    message: str


class ChatResponse(BaseModel):
    answer: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    answer = handle_message(request.session_id, request.tenant_id, request.message)
    return ChatResponse(answer=answer)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Mounted last so it never shadows the API routes above — it only serves
# the chat UI at "/" and any other static assets under app/static/.
app.mount(
    "/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static"
)
