from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser
from goals.models import Goal
from learning_sessions.models import LearningSession

PASSWORD = "Tr4ck-Learning!"


class LearningSessionAdminTests(TestCase):
    def setUp(self):
        self.assertIn(LearningSession, admin.site._registry)
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser("admin", password=PASSWORD)
        )
        goal = Goal.objects.create(
            owner=User.objects.create_user("alice"), title="Learn Django"
        )
        self.session = LearningSession.objects.create(
            goal=goal, date=date(2026, 3, 10), duration_minutes=45
        )

    def test_the_changelist_shows_goal_date_and_duration(self):
        session_admin = admin.site._registry[LearningSession]

        for column in ("goal", "date", "duration_minutes"):
            with self.subTest(column=column):
                self.assertIn(column, session_admin.list_display)
        self.assertIn("date", session_admin.list_filter)

        response = self.client.get(
            reverse("admin:learning_sessions_learningsession_changelist")
        )

        self.assertContains(response, str(self.session))

    def test_goal_and_tags_are_picked_with_autocomplete(self):
        response = self.client.get(
            reverse("admin:learning_sessions_learningsession_add")
        )
        self.assertEqual(response.status_code, 200)
        page = PageParser()
        page.feed(response.content.decode())
        selects = {
            attrs.get("name"): attrs for tag, attrs in page.elements if tag == "select"
        }

        for name in ("goal", "tags"):
            with self.subTest(field=name):
                self.assertIn(name, selects)
                self.assertIn(
                    "admin-autocomplete", selects[name].get("class", "").split()
                )
