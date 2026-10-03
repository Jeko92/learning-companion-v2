import importlib
import importlib.util
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


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
