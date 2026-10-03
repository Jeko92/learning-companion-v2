"""The one way the app talks to the OpenAI Chat Completions API."""

import json
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


def get_client(max_retries=MAX_RETRIES):
    """The only place an OpenAI client is built (tests replace this)."""
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=TIMEOUT_SECONDS,
        max_retries=max_retries,
    )


def complete(system, user, *, max_retries=MAX_RETRIES):
    """Send one Chat Completions request (a system prompt, then the user's
    message) and return the reply text, trimmed. Raises AIServiceError.

    Calls made while a user waits on a page pass max_retries=0: each retry
    can add a wait of up to two minutes (the SDK honours Retry-After)."""
    return _reply_text(system, user, max_retries=max_retries)


def complete_json(system, user, *, name, schema, max_retries=MAX_RETRIES):
    """Like complete(), but asks for a reply matching the JSON schema (strict
    Structured Outputs) and returns it parsed."""
    text = _reply_text(
        system,
        user,
        max_retries=max_retries,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        },
    )
    return json.loads(text)


def _reply_text(system, user, *, max_retries, **options):
    """The one request both calls share: the reply text, trimmed, or an
    AIServiceError. A refusal has no content, so it is an empty reply."""
    try:
        reply = get_client(max_retries=max_retries).chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **options,
        )
    except OpenAIError as error:
        # The type only: the SDK's text (and so a traceback) can echo part of
        # the key, e.g. "Incorrect API key provided: sk-...".
        logger.error("OpenAI request failed: %s", type(error).__name__)
        raise AIServiceError(
            "The AI service is unavailable right now. Please try again later."
        ) from error
    text = (reply.choices[0].message.content or "").strip() if reply.choices else ""
    if not text:
        logger.error("OpenAI returned an empty reply")
        raise AIServiceError("The AI service returned an empty reply.")
    return text
