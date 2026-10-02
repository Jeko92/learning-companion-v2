from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser
from goals.models import Goal

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

    def test_lists_only_your_goals_newest_first_with_status(self):
        older = Goal.objects.create(owner=self.alice, title="Read docs")
        Goal.objects.filter(pk=older.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        Goal.objects.create(
            owner=self.alice, title="Learn Django", status=Goal.Status.IN_PROGRESS
        )
        bob = get_user_model().objects.create_user("bob")
        Goal.objects.create(owner=bob, title="Bob's secret goal")

        main = get_page(self.client, "/goals/").text("main")

        self.assertIn("Learn Django", main)
        self.assertLess(main.index("Learn Django"), main.index("Read docs"))
        self.assertIn("In progress", main)
        self.assertNotIn("Bob's secret goal", main)

    def test_shows_an_empty_state_without_goals(self):
        main = get_page(self.client, "/goals/").text("main")

        self.assertIn("No goals yet.", main)


class GoalCreatePageTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(self.alice)

    def test_the_create_page_renders_a_goal_form(self):
        response = self.client.get("/goals/new/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "goals/goal_form.html")
        self.assertEqual(reverse("goals:create"), "/goals/new/")
        page = PageParser()
        page.feed(response.content.decode())
        ((attrs, inputs),) = page.forms("main")
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), "/goals/new/")
        self.assertLessEqual(
            {"csrfmiddlewaretoken", "title"}, {a.get("name") for a in inputs}
        )
        tags = [(tag, attrs) for tag, attrs in page.elements]
        self.assertIn(
            "description", {a.get("name") for t, a in tags if t == "textarea"}
        )
        self.assertIn("status", {a.get("name") for t, a in tags if t == "select"})
        options = [a for t, a in tags if t == "option"]
        self.assertEqual(
            [o.get("value") for o in options], ["planned", "in-progress", "done"]
        )
        self.assertIn("selected", options[0])
        self.assertNotIn("owner", {a.get("name") for _, a in tags})

    def test_the_list_links_to_the_create_page(self):
        page = get_page(self.client, "/goals/")

        self.assertIn(("/goals/new/", "New goal"), page.links("main"))


class GoalCreateTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(self.alice)
        self.data = {
            "title": "  Learn Django ",
            "description": "Parts 1-7",
            "status": "in-progress",
        }

    def test_a_valid_create_saves_your_goal_and_returns_to_the_list(self):
        response = self.client.post("/goals/new/", self.data)

        self.assertRedirects(response, "/goals/", fetch_redirect_response=False)
        goal = Goal.objects.get()
        self.assertEqual(
            (goal.owner, goal.title, goal.status),
            (self.alice, "Learn Django", Goal.Status.IN_PROGRESS),
        )
        followed = self.client.get("/goals/")
        self.assertContains(followed, "Goal created.")
        page = PageParser()
        page.feed(followed.content.decode())
        self.assertTrue(
            page.text("main").startswith("Your goals New goal Learn Django")
        )

    def test_a_posted_owner_is_ignored(self):
        bob = get_user_model().objects.create_user("bob")

        self.client.post("/goals/new/", {**self.data, "owner": bob.pk})

        self.assertEqual(Goal.objects.get().owner, self.alice)
        self.assertFalse(bob.goals.exists())
