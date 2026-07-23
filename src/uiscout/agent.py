"""Any-LLM agent frontend.

For users who want to point their OWN model at the browser toolkit instead of
using an MCP client. Implement the tiny `LLMProvider` interface for any LLM and
the same Playwright core does the work.

A reference `OpenAICompatibleProvider` is included. It speaks the OpenAI
`/chat/completions` tool-calling format, which also covers Ollama
(http://localhost:11434/v1), LM Studio, vLLM, Together, Groq, and most local
servers — so "any LLM" is real, not aspirational. Uses only the stdlib, so the
agent adds no dependencies of its own.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Protocol

from .browser import Session

# The tool schema handed to the LLM. Each name maps to a Session method below.
TOOLS = [
    {"type": "function", "function": {
        "name": "open_page",
        "description": "Open a URL and return title + HTTP status.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "snapshot",
        "description": "List visible interactive elements with labels + selectors.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "click",
        "description": "Click the element matching a CSS selector.",
        "parameters": {"type": "object", "properties": {
            "selector": {"type": "string"}}, "required": ["selector"]}}},
    {"type": "function", "function": {
        "name": "audit_interactivity",
        "description": "Click every interactive element; report dead controls, "
                       "navigations, dialogs, DOM changes, console errors.",
        "parameters": {"type": "object", "properties": {
            "max_elements": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "get_console_errors",
        "description": "Return console errors, page errors, failed requests.",
        "parameters": {"type": "object", "properties": {}}}},
]


class LLMProvider(Protocol):
    """Implement this for any LLM. `chat` takes the running message list plus the
    tool schema and returns the assistant message dict (with optional
    `tool_calls`), OpenAI-style."""

    def chat(self, messages: list[dict], tools: list[dict]) -> dict: ...


class OpenAICompatibleProvider:
    """Works with OpenAI and any OpenAI-compatible endpoint (Gemini's OpenAI
    endpoint, OpenRouter, Ollama, LM Studio, vLLM, Groq, Together, ...)."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1",
                 api_key: str = "not-needed") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]


def provider_from_config() -> "OpenAICompatibleProvider":
    """Build the brain from the user's ~/.uiscout config (set by `uiscout setup`).
    Raises a friendly error if setup hasn't been run."""
    from . import config
    brain = config.get_brain()
    if not brain:
        raise RuntimeError("No brain configured. Run `uiscout setup` first.")
    return OpenAICompatibleProvider(
        model=brain["model"], base_url=brain["base_url"],
        api_key=brain.get("api_key", "not-needed"))


async def _dispatch(session: Session, name: str, args: dict) -> Any:
    if name == "open_page":
        return await session.navigate(args["url"])
    if name == "snapshot":
        return await session.snapshot()
    if name == "click":
        return await session.click(args["selector"])
    if name == "audit_interactivity":
        return await session.audit_interactivity(args.get("max_elements", 40))
    if name == "get_console_errors":
        return session.get_console_errors()
    return {"error": f"unknown tool {name}"}


async def run_audit(provider: LLMProvider, goal: str, *, headless: bool = False,
                    max_steps: int = 20) -> str:
    """Drive the browser toward `goal` using any LLM. Returns the final report."""
    session = Session(headless=headless)
    await session.start()
    messages: list[dict] = [
        {"role": "system", "content":
            "You are a UI/UX tester. Use the tools to open the app, inspect it, "
            "and audit interactivity. Report broken buttons, console errors, and "
            "UX issues plainly. When done, reply with a final summary and no tool call."},
        {"role": "user", "content": goal},
    ]
    try:
        for _ in range(max_steps):
            msg = provider.chat(messages, TOOLS)
            messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content", "(no summary)")
            for call in calls:
                fn = call["function"]
                args = json.loads(fn.get("arguments") or "{}")
                result = await _dispatch(session, fn["name"], args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, default=str)[:6000],
                })
        return "(reached max_steps without a final summary)"
    finally:
        await session.stop()


if __name__ == "__main__":
    import asyncio
    import sys

    # Example: point at a local Ollama model (no API key needed).
    #   python -m uiscout.agent "Audit every button on http://localhost:3000"
    prov = OpenAICompatibleProvider(
        model="llama3.1", base_url="http://localhost:11434/v1")
    task = sys.argv[1] if len(sys.argv) > 1 else "Audit https://example.com"
    print(asyncio.run(run_audit(prov, task)))
