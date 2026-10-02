from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from core.tests.html import PageParser

LOGIN_PATH = "/accounts/login/"
USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


class LoginPageTests(TestCase):
    def test_login_page_is_served_at_the_login_url(self):
        response = self.client.get(LOGIN_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(reverse("accounts:login"), LOGIN_PATH)
        self.assertEqual(resolve_url(settings.LOGIN_URL), LOGIN_PATH)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertTemplateUsed(response, "base.html")

    def test_login_page_renders_the_login_form(self):
        page = get_page(self.client, LOGIN_PATH)

        forms = page.forms("main")
        self.assertEqual(
            [attrs for attrs, _ in forms],
            [{"method": "post", "action": reverse("accounts:login")}],
        )
        input_names = {attrs.get("name") for attrs in forms[0][1]}
        self.assertLessEqual(
            {"csrfmiddlewaretoken", "username", "password"}, input_names
        )

    def test_no_password_reset_or_change_routes_exist(self):
        # Only login and logout are wired, not django.contrib.auth.urls.
        for name in (
            "password_reset",
            "password_change",
            "accounts:password_reset",
            "accounts:password_change",
        ):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name)


class LoginSubmitTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def log_in(self, **extra):
        data = {"username": USERNAME, "password": PASSWORD, **extra}
        return self.client.post(LOGIN_PATH, data)

    def test_valid_login_logs_the_user_in_and_redirects(self):
        response = self.log_in()

        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
        self.assertRedirects(
            response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False
        )

    def test_landing_page_welcomes_the_user_back(self):
        response = self.client.post(
            LOGIN_PATH, {"username": USERNAME, "password": PASSWORD}, follow=True
        )

        self.assertContains(response, f"Welcome back, {USERNAME}!")
