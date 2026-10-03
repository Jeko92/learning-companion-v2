import importlib
import os
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from config import settings as settings_module

SETTINGS_FILE = Path(settings_module.__file__)

# Values that differ from the code defaults and from .env.example, so a
# hardcoded value in settings.py cannot pass by coincidence. The process
# environment wins over .env, so these also override a developer's .env.
PATCHED_ENVIRON = {
    "SECRET_KEY": "wiring-test-secret-key",
    "DEBUG": "True",
    "ALLOWED_HOSTS": "wiring.example, other.example",
    "OPENAI_API_KEY": "sk-wiring-test-key",
    "OPENAI_MODEL": "wiring-test-model",
}


class SettingsWiringTests(SimpleTestCase):
    def setUp(self):
        # Cleanups run last-in-first-out: restore os.environ, then reload the
        # module so it holds the real values again.
        self.addCleanup(importlib.reload, settings_module)
        self.enterContext(mock.patch.dict(os.environ, PATCHED_ENVIRON))
        importlib.reload(settings_module)

    def reload_with(self, **overrides):
        with mock.patch.dict(os.environ, overrides):
            importlib.reload(settings_module)

    def test_secret_key_comes_from_the_environment(self):
        # Compare without assertEqual so a failure never prints the secret.
        self.assertTrue(
            settings_module.SECRET_KEY == PATCHED_ENVIRON["SECRET_KEY"],
            "SECRET_KEY in config.settings does not come from the environment",
        )

    def test_debug_comes_from_the_environment(self):
        # Check both values: a hardcoded DEBUG could match either one.
        for raw, expected in {"True": True, "False": False}.items():
            with self.subTest(DEBUG=raw):
                self.reload_with(DEBUG=raw)

                self.assertIs(settings_module.DEBUG, expected)

    def test_allowed_hosts_come_from_the_environment(self):
        self.assertEqual(
            settings_module.ALLOWED_HOSTS, ["wiring.example", "other.example"]
        )

    def test_openai_api_key_comes_from_the_environment(self):
        # Compare without assertEqual so a failure never prints the key.
        self.assertTrue(
            getattr(settings_module, "OPENAI_API_KEY", None)
            == PATCHED_ENVIRON["OPENAI_API_KEY"],
            "OPENAI_API_KEY in config.settings does not come from the environment",
        )

    def test_openai_model_comes_from_the_environment(self):
        self.assertEqual(
            getattr(settings_module, "OPENAI_MODEL", None), "wiring-test-model"
        )

    def test_openai_model_defaults_when_blank(self):
        # Blank rather than unset: an empty value also beats a developer's
        # .env, and means the default.
        self.reload_with(OPENAI_MODEL="")

        self.assertEqual(getattr(settings_module, "OPENAI_MODEL", None), "gpt-4.1-mini")

    def test_generated_secret_key_is_not_hardcoded(self):
        self.assertNotIn("django-insecure", SETTINGS_FILE.read_text())

    def test_no_openai_key_is_hardcoded(self):
        self.assertNotIn("sk-", SETTINGS_FILE.read_text())
