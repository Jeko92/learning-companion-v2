from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser

PASSWORD = "Tr4ck-Learning!"


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


class DashboardAccessTests(TestCase):
    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.assertEqual(reverse("dashboard:index"), "/dashboard/")

        response = self.client.get("/dashboard/")

        self.assertRedirects(
            response, login_redirect("/dashboard/"), fetch_redirect_response=False
        )

    def test_a_post_is_not_allowed(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(alice)

        response = self.client.post("/dashboard/")

        self.assertEqual(response.status_code, 405)


class DashboardPageTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(self.alice)

    def test_the_dashboard_is_served_with_its_title_and_heading(self):
        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/dashboard.html")
        self.assertTemplateUsed(response, "base.html")
        page = PageParser()
        page.feed(response.content.decode())
        self.assertEqual(page.text("title"), "Dashboard · Learning Companion")
        self.assertRegex(response.content.decode(), r"<h1[^>]*>\s*Dashboard\s*</h1>")
