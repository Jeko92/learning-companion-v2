from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser
from goals.models import Goal
from resources.models import Resource

PASSWORD = "Tr4ck-Learning!"


class ResourceAdminTests(TestCase):
    def setUp(self):
        self.assertIn(Resource, admin.site._registry)
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser("admin", password=PASSWORD)
        )
        goal = Goal.objects.create(
            owner=User.objects.create_user("alice"), title="Learn Django"
        )
        self.resource = Resource.objects.create(
            goal=goal, title="Read the docs", url="https://docs.djangoproject.com/"
        )

    def test_the_changelist_shows_title_type_and_goal(self):
        resource_admin = admin.site._registry[Resource]

        for column in ("title", "type", "goal"):
            with self.subTest(column=column):
                self.assertIn(column, resource_admin.list_display)
        self.assertIn("type", resource_admin.list_filter)
        for field in ("title", "url"):
            with self.subTest(search=field):
                self.assertIn(field, resource_admin.search_fields)

        response = self.client.get(reverse("admin:resources_resource_changelist"))

        self.assertContains(response, "Read the docs")

    def test_the_goal_is_picked_with_autocomplete(self):
        response = self.client.get(reverse("admin:resources_resource_add"))
        self.assertEqual(response.status_code, 200)
        page = PageParser()
        page.feed(response.content.decode())
        selects = {
            attrs.get("name"): attrs for tag, attrs in page.elements if tag == "select"
        }

        self.assertIn("goal", selects)
        self.assertIn("admin-autocomplete", selects["goal"].get("class", "").split())
