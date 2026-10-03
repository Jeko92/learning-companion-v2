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


def complete(system, user):
    """Send one Chat Completions request (a system prompt, then the user's
    message) and return the reply text, trimmed."""
    reply = get_client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return reply.choices[0].message.content.strip()
