import httpx
import ollama
from django.conf import settings


class OllamaUnavailable(Exception):
    """raises error when the model isn't able to give a response."""


def chat(messages):
    client = ollama.Client(host=settings.OLLAMA_HOST, timeout=settings.OLLAMA_TIMEOUT)
    try:
        response = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            stream=False,
        )
    except (ollama.ResponseError, ConnectionError, httpx.HTTPError) as error:
        raise OllamaUnavailable(str(error)) from error
    return response.message.content or ""





