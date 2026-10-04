import importlib.util
import re
from datetime import timedelta

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import F
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

    def fail_log_ins(self, times, username=USERNAME, ip="127.0.0.1"):
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
                first_four = self.fail_log_ins(4, username, ip)
                for response in first_four:
                    self.assertEqual(response.status_code, 200)
                    page = PageParser()
                    page.feed(response.content.decode())
                    self.assertIn(INVALID_LOGIN, page.text("main"))

                # django-axes refuses the 5th failure itself.
                (fifth,) = self.fail_log_ins(1, username, ip)
                sixth = self.log_in(username, PASSWORD, ip)

                self.assertEqual(fifth.status_code, 429)
                self.assertEqual(sixth.status_code, 429)
                self.assert_logged_out()

    def test_the_lockout_is_per_username_and_ip_address(self):
        self.assertEqual(
            getattr(settings, "AXES_LOCKOUT_PARAMETERS", None),
            [["username", "ip_address"]],
        )

    def test_usernames_are_counted_casefolded(self):
        self.assertEqual(
            getattr(settings, "AXES_USERNAME_CALLABLE", None),
            "accounts.lockout.lockout_username",
        )

    def test_case_variants_of_a_username_share_one_counter(self):
        # On a database that matches usernames regardless of case, each
        # variant would log in as alice: they must not get 5 tries each.
        for variant in ("Alice", "ALICE", "alice", "aLiCe", "ALICe"):
            self.log_in(variant, WRONG_PASSWORD)

        response = self.log_in(USERNAME, PASSWORD)

        self.assertEqual(response.status_code, 429)
        self.assert_logged_out()

    def test_a_locked_out_username_can_still_log_in_from_another_ip(self):
        self.fail_log_ins(5, USERNAME, "127.0.0.1")

        response = self.log_in(USERNAME, PASSWORD, "10.0.0.2")

        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_another_username_can_still_log_in_from_a_locked_out_ip(self):
        get_user_model().objects.create_user("bob", password=PASSWORD)
        self.fail_log_ins(5, USERNAME, "127.0.0.1")

        response = self.log_in("bob", PASSWORD, "127.0.0.1")

        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)


LOCKED_OUT = "Too many failed log-in attempts. Try again in 15 minutes."


class ResetOnSuccessTests(LockoutTestCase):
    def test_a_successful_log_in_resets_the_count(self):
        self.assertIs(getattr(settings, "AXES_RESET_ON_SUCCESS", None), True)

    def test_failures_before_a_successful_log_in_no_longer_count(self):
        self.fail_log_ins(4)
        self.log_in(USERNAME, PASSWORD)
        self.client.post("/accounts/logout/")

        after = self.fail_log_ins(4)
        response = self.log_in(USERNAME, PASSWORD)

        self.assertEqual([r.status_code for r in after], [200] * 4)
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)


class CoolOffTests(LockoutTestCase):
    def age_failures(self, **delta):
        """Moves every recorded failure back in time, as if it were older."""
        AccessAttempt.objects.update(
            attempt_time=F("attempt_time") - timedelta(**delta)
        )

    def test_the_cool_off_matches_the_lockout_page(self):
        # The page says "Try again in 15 minutes" (LOCKED_OUT).
        self.assertEqual(
            getattr(settings, "AXES_COOLOFF_TIME", None), timedelta(minutes=15)
        )

    def test_still_locked_out_14_minutes_after_the_last_failure(self):
        self.fail_log_ins(5)
        self.age_failures(minutes=14)

        response = self.log_in(USERNAME, PASSWORD)

        self.assertEqual(response.status_code, 429)
        self.assert_logged_out()

    def test_the_right_password_logs_in_15_minutes_after_the_last_failure(self):
        self.fail_log_ins(5)
        self.age_failures(minutes=15)

        response = self.log_in(USERNAME, PASSWORD)

        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)


class LockoutPageTests(LockoutTestCase):
    def locked_out_page(self, response):
        page = PageParser()
        page.feed(response.content.decode())
        return page

    def test_the_lockout_page_says_when_to_try_again(self):
        self.fail_log_ins(5)

        response = self.log_in(USERNAME, PASSWORD)

        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, "accounts/locked_out.html")
        self.assertTemplateUsed(response, "base.html")
        page = self.locked_out_page(response)
        self.assertEqual(page.text("title"), "Locked out · Learning Companion")
        self.assertEqual([tag for tag, _ in page.elements].count("h1"), 1)
        self.assertIn(LOCKED_OUT, page.text("main"))

    def test_the_lockout_page_names_no_account(self):
        # The same page for an existing and a missing username: it neither
        # echoes the username nor tells whether the account exists.
        (alice,) = self.fail_log_ins(5, USERNAME, "10.0.0.1")[-1:]
        (nobody,) = self.fail_log_ins(5, "nobody", "10.0.0.9")[-1:]

        self.assertNotIn(USERNAME, alice.content.decode())
        self.assertNotIn("nobody", nobody.content.decode())
        self.assertEqual(
            self.locked_out_page(alice).text("main"),
            self.locked_out_page(nobody).text("main"),
        )

    def test_the_admin_log_in_is_locked_out_the_same_way(self):
        for _ in range(5):
            response = self.client.post(
                "/admin/login/?next=/admin/",
                {"username": USERNAME, "password": WRONG_PASSWORD, "next": "/admin/"},
            )

        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, "accounts/locked_out.html")
        self.assertIn(LOCKED_OUT, self.locked_out_page(response).text("main"))
