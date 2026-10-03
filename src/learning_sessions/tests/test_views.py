from datetime import UTC, datetime
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase, override_settings
from django.urls import get_resolver, reverse
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from core.tests.html import PageParser
from goals.models import Goal
from learning_sessions.models import LearningSession

PASSWORD = "Tr4ck-Learning!"
PAYLOAD = "<script>alert(1)</script>"
ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


def session_routes():
    """The session URL patterns, found through the root URLconf, so a route
    that isn't mounted fails an assertion rather than an import."""
    for pattern in get_resolver().url_patterns:
        if getattr(pattern, "namespace", None) == "learning_sessions":
            return pattern.url_patterns
    return []


def valid_data(**changes):
    return {"date": "2026-03-01", "duration_minutes": "45", "notes": "", **changes}


class SessionCreatePageTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/sessions/new/"

    def test_the_create_page_has_a_route_under_the_goal(self):
        self.assertEqual(
            reverse("learning_sessions:create", args=[self.goal.pk]), self.path
        )

    def test_the_form_posts_to_itself_with_the_allowed_fields_only(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning_sessions/session_form.html")
        page = get_page(self.client, self.path)

        ((form, _),) = page.forms("main")
        self.assertEqual(form.get("method"), "post")
        self.assertEqual(form.get("action"), self.path)
        names = {a.get("name") for t, a in page.elements if t in ("input", "select")}
        names |= {a.get("name") for t, a in page.elements if t == "textarea"}
        self.assertTrue({"date", "duration_minutes", "notes", "tags"} <= names)
        self.assertEqual({"goal", "created_at", "updated_at"} & names, set())
        textareas = {a.get("name") for t, a in page.elements if t == "textarea"}
        self.assertEqual(textareas, {"notes"})

    def test_the_date_is_a_date_input(self):
        page = get_page(self.client, self.path)

        (date,) = [a for t, a in page.elements if a.get("name") == "date"]
        self.assertEqual(date.get("type"), "date")

    @override_settings(TIME_ZONE="Pacific/Auckland")
    def test_the_date_defaults_to_today_in_the_project_time_zone(self):
        # 23:30 UTC on the 10th is already the 11th in Auckland.
        now = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
        with patch("django.utils.timezone.now", return_value=now):
            page = get_page(self.client, self.path)

        (date,) = [a for t, a in page.elements if a.get("name") == "date"]
        self.assertEqual(date.get("value"), "2026-03-11")

    def test_the_default_date_is_taken_per_request(self):
        for now, today in (
            (datetime(2026, 3, 10, 12, tzinfo=UTC), "2026-03-10"),
            (datetime(2026, 3, 11, 12, tzinfo=UTC), "2026-03-11"),
        ):
            with (
                self.subTest(today=today),
                patch("django.utils.timezone.now", return_value=now),
            ):
                page = get_page(self.client, self.path)

                (date,) = [a for t, a in page.elements if a.get("name") == "date"]
                self.assertEqual(date.get("value"), today)

    def test_the_page_names_the_goal_and_cancels_back_to_it(self):
        page = get_page(self.client, self.path)

        self.assertIn("Learn Django", page.text("main"))
        self.assertIn((self.goal.get_absolute_url(), "Cancel"), page.links("main"))

    def test_the_goal_title_is_escaped(self):
        self.goal.title = PAYLOAD
        self.goal.save()

        response = self.client.get(self.path)

        self.assertNotContains(response, PAYLOAD)
        self.assertContains(response, ESCAPED)


class SessionCreateAccessTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.path = f"/goals/{self.goal.pk}/sessions/new/"

    def test_anonymous_visitors_are_sent_to_log_in(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                # Only the POST carries data; on a GET it would land in `next`.
                data = valid_data() if method == "post" else None
                response = getattr(self.client, method)(self.path, data)

                self.assertRedirects(
                    response, login_redirect(self.path), fetch_redirect_response=False
                )
                self.assertFalse(LearningSession.objects.exists())

    def test_another_users_goal_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))
        cases = {
            "get": None,
            "valid post": valid_data(),
            "invalid post": valid_data(duration_minutes="0", date="2999-01-01"),
        }
        for case, data in cases.items():
            with self.subTest(case=case):
                method = self.client.get if data is None else self.client.post

                response = method(self.path, data)
                missing = method("/goals/999999/sessions/new/", data)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, missing.content)
                self.assertFalse(LearningSession.objects.exists())


class SessionViewsScopingTests(TestCase):
    def test_every_session_view_scopes_through_the_own_sessions_mixins(self):
        routes = {p.name: p for p in session_routes()}

        # A new route must be added here deliberately, not slip past the check.
        self.assertEqual(set(routes), {"create"})

        from learning_sessions.views import GoalSessionsMixin, OwnSessionsMixin

        User = get_user_model()
        alice = User.objects.create_user("alice")
        alices_goal = Goal.objects.create(owner=alice, title="Alice's goal")
        alices_other_goal = Goal.objects.create(owner=alice, title="Other")
        bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="B"
        )
        mine, other, bobs = (
            LearningSession.objects.create(goal=goal, duration_minutes=30)
            for goal in (alices_goal, alices_other_goal, bobs_goal)
        )
        for name, pattern in routes.items():
            view = pattern.callback.view_class
            with self.subTest(view=name):
                # A model on the view plus a wrong base order would serve
                # every user's sessions silently (as for goals, see CLAUDE.md).
                self.assertIsNone(view.model)
                mro = view.__mro__
                django_qs = [
                    c for c in (SingleObjectMixin, MultipleObjectMixin) if c in mro
                ]
                self.assertTrue(django_qs)
                self.assertLess(
                    mro.index(OwnSessionsMixin), min(mro.index(c) for c in django_qs)
                )
                if "get_queryset" not in view.__dict__:
                    self.assertIn(
                        view.get_queryset,
                        (OwnSessionsMixin.get_queryset, GoalSessionsMixin.get_queryset),
                    )
                request = RequestFactory().get("/")
                request.user = alice
                instance = view()
                if "goal_pk" in pattern.pattern.converters:
                    # Collection routes look the goal up through the owner.
                    self.assertTrue(issubclass(view, GoalSessionsMixin))
                    instance.setup(request, goal_pk=bobs_goal.pk)
                    with self.assertRaises(Http404):
                        instance.get_goal()
                    instance.setup(request, goal_pk=alices_goal.pk)
                    instance.goal = instance.get_goal()
                    self.assertEqual(instance.goal, alices_goal)
                    self.assertEqual(set(instance.get_queryset()), {mine})
                else:
                    instance.setup(request, pk=mine.pk)
                    self.assertEqual(set(instance.get_queryset()), {mine, other})
                self.assertNotIn(bobs, set(instance.get_queryset()))
