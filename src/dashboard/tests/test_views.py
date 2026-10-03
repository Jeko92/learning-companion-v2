from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from core.tests.html import VOID_ELEMENTS, PageParser, collapse
from goals.models import Goal

PASSWORD = "Tr4ck-Learning!"


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


class LabelledSection(HTMLParser):
    """The element labelled by `heading_id` (its aria-labelledby): its
    heading's text and its table rows as lists of cell texts, so a check
    can't pick up the same words elsewhere on the page."""

    def __init__(self, heading_id):
        super().__init__()
        self.heading_id = heading_id
        self.depth = 0
        self.heading_pieces = None
        self.in_heading = False
        self.rows = []
        self.cell = None

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

    def handle_data(self, data):
        if self.in_heading:
            self.heading_pieces.append(data)
        if self.depth and self.cell is not None:
            self.cell.append(data)

    def heading(self):
        return collapse(self.heading_pieces or [])


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
