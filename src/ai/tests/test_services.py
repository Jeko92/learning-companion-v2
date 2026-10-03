import importlib
import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


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
