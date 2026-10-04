"""Every page type of the site, for tests that check all pages at once.

Not a test module (no test_ prefix), so the runner doesn't collect it. A new
page type is added to PAGES deliberately, so the site-wide checks cover it.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from core.tests.html import PageParser
from goals.models import Goal
from learning_sessions.models import LearningSession
from profiles.models import Profile
from resources.models import Resource
from tags.models import Tag

PASSWORD = "Tr4ck-Learning!"


@dataclass(frozen=True)
class Page:
    name: str
    path: str
    logged_in: bool
    # A page that isn't a plain GET: render(client) returns its response.
    render: Callable | None = None
    status: int = 200


def locked_out(client):
    """The lockout page that django-axes renders: locked out at the first
    failed log-in here, as each failure costs a password hash and every page
    walk renders it. accounts/tests/test_lockout.py covers the real limit."""
    with override_settings(AXES_FAILURE_LIMIT=1):
        return client.post(
            reverse("accounts:login"),
            {"username": "alice", "password": "not-the-password"},
        )


def build_pages():
    """Creates alice with one goal, one tagged session and one resource, and
    returns (alice, [Page]) covering every page type."""
    alice = get_user_model().objects.create_user("alice", password=PASSWORD)
    profile, _ = Profile.objects.get_or_create(user=alice)
    goal = Goal.objects.create(owner=alice, title="Learn Django")
    session = LearningSession.objects.create(goal=goal, duration_minutes=45)
    session.tags.set([Tag.objects.get_or_create_by_name("Django")[0]])
    resource = Resource.objects.create(
        goal=goal, url="https://docs.djangoproject.com/", title="Django docs"
    )
    public = [
        ("home", reverse("home")),
        ("log in", reverse("accounts:login")),
        ("sign up", reverse("accounts:signup")),
    ]
    private = [
        ("dashboard", reverse("dashboard:index")),
        ("profile", reverse("profiles:detail", args=[profile.pk])),
        ("profile edit", reverse("profiles:edit", args=[profile.pk])),
        ("goal list", reverse("goals:list")),
        ("goal create", reverse("goals:create")),
        ("goal detail", reverse("goals:detail", args=[goal.pk])),
        ("goal edit", reverse("goals:edit", args=[goal.pk])),
        ("goal delete", reverse("goals:delete", args=[goal.pk])),
        ("session list", reverse("learning_sessions:list", args=[goal.pk])),
        ("session create", reverse("learning_sessions:create", args=[goal.pk])),
        ("session edit", reverse("learning_sessions:edit", args=[session.pk])),
        ("session delete", reverse("learning_sessions:delete", args=[session.pk])),
        ("resource create", reverse("resources:create", args=[goal.pk])),
        ("resource delete", reverse("resources:delete", args=[resource.pk])),
    ]
    pages = [Page(name, path, False) for name, path in public]
    pages.append(
        Page(
            "locked out",
            reverse("accounts:login"),
            False,
            render=locked_out,
            status=429,
        )
    )
    pages += [Page(name, path, True) for name, path in private]
    return alice, pages


class AllPagesMixin:
    """For a TestCase: builds the pages in setUp; walk() yields each page with
    its response, rendered as the right visitor (logged in or not)."""

    def setUp(self):
        super().setUp()
        self.alice, self.pages = build_pages()

    def get(self, page):
        if page.logged_in:
            self.client.force_login(self.alice)
        else:
            self.client.logout()
        if page.render:
            response = page.render(self.client)
        else:
            response = self.client.get(page.path)
        self.assertEqual(response.status_code, page.status, page.name)
        return response

    def walk(self):
        """[(page, PageParser)] for every page; check each in a subTest."""
        parsed = []
        for page in self.pages:
            parser = PageParser()
            parser.feed(self.get(page).content.decode())
            parsed.append((page, parser))
        return parsed
