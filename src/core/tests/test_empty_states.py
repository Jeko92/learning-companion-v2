import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import collapse
from goals.models import Goal

PASSWORD = "Tr4ck-Learning!"
EMPTY_STATE = re.compile(r"<div data-empty-state[^>]*>(.*?)</div>", re.DOTALL)
LINK = re.compile(r'<a [^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
TAG = re.compile(r"<[^>]+>")


def empty_states(html):
    """(text, [(href, link text)]) for each empty-state block on the page."""
    found = []
    for inner in EMPTY_STATE.findall(html):
        links = [
            (href, collapse([TAG.sub("", text)])) for href, text in LINK.findall(inner)
        ]
        found.append((collapse([TAG.sub(" ", inner)]), links))
    return found


class EmptyStateTests(TestCase):
    """Empty lists keep their wording, in a styled block with the next action."""

    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(self.alice)

    def states(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return empty_states(response.content.decode())

    def test_no_goals_offers_to_create_one(self):
        self.assertEqual(
            self.states(reverse("goals:list")),
            [("No goals yet. New goal", [(reverse("goals:create"), "New goal")])],
        )

    def test_no_goals_with_a_status_has_no_call_to_action(self):
        Goal.objects.create(owner=self.alice, title="Learn Django")

        self.assertEqual(
            self.states(reverse("goals:list") + "?status=done"),
            [("No goals with this status.", [])],
        )

    def test_an_empty_goal_page_shows_each_section_as_empty(self):
        goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        add_session = reverse("learning_sessions:create", args=[goal.pk])

        self.assertEqual(
            self.states(goal.get_absolute_url()),
            [
                ("No summary yet.", []),
                ("No next steps yet.", []),
                ("No sessions yet. Add session", [(add_session, "Add session")]),
                ("No resources yet.", []),
            ],
        )

    def test_an_empty_session_list_offers_to_add_one(self):
        goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        add_session = reverse("learning_sessions:create", args=[goal.pk])

        self.assertEqual(
            self.states(reverse("learning_sessions:list", args=[goal.pk])),
            [("No sessions yet. Add session", [(add_session, "Add session")])],
        )

    def test_a_profile_without_focus_areas_offers_to_edit_it(self):
        pk = self.alice.profile.pk

        self.assertEqual(
            self.states(reverse("profiles:detail", args=[pk])),
            [
                (
                    "No focus areas yet. Edit profile",
                    [(reverse("profiles:edit", args=[pk]), "Edit profile")],
                )
            ],
        )

    def test_an_empty_dashboard_offers_a_first_goal_and_shows_no_sessions(self):
        self.assertEqual(
            self.states(reverse("dashboard:index")),
            [
                (
                    "No goals yet. Create your first goal",
                    [(reverse("goals:create"), "Create your first goal")],
                ),
                ("No sessions logged yet.", []),
            ],
        )
