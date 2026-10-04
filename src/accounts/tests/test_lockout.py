import importlib.util
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from accounts.tests.test_login import INVALID_LOGIN, LOGIN_PATH, PASSWORD, USERNAME
from core.tests.html import PageParser

REQUIREMENTS = settings.BASE_DIR.parent / "requirements.txt"
WRONG_PASSWORD = "not-the-password"


class LockoutTestCase(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def log_in(self, username, password, ip="127.0.0.1"):
        return self.client.post(
            LOGIN_PATH,
            {"username": username, "password": password},
            REMOTE_ADDR=ip,
        )

    def fail(self, times, username=USERNAME, ip="127.0.0.1"):
        return [self.log_in(username, WRONG_PASSWORD, ip) for _ in range(times)]

    def assert_logged_out(self):
        self.assertNotIn("_auth_user_id", self.client.session)


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


class LockoutTests(LockoutTestCase):
    def test_the_failure_limit_is_five(self):
        self.assertEqual(settings.AXES_FAILURE_LIMIT, 5)

    def test_after_five_failures_even_the_right_password_is_refused(self):
        # A username that doesn't exist is counted the same way, so the
        # lockout doesn't tell whether an account exists. Separate IPs keep
        # the two cases apart.
        for username, ip in ((USERNAME, "10.0.0.1"), ("nobody", "10.0.0.9")):
            with self.subTest(username=username):
                first_four = self.fail(4, username, ip)
                for response in first_four:
                    self.assertEqual(response.status_code, 200)
                    page = PageParser()
                    page.feed(response.content.decode())
                    self.assertIn(INVALID_LOGIN, page.text("main"))

                # django-axes refuses the 5th failure itself.
                (fifth,) = self.fail(1, username, ip)
                sixth = self.log_in(username, PASSWORD, ip)

                self.assertEqual(fifth.status_code, 429)
                self.assertEqual(sixth.status_code, 429)
                self.assert_logged_out()
