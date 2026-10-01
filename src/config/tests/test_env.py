from pathlib import Path

from django.test import SimpleTestCase

from config.env import resolve_settings

MISSING_ENV_FILE = Path(__file__).parent / "no-such.env"


class ResolveSettingsTests(SimpleTestCase):
    def resolve(self, environ, env_file=MISSING_ENV_FILE):
        return resolve_settings(environ, env_file)

    def test_secret_key_comes_from_environment(self):
        settings = self.resolve({"SECRET_KEY": "from-env"})

        self.assertEqual(settings.secret_key, "from-env")
