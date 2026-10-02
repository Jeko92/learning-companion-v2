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

    def test_anonymous_nav_has_placeholders_and_a_signup_link(self):
        page = self.get_page()

        self.assertEqual(page.links("nav"), [(reverse("accounts:signup"), "Sign up")])
        for placeholder in ("Goals", "Log in"):
            with self.subTest(placeholder=placeholder):
                self.assertIn(placeholder, page.text("nav"))
                self.assertNotIn(placeholder, page.href_text())

    def test_logged_in_nav_has_no_login_placeholder_and_no_signup_link(self):
        self.log_in()

        page = self.get_page()

        self.assertEqual(page.links("nav"), [])
        self.assertIn("Goals", page.text("nav"))
        self.assertNotIn("Log in", page.text("nav"))
