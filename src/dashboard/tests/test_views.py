from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.shortcuts import resolve_url
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.tests.html import VOID_ELEMENTS, PageParser, collapse
from goals.models import Goal

PASSWORD = "Tr4ck-Learning!"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


class LabelledSection(HTMLParser):
    """The element labelled by `heading_id` (its aria-labelledby): its
    heading's text, its table rows as lists of cell texts and its links as
    (href, text), so a check can't pick up the same words elsewhere on the
    page."""

    def __init__(self, heading_id):
        super().__init__()
        self.heading_id = heading_id
        self.depth = 0
        self.heading_pieces = None
        self.in_heading = False
        self.rows = []
        self.cell = None
        self.link_pieces = []
        self.link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") == self.heading_id:
            self.in_heading, self.heading_pieces = True, []
        if self.depth:
            if tag not in VOID_ELEMENTS:
                self.depth += 1
            if tag == "tr":
                self.rows.append([])
            elif tag in ("th", "td"):
                self.cell = []
            elif tag == "a":
                self.link = []
                self.link_pieces.append((attrs.get("href"), self.link))
        elif attrs.get("aria-labelledby") == self.heading_id:
            self.depth = 1

    def handle_endtag(self, tag):
        if self.in_heading and tag.startswith("h"):
            self.in_heading = False
        if self.depth:
            self.depth -= 1
            if tag in ("th", "td") and self.cell is not None:
                self.rows[-1].append(collapse(self.cell))
                self.cell = None
            elif tag == "a":
                self.link = None

    def handle_data(self, data):
        if self.in_heading:
            self.heading_pieces.append(data)
        if self.depth and self.cell is not None:
            self.cell.append(data)
        if self.depth and self.link is not None:
            self.link.append(data)

    def heading(self):
        return collapse(self.heading_pieces or [])

    def links(self):
        return [(href, collapse(pieces)) for href, pieces in self.link_pieces]


def status_section(client):
    section = LabelledSection("goals-by-status-heading")
    section.feed(client.get("/dashboard/").content.decode())
    return section


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


class DashboardStatusCountsTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.bob = get_user_model().objects.create_user("bob")
        self.client.force_login(self.alice)
        for status in Goal.Status.values:
            Goal.objects.create(owner=self.bob, title="Bob's", status=status)

    def add_goals(self, *statuses):
        for status in statuses:
            Goal.objects.create(owner=self.alice, title="Mine", status=status)

    def test_lists_your_goal_count_per_status_in_order_then_the_total(self):
        self.add_goals(Goal.Status.PLANNED, Goal.Status.DONE, Goal.Status.PLANNED)

        section = status_section(self.client)

        self.assertEqual(section.heading(), "Goals by status")
        self.assertEqual(
            section.rows,
            [
                ["Status", "Goals"],
                ["Planned", "2"],
                ["In progress", "0"],
                ["Done", "1"],
                ["Total", "3"],
            ],
        )

    def test_statuses_without_goals_are_listed_with_zero(self):
        self.add_goals(Goal.Status.IN_PROGRESS)

        section = status_section(self.client)

        self.assertEqual(
            section.rows[1:],
            [["Planned", "0"], ["In progress", "1"], ["Done", "0"], ["Total", "1"]],
        )

    def test_each_row_links_to_the_goal_list_filtered_by_its_status(self):
        self.add_goals(Goal.Status.PLANNED)

        section = status_section(self.client)

        goals = reverse("goals:list")
        self.assertEqual(
            section.links(),
            [
                (f"{goals}?status=planned", "Planned"),
                (f"{goals}?status=in-progress", "In progress"),
                (f"{goals}?status=done", "Done"),
                (goals, "Total"),
            ],
        )


class DashboardEmptyStateTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(self.alice)

    def test_without_goals_every_count_is_zero_and_a_create_link_is_shown(self):
        bob = get_user_model().objects.create_user("bob")
        Goal.objects.create(owner=bob, title="Bob's")

        page = get_page(self.client, "/dashboard/")
        section = status_section(self.client)

        self.assertEqual(
            section.rows[1:],
            [["Planned", "0"], ["In progress", "0"], ["Done", "0"], ["Total", "0"]],
        )
        self.assertIn(
            (reverse("goals:create"), "Create your first goal"), page.links("main")
        )

    def test_with_a_goal_the_create_link_is_not_shown(self):
        Goal.objects.create(owner=self.alice, title="Learn Django")

        page = get_page(self.client, "/dashboard/")

        self.assertNotIn("Create your first goal", page.text("main"))


class DashboardQueryCountTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.few = User.objects.create_user("alice", password=PASSWORD)
        Goal.objects.create(owner=self.few, title="Only one")
        self.many = User.objects.create_user("carol", password=PASSWORD)
        for n in range(30):
            status = Goal.Status.values[n % len(Goal.Status.values)]
            Goal.objects.create(owner=self.many, title=f"Goal {n}", status=status)

    def queries_for(self, user):
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_the_query_count_does_not_grow_with_the_number_of_goals(self):
        self.assertEqual(self.queries_for(self.many), self.queries_for(self.few))

    def test_the_dashboard_takes_a_fixed_number_of_queries(self):
        self.client.force_login(self.many)
        # Login session, user, the grouped status count.
        with self.assertNumQueries(3):
            self.client.get("/dashboard/")
