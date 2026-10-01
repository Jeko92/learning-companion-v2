import os
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from config import settings as settings_module
from config.env import resolve_settings

SETTINGS_FILE = Path(settings_module.__file__)


class SettingsWiringTests(SimpleTestCase):
    def setUp(self):
        self.expected = resolve_settings(os.environ, settings.BASE_DIR.parent / ".env")

    def test_secret_key_comes_from_resolve_settings(self):
        # Compare without assertEqual so a failure never prints the secret.
        self.assertTrue(
            settings.SECRET_KEY == self.expected.secret_key,
            "settings.SECRET_KEY does not match the resolved SECRET_KEY",
        )

    def test_allowed_hosts_come_from_resolve_settings(self):
        # The test runner appends "testserver" to ALLOWED_HOSTS.
        self.assertEqual(
            [host for host in settings.ALLOWED_HOSTS if host != "testserver"],
            self.expected.allowed_hosts,
        )

    def test_debug_comes_from_resolve_settings(self):
        # The test runner forces settings.DEBUG to False, so check the module value.
        self.assertIs(settings_module.DEBUG, self.expected.debug)

    def test_generated_secret_key_is_not_hardcoded(self):
        self.assertNotIn("django-insecure", SETTINGS_FILE.read_text())
