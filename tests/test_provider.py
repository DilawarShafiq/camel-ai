"""AnthropicProvider format conversion — unit-tested with a fake HTTP call."""

import io
import json

from camel.agent import AnthropicProvider


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_anthropic_converts_openai_shapes(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data)
        return _Resp(json.dumps({"content": [
            {"type": "text", "text": "hi"},
            {"type": "tool_use", "id": "t1", "name": "open_page",
             "input": {"url": "https://x"}},
        ]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    p = AnthropicProvider("claude-sonnet-4-5", "sk-ant-test")
    msg = p.chat(
        [{"role": "system", "content": "sys"},
         {"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {
            "name": "open_page", "description": "d",
            "parameters": {"type": "object", "properties": {}}}}])

    # request: hits /messages, system pulled out, tools converted to input_schema
    assert captured["url"].endswith("/messages")
    assert captured["body"]["system"] == "sys"
    assert captured["body"]["tools"][0]["name"] == "open_page"
    assert "input_schema" in captured["body"]["tools"][0]
    assert captured["body"]["messages"][0]["role"] == "user"

    # response: parsed back into OpenAI-style message with tool_calls
    assert msg["content"] == "hi"
    assert msg["tool_calls"][0]["function"]["name"] == "open_page"
    assert json.loads(msg["tool_calls"][0]["function"]["arguments"]) == {"url": "https://x"}
