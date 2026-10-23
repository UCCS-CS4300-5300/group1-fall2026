import ollama
import pytest


@pytest.fixture(autouse=True)
def block_real_ollama_calls(monkeypatch):
    # this is a catch incase the program reaches for a running ollama instance, even if there isn't one.
    # a test that needs to test a llama response should replace ollama.Client or the chat function, look at test_ollama_client.py for details.

    class BlockedClient:
        def __init__(self, *args, **kwargs):
            pass

        def chat(self, *args, **kwargs):
            raise AssertionError(
                "A test tried to call a real Ollama server. Mock it instead."
            )

    monkeypatch.setattr(ollama, "Client", BlockedClient)
    
    
    
    
    
    