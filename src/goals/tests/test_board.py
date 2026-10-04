"""The goal board: one column per status, goals moved between them by drag and
drop (SortableJS) or by each card's Move menu, both through goals:move."""

import json
from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from core.tests.html import PageParser
from goals.models import Goal

PASSWORD = "Tr4ck-Learning!"
JSON = {"HTTP_ACCEPT": "application/json"}


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


class MoveTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.path = reverse("goals:move", args=[self.goal.pk])
        self.client.force_login(self.alice)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class GoalMoveTests(MoveTestCase):
    def test_the_move_route(self):
        self.assertEqual(self.path, f"/goals/{self.goal.pk}/move/")

    def test_a_post_moves_the_goal_and_returns_to_the_board(self):
        response = self.client.post(self.path, {"status": "in-progress"})

        self.assertRedirects(response, "/goals/", fetch_redirect_response=False)
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.IN_PROGRESS)
        self.assertEqual(
            self.messages(response), ["Moved “Learn Django” to In progress."]
        )

    def test_a_move_updates_the_goals_updated_at(self):
        Goal.objects.filter(pk=self.goal.pk).update(
            updated_at=datetime(2026, 1, 1, tzinfo=UTC)
        )

        self.client.post(self.path, {"status": "done"})

        self.goal.refresh_from_db()
        self.assertGreater(self.goal.updated_at, datetime(2026, 1, 1, tzinfo=UTC))

    def test_a_same_site_next_is_followed(self):
        response = self.client.post(
            self.path, {"status": "done", "next": "/goals/?status=planned"}
        )

        self.assertRedirects(
            response, "/goals/?status=planned", fetch_redirect_response=False
        )

    def test_an_off_site_next_is_ignored(self):
        for next_url in ("https://evil.example/", "//evil.example/", "javascript:x"):
            with self.subTest(next=next_url):
                response = self.client.post(
                    self.path, {"status": "done", "next": next_url}
                )

                self.assertRedirects(response, "/goals/", fetch_redirect_response=False)

    def test_an_invalid_or_missing_status_changes_nothing(self):
        for data in ({"status": "bogus"}, {"status": ""}, {}):
            with self.subTest(data=data):
                response = self.client.post(self.path, data)

                self.assertRedirects(response, "/goals/", fetch_redirect_response=False)
                self.goal.refresh_from_db()
                self.assertEqual(self.goal.status, Goal.Status.PLANNED)
                # Unread messages pile up across the subtests: compare the set.
                self.assertEqual(
                    set(self.messages(response)), {"Choose a valid status."}
                )

    def test_another_users_goal_is_not_found(self):
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="Bob's"
        )
        path = reverse("goals:move", args=[bobs.pk])

        for extra in ({}, JSON):
            with self.subTest(extra=extra):
                response = self.client.post(path, {"status": "done"}, **extra)

                self.assertEqual(response.status_code, 404)
        bobs.refresh_from_db()
        self.assertEqual(bobs.status, Goal.Status.PLANNED)

    def test_a_missing_goal_is_not_found(self):
        path = reverse("goals:move", args=[self.goal.pk + 100])

        self.assertEqual(self.client.post(path, {"status": "done"}).status_code, 404)

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(self.path).status_code, 405)

    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.client.logout()

        response = self.client.post(self.path, {"status": "done"})

        self.assertRedirects(
            response,
            f"/accounts/login/?next={self.path}",
            fetch_redirect_response=False,
        )
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.PLANNED)


class GoalMoveJsonTests(MoveTestCase):
    """The board's drag and drop posts with Accept: application/json."""

    def test_a_move_answers_with_the_new_status(self):
        response = self.client.post(self.path, {"status": "done"}, **JSON)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content), {"status": "done", "label": "Done"}
        )
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.DONE)
        # The page doesn't reload, so no flash message waits for the next one.
        self.assertEqual(self.messages(response), [])

    def test_an_invalid_status_is_a_bad_request(self):
        response = self.client.post(self.path, {"status": "bogus"}, **JSON)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content), {"error": "Choose a valid status."}
        )
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.PLANNED)
        self.assertEqual(self.messages(response), [])


class GoalMoveCsrfTests(MoveTestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        super().setUp()
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.alice)

    def test_a_post_without_a_token_is_rejected(self):
        self.csrf_client.get("/goals/")

        for extra in ({}, JSON):
            with self.subTest(extra=extra):
                response = self.csrf_client.post(self.path, {"status": "done"}, **extra)

                self.assertEqual(response.status_code, 403)
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.PLANNED)
