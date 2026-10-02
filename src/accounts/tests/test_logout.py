from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse

from accounts.tests.test_login import UNSAFE_NEXTS
from core.tests.html import PageParser

LOGOUT_PATH = "/accounts/logout/"
USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


class LogoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.client.force_login(self.user)

    def test_post_logs_out_and_redirects_with_a_message(self):
        response = self.client.post(LOGOUT_PATH)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(reverse("accounts:logout"), LOGOUT_PATH)
        self.assertEqual(settings.LOGOUT_REDIRECT_URL, "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False
        )

    def test_landing_page_says_the_user_logged_out(self):
        response = self.client.post(LOGOUT_PATH, follow=True)

        self.assertContains(response, "You have been logged out.")

    def test_unsafe_next_is_never_followed(self):
        # LogoutView honours a posted next only after the same same-site check
        # as login.
        for payload in UNSAFE_NEXTS:
            with self.subTest(payload=payload):
                self.client.force_login(self.user)

                response = self.client.post(LOGOUT_PATH, {"next": payload})

                self.assertNotIn("_auth_user_id", self.client.session)
                self.assertRedirects(
                    response,
                    settings.LOGOUT_REDIRECT_URL,
                    fetch_redirect_response=False,
                )

    def test_get_is_not_allowed_and_keeps_the_user_logged_in(self):
        response = self.client.get(LOGOUT_PATH)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))


class SessionLifecycleTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def session_key(self):
        return self.client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_login_replaces_the_session_key(self):
        # An anonymous session that an attacker could have planted (fixation).
        session = self.client.session
        session["probe"] = "anonymous"
        session.save()
        anonymous_key = session.session_key

        self.client.post(
            reverse("accounts:login"), {"username": USERNAME, "password": PASSWORD}
        )

        self.assertNotEqual(self.session_key(), anonymous_key)
        self.assertFalse(Session.objects.filter(session_key=anonymous_key).exists())

    def test_logout_invalidates_the_old_session(self):
        self.client.post(
            reverse("accounts:login"), {"username": USERNAME, "password": PASSWORD}
        )
        old_key = self.session_key()

        self.client.post(LOGOUT_PATH)
        self.client.cookies[settings.SESSION_COOKIE_NAME] = old_key
        response = self.client.get("/")

        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertIs(response.wsgi_request.user.is_authenticated, False)


class CsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        self.user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.csrf_client = Client(enforce_csrf_checks=True)

    def test_login_without_a_csrf_token_is_rejected(self):
        response = self.csrf_client.post(
            reverse("accounts:login"), {"username": USERNAME, "password": PASSWORD}
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", self.csrf_client.session)

    def test_logout_without_a_csrf_token_is_rejected(self):
        self.csrf_client.force_login(self.user)

        response = self.csrf_client.post(LOGOUT_PATH)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.csrf_client.session.get("_auth_user_id"), str(self.user.pk)
        )

    def test_logout_with_the_token_from_the_nav_form_succeeds(self):
        self.csrf_client.force_login(self.user)
        page = PageParser()
        page.feed(self.csrf_client.get("/").content.decode())
        ((_, inputs),) = page.forms("nav")
        tokens = [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]
        self.assertEqual(len(tokens), 1, "the nav logout form has no CSRF token")
        token = tokens[0]

        response = self.csrf_client.post(LOGOUT_PATH, {"csrfmiddlewaretoken": token})

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.csrf_client.session)


class RoundTripTests(TestCase):
    def test_sign_up_log_out_and_log_back_in(self):
        self.client.post(
            reverse("accounts:signup"),
            {"username": USERNAME, "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(LOGOUT_PATH)
        self.assertNotIn("_auth_user_id", self.client.session)

        self.client.post(
            reverse("accounts:login"), {"username": USERNAME, "password": PASSWORD}
        )
        self.assertIn("_auth_user_id", self.client.session)
        page = PageParser()
        page.feed(self.client.get("/").content.decode())
        self.assertIn(USERNAME, page.text("nav"))
