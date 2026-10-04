"""The goal board: one column per status, goals moved between them by drag and
drop (SortableJS) or by each card's Move menu, both through goals:move."""

import json
from datetime import UTC, datetime
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from core.tests.html import VOID_ELEMENTS, collapse
from goals.models import Goal

PASSWORD = "Tr4ck-Learning!"
JSON = {"HTTP_ACCEPT": "application/json"}


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children = []  # Nodes and text strings, in document order.

    def find_all(self, predicate):
        found = []
        for child in self.children:
            if isinstance(child, Node):
                if predicate(child):
                    found.append(child)
                found += child.find_all(predicate)
        return found

    def with_attr(self, name):
        return self.find_all(lambda n: name in n.attrs)

    def text(self):
        pieces = []
        for child in self.children:
            pieces.append(child.text() if isinstance(child, Node) else child)
        return collapse(pieces)


class Tree(HTMLParser):
    """The page as a tree of Nodes, for checks on what sits inside what."""

    def __init__(self, html):
        super().__init__()
        self.root = self.current = Node("#root", {})
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in VOID_ELEMENTS:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent and node.tag != tag:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def get_tree(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.status_code
    return Tree(response.content.decode()).root


def columns(root):
    """{status: column node} for each board column, in page order."""
    return {c.attrs["data-status"]: c for c in root.with_attr("data-board-column")}


def card_titles(column):
    return [c.find_all(lambda n: n.tag == "a")[0].text() for c in cards(column)]


def cards(column):
    return column.with_attr("data-goal")


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


def add_goal(owner, title, status=Goal.Status.PLANNED, day=1):
    goal = Goal.objects.create(owner=owner, title=title, status=status)
    Goal.objects.filter(pk=goal.pk).update(
        created_at=datetime(2026, 1, day, tzinfo=UTC)
    )
    return goal


class BoardTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.bob = User.objects.create_user("bob")
        self.client.force_login(self.alice)


class BoardColumnTests(BoardTestCase):
    def test_all_shows_one_column_per_status_in_order(self):
        add_goal(self.alice, "Read docs")

        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(list(board), Goal.Status.values)
        for status, column in board.items():
            with self.subTest(status=status):
                (heading,) = column.find_all(lambda n: n.tag == "h2")
                self.assertEqual(heading.text(), Goal.Status(status).label)
                self.assertEqual(column.attrs["aria-labelledby"], heading.attrs["id"])
                self.assertEqual(column.tag, "section")

    def test_each_goal_sits_in_its_status_column_newest_first(self):
        add_goal(self.alice, "p-old", day=1)
        add_goal(self.alice, "p-new", day=3)
        add_goal(self.alice, "i-one", Goal.Status.IN_PROGRESS, day=2)
        add_goal(self.alice, "d-old", Goal.Status.DONE, day=1)
        add_goal(self.alice, "d-new", Goal.Status.DONE, day=5)
        add_goal(self.bob, "bob-planned")

        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(card_titles(board["planned"]), ["p-new", "p-old"])
        self.assertEqual(card_titles(board["in-progress"]), ["i-one"])
        self.assertEqual(card_titles(board["done"]), ["d-new", "d-old"])

    def test_each_column_counts_its_goals(self):
        add_goal(self.alice, "a")
        add_goal(self.alice, "b")
        add_goal(self.alice, "c", Goal.Status.DONE)
        add_goal(self.bob, "bob")

        board = columns(get_tree(self.client, "/goals/"))

        counts = {
            status: column.with_attr("data-board-count")[0].text()
            for status, column in board.items()
        }
        self.assertEqual(counts, {"planned": "2", "in-progress": "0", "done": "1"})

    def test_the_count_badge_has_its_status_colour(self):
        add_goal(self.alice, "a")
        expected = {
            "planned": "badge-neutral",
            "in-progress": "badge-info",
            "done": "badge-success",
        }

        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(list(board), Goal.Status.values)
        for status, column in board.items():
            with self.subTest(status=status):
                (count,) = column.with_attr("data-board-count")
                classes = count.attrs["class"].split()
                self.assertIn("badge", classes)
                self.assertIn(expected[status], classes)

    def test_an_empty_column_says_so_and_a_full_one_hides_the_note(self):
        add_goal(self.alice, "a")

        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(list(board), Goal.Status.values)
        for status, column in board.items():
            with self.subTest(status=status):
                (note,) = column.with_attr("data-board-empty")
                self.assertEqual(note.text(), "No goals.")
                self.assertEqual("hidden" in note.attrs, status == "planned")

    def test_cards_sit_in_each_columns_list(self):
        add_goal(self.alice, "a")

        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(list(board), Goal.Status.values)
        for status, column in board.items():
            with self.subTest(status=status):
                (cards_list,) = column.with_attr("data-board-list")
                self.assertEqual(cards_list.tag, "ul")
                self.assertEqual(cards_list.attrs["data-status"], status)
                self.assertEqual(cards(cards_list), cards(column))
                for card in cards(column):
                    self.assertEqual(card.tag, "li")

    def test_a_filtered_tab_shows_just_its_column(self):
        for status in Goal.Status.values:
            add_goal(self.alice, status, status)

        for status in Goal.Status.values:
            with self.subTest(status=status):
                board = columns(get_tree(self.client, f"/goals/?status={status}"))

                self.assertEqual(list(board), [status])
                self.assertEqual(card_titles(board[status]), [status])

    def test_the_board_is_not_paginated(self):
        for n in range(1, 26):
            add_goal(self.alice, f"g{n:02}", day=n)

        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(
            card_titles(board["planned"]), [f"g{n:02}" for n in range(25, 0, -1)]
        )
        self.assertNotIn("Next", get_tree(self.client, "/goals/").text())

    def test_without_goals_there_is_no_board(self):
        board = columns(get_tree(self.client, "/goals/"))

        self.assertEqual(board, {})

    def test_the_board_takes_a_fixed_number_of_queries(self):
        for n in range(1, 4):
            add_goal(self.alice, f"g{n}", Goal.Status.values[n - 1])
        self.client.get("/goals/")  # warm up: session, user

        with self.assertNumQueries(4):  # session, user, goals, has_goals
            self.client.get("/goals/")
