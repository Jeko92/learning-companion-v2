from django.conf import settings
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


class DashboardAccessTests(TestCase):
    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.assertEqual(reverse("dashboard:index"), "/dashboard/")

        response = self.client.get("/dashboard/")

        self.assertRedirects(
            response, login_redirect("/dashboard/"), fetch_redirect_response=False
        )
