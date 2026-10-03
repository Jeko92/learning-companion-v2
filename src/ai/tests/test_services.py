import importlib
import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx2
import openai
from django.test import SimpleTestCase, override_settings

KEY_LIKE = "sk-abc123secret"


def response(*contents):
    """A Chat Completions response with one choice per given content."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content))
            for content in contents
        ]
    )


class FakeClient:
    """Stands in for openai.OpenAI: records each chat.completions.create call
    and returns `reply`, or raises `error`."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.reply


class NoNetworkTestCase(SimpleTestCase):
    """Fails any test that would build a real OpenAI client, so no test can
    reach the network: tests replace get_client() with a fake instead."""

    def setUp(self):
        # Asserted first, so a missing module fails cleanly, not with an error.
        self.assertIsNotNone(
            importlib.util.find_spec("ai.services"), "ai.services is missing"
        )
        self.services = importlib.import_module("ai.services")
        self.enterContext(
            patch(
                "ai.services.OpenAI",
                side_effect=AssertionError("a test tried to build a real client"),
            )
        )


class GetClientTests(NoNetworkTestCase):
    def test_a_real_client_is_never_built_in_tests(self):
        with self.assertRaisesMessage(AssertionError, "build a real client"):
            self.services.get_client()

    @override_settings(OPENAI_API_KEY="sk-test-client")
    def test_the_client_uses_the_key_a_30_second_timeout_and_2_retries(self):
        with patch("ai.services.OpenAI") as client_class:
            client = self.services.get_client()

        client_class.assert_called_once_with(
            api_key="sk-test-client", timeout=30, max_retries=2
        )
        self.assertIs(client, client_class.return_value)
        self.assertIsInstance(client, MagicMock)


class CompleteTests(NoNetworkTestCase):
    def complete_with(self, client, system="Be brief.", user="Summarise this."):
        with patch("ai.services.get_client", return_value=client):
            return self.services.complete(system, user)

    @override_settings(OPENAI_MODEL="test-model")
    def test_one_request_with_the_model_and_the_system_then_user_message(self):
        client = FakeClient(reply=response("Hi"))

        self.complete_with(client, system="You are a coach.", user="My sessions…")

        self.assertEqual(
            client.calls,
            [
                {
                    "model": "test-model",
                    "messages": [
                        {"role": "system", "content": "You are a coach."},
                        {"role": "user", "content": "My sessions…"},
                    ],
                }
            ],
        )

    def test_the_reply_text_comes_back_trimmed(self):
        client = FakeClient(reply=response("  Hi there \n"))

        self.assertEqual(self.complete_with(client), "Hi there")


def sdk_errors():
    """One of each kind of error the SDK raises, built as it builds them. The
    authentication error's text echoes a key, as the real API's does."""
    request = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")

    def status(code):
        return {"response": httpx2.Response(code, request=request), "body": None}

    return [
        openai.APIConnectionError(request=request),
        openai.APITimeoutError(request=request),
        openai.AuthenticationError(
            f"Incorrect API key provided: {KEY_LIKE}", **status(401)
        ),
        openai.RateLimitError("Rate limit reached", **status(429)),
        openai.InternalServerError("The server had an error", **status(500)),
    ]


@override_settings(OPENAI_API_KEY=KEY_LIKE)
class CompleteErrorTests(NoNetworkTestCase):
    SAFE_MESSAGE = "The AI service is unavailable right now. Please try again later."

    def failing_with(self, error):
        return patch("ai.services.get_client", return_value=FakeClient(error=error))

    def test_every_sdk_error_becomes_one_safe_ai_service_error(self):
        for error in sdk_errors():
            with self.subTest(error=type(error).__name__):
                with (
                    self.failing_with(error),
                    self.assertLogs("ai.services", "ERROR"),
                    self.assertRaises(self.services.AIServiceError) as raised,
                ):
                    self.services.complete("Be brief.", "Hi")

                self.assertEqual(str(raised.exception), self.SAFE_MESSAGE)
                self.assertIs(raised.exception.__cause__, error)
                self.assertNotIn(KEY_LIKE, str(raised.exception))

    def test_each_failure_is_logged_once_by_type_without_the_key(self):
        for error in sdk_errors():
            with self.subTest(error=type(error).__name__):
                with (
                    self.failing_with(error),
                    self.assertLogs("ai.services", "ERROR") as logs,
                    self.assertRaises(self.services.AIServiceError),
                ):
                    self.services.complete("Be brief.", "Hi")

                (record,) = logs.records
                text = record.getMessage()
                self.assertEqual(record.levelname, "ERROR")
                self.assertIn(type(error).__name__, text)
                self.assertNotIn(KEY_LIKE, text)
                self.assertNotIn(str(error), text)
                # No traceback either: the SDK error's text would be in it.
                self.assertIsNone(record.exc_info)


class CompleteEmptyReplyTests(NoNetworkTestCase):
    def test_a_reply_without_content_is_an_ai_service_error(self):
        cases = {
            "no choices": response(),
            "no content": response(None),
            "blank content": response(" \n\t "),
        }
        for case, reply in cases.items():
            with self.subTest(case=case):
                with (
                    patch(
                        "ai.services.get_client",
                        return_value=FakeClient(reply=reply),
                    ),
                    self.assertLogs("ai.services", "ERROR") as logs,
                    self.assertRaises(self.services.AIServiceError) as raised,
                ):
                    self.services.complete("Be brief.", "Hi")

                self.assertEqual(
                    str(raised.exception), "The AI service returned an empty reply."
                )
                (record,) = logs.records
                self.assertIn("empty reply", record.getMessage())
