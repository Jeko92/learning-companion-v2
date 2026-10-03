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

    def test_anonymous_nav_has_only_login_and_signup_links(self):
        # goal-list-create removed the "Goals" placeholder for anonymous
        # visitors (#2 AC4, #3 AC9 pinned it); it's a link once logged in.
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
        self.assertEqual(page.text("nav"), "Log in Sign up")

    def test_logged_in_nav_links_dashboard_goals_the_profile_and_has_logout(self):
        # profile-page made the username a link to /profile/ (#4 AC10 had no
        # links); goal-list-create made "Goals" a link to /goals/;
        # dashboard-status put "Dashboard" first.
        self.log_in()

        page = self.get_page()

        self.assertEqual(
            page.links("nav"),
            [
                (reverse("dashboard:index"), "Dashboard"),
                (reverse("goals:list"), "Goals"),
                (reverse("profiles:mine"), USERNAME),
            ],
        )
        # Exact text: Dashboard, Goals, the username and the Log out button,
        # nothing else. (#3 pinned "Goals <username>"; auth-login-logout adds
        # Log out.)
        self.assertEqual(page.text("nav"), f"Dashboard Goals {USERNAME} Log out")
        ((attrs, inputs),) = page.forms("nav")
        # Only method and action, so styling attributes can't break the test.
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), reverse("accounts:logout"))
        self.assertIn("csrfmiddlewaretoken", {a.get("name") for a in inputs})

    def test_logged_in_nav_shows_the_username(self):
        self.log_in()

        page = self.get_page()

        self.assertIn(USERNAME, page.text("nav"))
