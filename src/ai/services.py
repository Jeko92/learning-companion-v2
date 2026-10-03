"""The one way the app talks to the OpenAI Chat Completions API."""

from django.conf import settings
from openai import OpenAI

# The SDK's default read timeout is 600 s; a page should never wait that long.
TIMEOUT_SECONDS = 30
# The SDK retries connection errors, 429 and 5xx with backoff.
MAX_RETRIES = 2


def get_client():
    """The only place an OpenAI client is built (tests replace this)."""
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )
