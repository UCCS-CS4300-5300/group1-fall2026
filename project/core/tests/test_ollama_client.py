from types import SimpleNamespace

import httpx
import ollama
import pytest

from core.ollama_client import OllamaUnavailable, chat

MESSAGES = [
    {"role": "system", "content": "You are a friendly workout buddy."},
    {"role": "user", "content": "Hi!"},
]


def make_reply(text):
    # the response should look like the object a real ollama would return.
    return SimpleNamespace(message=SimpleNamespace(content=text))


@pytest.fixture
def fake_ollama(monkeypatch):
    # repalce a real ollama client with a moc one for testing.
    state = {"outcome": make_reply("Nice work!")}

    class FakeClient:
        def __init__(self, host, timeout):
            state["host"] = host
            state["timeout"] = timeout

        def chat(self, model, messages, stream):
            state.update(model=model, messages=messages, stream=stream)
            if isinstance(state["outcome"], Exception):
                raise state["outcome"]
            return state["outcome"]

    monkeypatch.setattr(ollama, "Client", FakeClient)
    return state


def test_chat_returns_the_reply_text(fake_ollama):
    assert chat(MESSAGES) == "Nice work!"


def test_chat_sends_the_messages_without_streaming(fake_ollama):
    chat(MESSAGES)
    assert fake_ollama["messages"] == MESSAGES
    assert fake_ollama["stream"] is False


def test_chat_uses_the_configured_model_host_and_timeout(fake_ollama, settings):
    settings.OLLAMA_MODEL = "llama3.2:3b"
    settings.OLLAMA_HOST = "http://localhost:11434"
    settings.OLLAMA_TIMEOUT = 42

    chat(MESSAGES)

    assert fake_ollama["model"] == "llama3.2:3b"
    assert fake_ollama["host"] == "http://localhost:11434"
    assert fake_ollama["timeout"] == 42


def test_empty_reply_becomes_empty_string(fake_ollama):
    fake_ollama["outcome"] = make_reply(None)
    assert chat(MESSAGES) == ""


@pytest.mark.parametrize(
    "problem",
    [
        ConnectionError("Failed to connect to Ollama."),
        ollama.ResponseError("model 'llama3.2:3b' not found", 404),
        httpx.ReadTimeout("timed out"),
    ],
    ids=["server-not-running", "model-not-installed", "reply-too-slow"],
)
def test_ollama_problems_become_ollama_unavailable(fake_ollama, problem):
    fake_ollama["outcome"] = problem
    with pytest.raises(OllamaUnavailable) as info:
        chat(MESSAGES)
    assert info.value.__cause__ is problem


def test_real_ollama_is_blocked_during_tests():
    with pytest.raises(AssertionError, match="real Ollama"):
        ollama.Client(host="http://localhost:11434").chat(model="x", messages=[])





