from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.env import resolve_settings

MISSING_ENV_FILE = Path(__file__).parent / "no-such.env"


class ResolveSettingsTests(SimpleTestCase):
    def resolve(self, environ, env_file=MISSING_ENV_FILE):
        return resolve_settings(environ, env_file)

    def test_secret_key_comes_from_environment(self):
        settings = self.resolve({"SECRET_KEY": "from-env"})

        self.assertEqual(settings.secret_key, "from-env")

    def test_missing_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve({})

    def test_empty_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve({"SECRET_KEY": ""})

    def test_debug_is_parsed_as_boolean(self):
        cases = {
            "True": True,
            "1": True,
            "yes": True,
            "False": False,
            "0": False,
            "no": False,
        }
        for raw, expected in cases.items():
            with self.subTest(DEBUG=raw):
                settings = self.resolve({"SECRET_KEY": "x", "DEBUG": raw})

                self.assertIs(settings.debug, expected)
