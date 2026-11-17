import json

import httpx
import pytest
from pydantic import BaseModel

from blocapta.llm import LLMError, OllamaClient


class Out(BaseModel):
    name: str
    count: int


def _client(responses: list[str], seen: list[dict]) -> OllamaClient:
    it = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": next(it)}})

    http = httpx.Client(base_url="http://ollama", transport=httpx.MockTransport(handler))
    return OllamaClient("qwen3:8b", http_client=http)


def test_structured_output_sends_schema():
    seen: list[dict] = []
    out = _client(['{"name": "x", "count": 2}'], seen).structured("prompt", Out, system="sys")
    assert out == Out(name="x", count=2)
    body = seen[0]
    assert body["model"] == "qwen3:8b"
    assert body["format"]["properties"]["count"]["type"] == "integer"
    assert body["stream"] is False and body["think"] is False
    assert body["messages"][0]["role"] == "system"


def test_retries_on_invalid_json():
    seen: list[dict] = []
    out = _client(['{"name": "x"}', '{"name": "x", "count": 3}'], seen).structured("p", Out)
    assert out.count == 3
    assert len(seen) == 2
    assert "ne respecte pas le schéma" in seen[1]["messages"][-1]["content"]


def test_gives_up_after_retries():
    with pytest.raises(LLMError):
        _client(["{}"] * 3, []).structured("p", Out)


def test_connection_error_is_explicit():
    def handler(request):
        raise httpx.ConnectError("refused")

    c = OllamaClient("qwen3:8b", http_client=httpx.Client(base_url="http://x", transport=httpx.MockTransport(handler)))
    with pytest.raises(LLMError, match="ollama pull qwen3:8b"):
        c.text("bonjour")
