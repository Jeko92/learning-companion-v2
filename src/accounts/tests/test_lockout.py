import importlib.util
import re

from django.conf import settings
from django.test import SimpleTestCase

REQUIREMENTS = settings.BASE_DIR.parent / "requirements.txt"


class LockoutWiringTests(SimpleTestCase):
    """Failed log-ins are counted and locked out by django-axes, for the app's
    log-in and the admin's alike (both call authenticate() with the request)."""

    def test_django_axes_is_a_pinned_requirement(self):
        lines = REQUIREMENTS.read_text().splitlines()

        self.assertIn("django-axes>=8.3,<8.4", lines)
        self.assertEqual(
            [line for line in lines if re.match(r"django-axes\b", line)],
            ["django-axes>=8.3,<8.4"],
        )
        self.assertIsNotNone(importlib.util.find_spec("axes"), "axes isn't installed")

    def test_the_app_and_its_middleware_are_installed(self):
        self.assertIn("axes", settings.INSTALLED_APPS)
        # Last, as django-axes requires: it swaps in the lockout response
        # after the view ran.
        self.assertEqual(settings.MIDDLEWARE[-1], "axes.middleware.AxesMiddleware")

    def test_the_axes_backend_checks_before_the_model_backend_logs_in(self):
        self.assertEqual(
            settings.AUTHENTICATION_BACKENDS,
            [
                "axes.backends.AxesStandaloneBackend",
                "django.contrib.auth.backends.ModelBackend",
            ],
        )

    def test_failures_are_stored_in_the_database_and_refused_with_429(self):
        self.assertIsNotNone(importlib.util.find_spec("axes"), "axes isn't installed")
        from axes.conf import settings as axes_settings

        # The database handler: every gunicorn worker sees the same counts
        # (a cache would be per process with the default local-memory cache).
        self.assertEqual(
            axes_settings.AXES_HANDLER, "axes.handlers.database.AxesDatabaseHandler"
        )
        self.assertEqual(axes_settings.AXES_HTTP_RESPONSE_CODE, 429)
