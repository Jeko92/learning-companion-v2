from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser

PASSWORD = "Tr4ck-Learning!"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


class GoalListTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(self.alice)

    def test_the_goals_list_is_served(self):
        response = self.client.get("/goals/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "goals/goal_list.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(reverse("goals:list"), "/goals/")

    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.client.logout()

        response = self.client.get("/goals/")

        self.assertRedirects(
            response, login_redirect("/goals/"), fetch_redirect_response=False
        )
