from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from goals.models import Goal


class GoalAdminTests(TestCase):
    def test_goal_is_registered_with_list_filter_and_search(self):
        self.assertIn(Goal, admin.site._registry)
        goal_admin = admin.site._registry[Goal]

        for column in ("title", "owner", "status", "created_at"):
            with self.subTest(column=column):
                self.assertIn(column, goal_admin.list_display)
        self.assertIn("status", goal_admin.list_filter)
        self.assertIn("title", goal_admin.search_fields)

    def test_changelist_lists_goals(self):
        User = get_user_model()
        self.client.force_login(User.objects.create_superuser("admin", password="x"))
        Goal.objects.create(
            owner=User.objects.create_user("alice"), title="Learn Django"
        )

        response = self.client.get(reverse("admin:goals_goal_changelist"))

        self.assertContains(response, "Learn Django")

    def test_the_change_page_links_to_the_goal_on_the_site(self):
        User = get_user_model()
        self.client.force_login(User.objects.create_superuser("admin", password="x"))
        goal = Goal.objects.create(owner=User.objects.create_user("alice"), title="x")

        response = self.client.get(reverse("admin:goals_goal_change", args=[goal.pk]))

        self.assertContains(response, 'class="viewsitelink"')
