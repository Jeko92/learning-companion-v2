import importlib
import os
from pathlib import Path
from unittest import mock

from django.conf import settings
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
    # Never opened: reloading settings doesn't touch the live connections.
    "DATABASE_URL": "sqlite:////wiring-test/db.sqlite3",
    "CSRF_TRUSTED_ORIGINS": "https://wiring.example, https://other.example",
    # With DEBUG on, each of these defaults to off.
    "SECURE_SSL_REDIRECT": "True",
    "SESSION_COOKIE_SECURE": "True",
    "CSRF_COOKIE_SECURE": "True",
    "SECURE_HSTS_SECONDS": "7200",
    "SECURE_PROXY_SSL_HEADER": "True",
}

# Blank means the default; it also beats a developer's .env.
HTTPS_DEFAULTS = {
    "SECURE_SSL_REDIRECT": "",
    "SESSION_COOKIE_SECURE": "",
    "CSRF_COOKIE_SECURE": "",
    "SECURE_HSTS_SECONDS": "",
    "SECURE_PROXY_SSL_HEADER": "",
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

    def test_the_database_comes_from_database_url(self):
        default = settings_module.DATABASES["default"]

        self.assertEqual(default["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(default["NAME"], "/wiring-test/db.sqlite3")

    def test_a_blank_database_url_keeps_the_sqlite_file_in_src(self):
        self.reload_with(DATABASE_URL="")

        self.assertEqual(
            settings_module.DATABASES,
            {
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": settings_module.BASE_DIR / "db.sqlite3",
                }
            },
        )

    def test_csrf_trusted_origins_come_from_the_environment(self):
        self.assertEqual(
            getattr(settings_module, "CSRF_TRUSTED_ORIGINS", None),
            ["https://wiring.example", "https://other.example"],
        )

    def test_csrf_trusted_origins_are_empty_when_blank(self):
        self.reload_with(CSRF_TRUSTED_ORIGINS="")

        self.assertEqual(getattr(settings_module, "CSRF_TRUSTED_ORIGINS", None), [])

    def https_settings(self):
        return {
            name: getattr(settings_module, name, None)
            for name in (
                "SECURE_SSL_REDIRECT",
                "SESSION_COOKIE_SECURE",
                "CSRF_COOKIE_SECURE",
                "SECURE_HSTS_SECONDS",
                "SECURE_PROXY_SSL_HEADER",
            )
        }

    def test_https_settings_come_from_the_environment(self):
        self.assertEqual(
            self.https_settings(),
            {
                "SECURE_SSL_REDIRECT": True,
                "SESSION_COOKIE_SECURE": True,
                "CSRF_COOKIE_SECURE": True,
                "SECURE_HSTS_SECONDS": 7200,
                "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
            },
        )

    def test_https_settings_are_on_by_default_without_debug(self):
        self.reload_with(DEBUG="False", **HTTPS_DEFAULTS)

        self.assertEqual(
            self.https_settings(),
            {
                "SECURE_SSL_REDIRECT": True,
                "SESSION_COOKIE_SECURE": True,
                "CSRF_COOKIE_SECURE": True,
                "SECURE_HSTS_SECONDS": 3600,
                "SECURE_PROXY_SSL_HEADER": None,
            },
        )

    def test_https_settings_are_off_by_default_with_debug(self):
        self.reload_with(DEBUG="True", **HTTPS_DEFAULTS)

        self.assertEqual(
            self.https_settings(),
            {
                "SECURE_SSL_REDIRECT": False,
                "SESSION_COOKIE_SECURE": False,
                "CSRF_COOKIE_SECURE": False,
                "SECURE_HSTS_SECONDS": 0,
                "SECURE_PROXY_SSL_HEADER": None,
            },
        )

    def test_mail_goes_to_the_console_only_with_debug(self):
        # check --deploy rejects the console backend (mail.E001).
        cases = {
            "True": "django.core.mail.backends.console.EmailBackend",
            "False": "django.core.mail.backends.smtp.EmailBackend",
        }
        for raw, backend in cases.items():
            with self.subTest(DEBUG=raw):
                self.reload_with(DEBUG=raw)

                self.assertEqual(
                    settings_module.MAILERS, {"default": {"BACKEND": backend}}
                )

    def test_generated_secret_key_is_not_hardcoded(self):
        self.assertNotIn("django-insecure", SETTINGS_FILE.read_text())

    def test_no_openai_key_is_hardcoded(self):
        self.assertNotIn("sk-", SETTINGS_FILE.read_text())


class StaticFilesSettingsTests(SimpleTestCase):
    """Outside runserver, WhiteNoise serves the files collectstatic gathers."""

    def test_static_files_are_collected_into_a_git_ignored_directory(self):
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / "staticfiles")
        gitignore = (settings.BASE_DIR.parent / ".gitignore").read_text().splitlines()
        self.assertIn("staticfiles/", gitignore)

    def test_whitenoise_middleware_comes_right_after_the_security_middleware(self):
        self.assertEqual(
            settings.MIDDLEWARE[:2],
            [
                "django.middleware.security.SecurityMiddleware",
                "whitenoise.middleware.WhiteNoiseMiddleware",
            ],
        )

    def test_static_files_are_stored_compressed_without_hashed_names(self):
        # Hashed (manifest) names would change every {% static %} URL and need
        # collectstatic before any page renders, also in tests.
        self.assertEqual(
            settings.STORAGES,
            {
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
                },
            },
        )
