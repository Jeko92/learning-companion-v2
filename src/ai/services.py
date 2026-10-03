"""The one way the app talks to the OpenAI Chat Completions API."""

import logging

from django.conf import settings
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

# The SDK's default read timeout is 600 s; a page should never wait that long.
TIMEOUT_SECONDS = 30
# The SDK retries connection errors, 429 and 5xx with backoff.
MAX_RETRIES = 2


class AIServiceError(Exception):
    """The one error callers handle. Its message is safe to show a user; the
    SDK's error is chained as __cause__."""


def get_client():
    """The only place an OpenAI client is built (tests replace this)."""
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )


def complete(system, user):
    """Send one Chat Completions request (a system prompt, then the user's
    message) and return the reply text, trimmed. Raises AIServiceError."""
    try:
        reply = get_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except OpenAIError as error:
        # The type only: the SDK's text (and so a traceback) can echo part of
        # the key, e.g. "Incorrect API key provided: sk-...".
        logger.error("OpenAI request failed: %s", type(error).__name__)
        raise AIServiceError(
            "The AI service is unavailable right now. Please try again later."
        ) from error
    return reply.choices[0].message.content.strip()
