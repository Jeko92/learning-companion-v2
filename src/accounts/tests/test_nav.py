from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser

USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


class NavTests(TestCase):
    def get_page(self):
        response = self.client.get("/")
        page = PageParser()
        page.feed(response.content.decode())
        return page

    def log_in(self):
        user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.client.force_login(user)

    def test_anonymous_nav_has_goals_and_login_and_signup_links(self):
        # auth-login-logout made "Log in" a real link; it was a placeholder
        # until then (#2 AC4, #3 AC9). "Goals" stays a non-link placeholder.
        page = self.get_page()

        self.assertEqual(
            page.links("nav"),
            [
                (reverse("accounts:login"), "Log in"),
                (reverse("accounts:signup"), "Sign up"),
            ],
        )
        # Exact text guards against stray nav text. "No username for anonymous
        # visitors" holds by construction: AnonymousUser.get_username() is "".
        self.assertEqual(page.text("nav"), "Goals Log in Sign up")
        self.assertNotIn("Goals", page.href_text())

    def test_logged_in_nav_has_username_and_logout_form_and_no_auth_links(self):
        self.log_in()

        page = self.get_page()

        self.assertEqual(page.links("nav"), [])
        # Exact text: Goals, the username and the Log out button, nothing else.
        # (#3 pinned "Goals <username>"; auth-login-logout adds Log out.)
        self.assertEqual(page.text("nav"), f"Goals {USERNAME} Log out")
        ((attrs, inputs),) = page.forms("nav")
        # Only method and action, so styling attributes can't break the test.
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), reverse("accounts:logout"))
        self.assertIn("csrfmiddlewaretoken", {a.get("name") for a in inputs})

    def test_logged_in_nav_shows_the_username(self):
        self.log_in()

        page = self.get_page()

        self.assertIn(USERNAME, page.text("nav"))
