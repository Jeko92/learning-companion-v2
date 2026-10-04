import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.shortcuts import resolve_url
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from core.tests.html import VOID_ELEMENTS, PageParser, collapse
from goals import urls as goal_urls
from goals.models import Goal
from goals.views import OwnGoalsMixin
from learning_sessions.models import LearningSession
from resources.models import Resource
from tags.models import Tag

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

    def test_goal_values_are_shown_escaped(self):
        payload = "<script>alert(1)</script>"
        Goal.objects.create(owner=self.alice, title=payload, description=payload)

        response = self.client.get("/goals/")

        self.assertNotContains(response, payload)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_each_title_links_to_its_goal(self):
        goals = [Goal.objects.create(owner=self.alice, title=t) for t in ("A", "B")]

        links = get_page(self.client, "/goals/").links("main")

        for goal in goals:
            with self.subTest(goal=goal.title):
                self.assertIn((goal.get_absolute_url(), goal.title), links)


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

    def test_a_valid_create_saves_your_goal_and_opens_it(self):
        # goal-edit-delete: a new goal now opens its detail page (#8 AC6
        # returned to the list).
        response = self.client.post("/goals/new/", self.data)

        goal = Goal.objects.get()
        self.assertRedirects(
            response, goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.assertEqual(
            (goal.owner, goal.title, goal.status),
            (self.alice, "Learn Django", Goal.Status.IN_PROGRESS),
        )
        followed = self.client.get(goal.get_absolute_url())
        self.assertContains(followed, "Goal created.")
        self.assertContains(followed, "Learn Django")

    def test_a_posted_owner_is_ignored(self):
        bob = get_user_model().objects.create_user("bob")

        self.client.post("/goals/new/", {**self.data, "owner": bob.pk})

        self.assertEqual(Goal.objects.get().owner, self.alice)
        self.assertFalse(bob.goals.exists())

    def test_anonymous_visitors_are_sent_to_log_in_and_nothing_is_created(self):
        self.client.logout()
        for method in ("get", "post"):
            with self.subTest(method=method):
                # Only the POST carries data; on a GET it would land in `next`.
                data = self.data if method == "post" else None
                response = getattr(self.client, method)("/goals/new/", data)

                self.assertRedirects(
                    response,
                    login_redirect("/goals/new/"),
                    fetch_redirect_response=False,
                )
                self.assertFalse(Goal.objects.exists())

    def test_invalid_input_rerenders_the_form_and_creates_nothing(self):
        cases = (
            ("blank title", {"title": ""}, "title", "This field is required."),
            ("whitespace title", {"title": "   "}, "title", "This field is required."),
            (
                "long title",
                {"title": "t" * 201},
                "title",
                "Ensure this value has at most 200 characters (it has 201).",
            ),
            (
                "long description",
                {"description": "d" * 2001},
                "description",
                "Ensure this value has at most 2000 characters (it has 2001).",
            ),
            (
                "unknown status",
                {"status": "bogus"},
                "status",
                "Select a valid choice. bogus is not one of the available choices.",
            ),
        )
        for case, changes, field, message in cases:
            with self.subTest(case=case):
                response = self.client.post("/goals/new/", {**self.data, **changes})

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "goals/goal_form.html")
                self.assertFormError(response.context["form"], field, message)
                page = PageParser()
                page.feed(response.content.decode())
                self.assertIn(message, page.text("main"))
                self.assertFalse(Goal.objects.exists())


class GoalCreateCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        # GET first so the CSRF cookie is set: a 403 must come from the token.
        page = PageParser()
        page.feed(self.csrf_client.get("/goals/new/").content.decode())
        ((_, inputs),) = page.forms("main")
        self.tokens = [
            a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"
        ]
        self.data = {"title": "Learn Django", "description": "", "status": "planned"}

    def test_a_create_without_a_token_is_rejected(self):
        response = self.csrf_client.post("/goals/new/", self.data)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Goal.objects.exists())

    def test_a_create_with_the_forms_token_succeeds(self):
        self.assertEqual(len(self.tokens), 1, "the goal form has no CSRF token")

        response = self.csrf_client.post(
            "/goals/new/", {**self.data, "csrfmiddlewaretoken": self.tokens[0]}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Goal.objects.exists())


class GoalListPaginationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        alice = User.objects.create_user("alice", password=PASSWORD)
        bob = User.objects.create_user("bob")
        for n in range(1, 22):  # g01 (oldest) .. g21 (newest)
            goal = Goal.objects.create(owner=alice, title=f"g{n:02}")
            Goal.objects.filter(pk=goal.pk).update(
                created_at=datetime(2026, 1, n, tzinfo=UTC)
            )
        for n in range(30):
            Goal.objects.create(owner=bob, title=f"bob-{n}")
        self.client.force_login(alice)

    def titles(self, page):
        # Only the seeded titles ("g01".."g21", "bob-N"), not words like "goals".
        return re.findall(r"\b(?:g\d\d|bob-\d+)\b", page.text("main"))

    def test_twenty_goals_per_page_counting_only_yours(self):
        first = get_page(self.client, "/goals/")
        second = get_page(self.client, "/goals/?page=2")

        self.assertEqual(self.titles(first), [f"g{n:02}" for n in range(21, 1, -1)])
        self.assertEqual(self.titles(second), ["g01"])
        self.assertIn(("?page=2", "Next"), first.links("main"))
        self.assertNotIn("Previous", first.text("main"))
        self.assertIn(("?page=1", "Previous"), second.links("main"))
        self.assertNotIn("Next", second.text("main"))

    def test_an_out_of_range_page_is_not_found(self):
        self.assertEqual(self.client.get("/goals/?page=99").status_code, 404)


class GoalDetailTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(
            owner=self.alice,
            title="Learn Django",
            description="Parts 1-3\nParts 4-7",
            status=Goal.Status.IN_PROGRESS,
        )
        self.path = f"/goals/{self.goal.pk}/"
        self.client.force_login(self.alice)

    def test_the_detail_page_is_served(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "goals/goal_detail.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(reverse("goals:detail", args=[self.goal.pk]), self.path)

    def test_shows_the_goal(self):
        page = get_page(self.client, self.path)
        main = page.text("main")

        for text in ("Learn Django", "In progress", "Parts 1-3", "Parts 4-7"):
            with self.subTest(text=text):
                self.assertIn(text, main)
        self.assertIn("br", [tag for tag, _ in page.elements])
        self.assertIn("Created", main)
        self.assertIn("Updated", main)
        self.assertIn(("/goals/", "Back to goals"), page.links("main"))

    def test_shows_a_placeholder_without_a_description(self):
        self.goal.description = ""
        self.goal.save()

        self.assertIn("No description.", get_page(self.client, self.path).text("main"))

    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.client.logout()

        response = self.client.get(self.path)

        self.assertRedirects(
            response, login_redirect(self.path), fetch_redirect_response=False
        )

    def test_another_users_goal_is_not_found_like_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))

        response = self.client.get(self.path)
        missing = self.client.get("/goals/999999/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, missing.content)


class GoalEditTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(
            owner=self.alice,
            title="Learn Django",
            description="Parts 1-7",
            status=Goal.Status.IN_PROGRESS,
        )
        self.path = f"/goals/{self.goal.pk}/edit/"
        self.client.force_login(self.alice)

    def test_the_edit_page_renders_your_goal_in_a_form(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "goals/goal_form.html")
        self.assertEqual(reverse("goals:edit", args=[self.goal.pk]), self.path)
        page = PageParser()
        page.feed(response.content.decode())
        ((attrs, inputs),) = page.forms("main")
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), self.path)
        values = {a.get("name"): a.get("value") for a in inputs}
        self.assertIn("csrfmiddlewaretoken", values)
        self.assertEqual(values["title"], "Learn Django")
        self.assertIn("Parts 1-7", page.text("main"))  # the textarea's content
        selected = [
            a.get("value")
            for t, a in page.elements
            if t == "option" and "selected" in a
        ]
        self.assertEqual(selected, ["in-progress"])
        self.assertNotIn("owner", {a.get("name") for _, a in page.elements})
        self.assertIn("Edit goal", page.text("main"))
        self.assertNotIn("New goal", page.text("main"))
        self.assertIn((self.goal.get_absolute_url(), "Cancel"), page.links("main"))

    def test_editing_keeps_the_summary_and_the_form_cannot_set_it(self):
        generated = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
        Goal.objects.filter(pk=self.goal.pk).update(
            summary="Earlier summary", summary_generated_at=generated
        )

        self.client.post(
            self.path,
            {
                "title": "Learn Django well",
                "description": "",
                "status": "done",
                "summary": "Posted summary",
                "summary_generated_at": "2000-01-01 00:00",
            },
        )

        self.goal.refresh_from_db()
        self.assertEqual(self.goal.title, "Learn Django well")
        self.assertEqual(self.goal.summary, "Earlier summary")
        self.assertEqual(self.goal.summary_generated_at, generated)

    def test_editing_keeps_the_next_steps_and_the_form_cannot_set_them(self):
        generated = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
        Goal.objects.filter(pk=self.goal.pk).update(
            next_steps=["Earlier step", "Another step"],
            next_steps_generated_at=generated,
        )

        self.client.post(
            self.path,
            {
                "title": "Learn Django well",
                "description": "",
                "status": "done",
                "next_steps": '["Posted step"]',
                "next_steps_generated_at": "2000-01-01 00:00",
            },
        )

        self.goal.refresh_from_db()
        self.assertEqual(self.goal.title, "Learn Django well")
        self.assertEqual(self.goal.next_steps, ["Earlier step", "Another step"])
        self.assertEqual(self.goal.next_steps_generated_at, generated)

    def test_the_detail_page_links_to_the_edit_page(self):
        links = get_page(self.client, self.goal.get_absolute_url()).links("main")

        self.assertIn((self.path, "Edit goal"), links)

    def test_a_valid_edit_saves_and_returns_to_the_goal(self):
        bob = get_user_model().objects.create_user("bob")
        data = {
            "title": "  Learn Django well ",
            "description": "All parts",
            "status": "done",
            "owner": bob.pk,
        }

        response = self.client.post(self.path, data)

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.goal.refresh_from_db()
        self.assertEqual(
            (self.goal.title, self.goal.description, self.goal.status, self.goal.owner),
            ("Learn Django well", "All parts", Goal.Status.DONE, self.alice),
        )
        self.assertContains(
            self.client.get(self.goal.get_absolute_url()), "Goal updated."
        )

    def test_an_invalid_edit_rerenders_the_form_and_changes_nothing(self):
        valid = {"title": "Changed", "description": "Changed", "status": "done"}
        cases = (
            ("blank title", {"title": ""}, "title", "This field is required."),
            ("whitespace title", {"title": "   "}, "title", "This field is required."),
            (
                "long title",
                {"title": "t" * 201},
                "title",
                "Ensure this value has at most 200 characters (it has 201).",
            ),
            (
                "long description",
                {"description": "d" * 2001},
                "description",
                "Ensure this value has at most 2000 characters (it has 2001).",
            ),
            (
                "unknown status",
                {"status": "bogus"},
                "status",
                "Select a valid choice. bogus is not one of the available choices.",
            ),
        )
        for case, changes, field, message in cases:
            with self.subTest(case=case):
                response = self.client.post(self.path, {**valid, **changes})

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "goals/goal_form.html")
                self.assertFormError(response.context["form"], field, message)
                page = PageParser()
                page.feed(response.content.decode())
                self.assertIn(message, page.text("main"))
                self.goal.refresh_from_db()
                self.assertEqual(
                    (self.goal.title, self.goal.description, self.goal.status),
                    ("Learn Django", "Parts 1-7", Goal.Status.IN_PROGRESS),
                )


class GoalDeleteTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.path = f"/goals/{self.goal.pk}/delete/"
        self.client.force_login(self.alice)

    def test_delete_asks_for_confirmation_and_a_get_deletes_nothing(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "goals/goal_confirm_delete.html")
        self.assertEqual(reverse("goals:delete", args=[self.goal.pk]), self.path)
        page = PageParser()
        page.feed(response.content.decode())
        self.assertIn("Delete “Learn Django”?", page.text("main"))
        ((attrs, inputs),) = page.forms("main")
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), self.path)
        self.assertIn("csrfmiddlewaretoken", {a.get("name") for a in inputs})
        self.assertIn("button", [t for t, _ in page.elements])
        self.assertIn("Delete", page.text("main"))
        self.assertIn((self.goal.get_absolute_url(), "Cancel"), page.links("main"))
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())

    def test_the_detail_page_links_to_delete(self):
        links = get_page(self.client, self.goal.get_absolute_url()).links("main")

        self.assertIn((self.path, "Delete goal"), links)

    def test_confirming_deletes_the_goal(self):
        response = self.client.post(self.path)

        self.assertRedirects(response, "/goals/", fetch_redirect_response=False)
        self.assertFalse(Goal.objects.filter(pk=self.goal.pk).exists())
        followed = self.client.get("/goals/")
        self.assertContains(followed, "Goal deleted.")
        self.assertNotContains(followed, "Learn Django")


class GoalEditDeleteAccessTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.cases = [
            (page, method) for page in ("edit", "delete") for method in ("get", "post")
        ]

    def request(self, page, method, pk):
        path = reverse(f"goals:{page}", args=[pk])
        # Only the POSTs carry data; on a GET it would land in `next`.
        data = {"title": "hacked", "status": "done"} if method == "post" else None
        return path, getattr(self.client, method)(path, data)

    def assert_untouched(self):
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.title, "Learn Django")

    def test_anonymous_visitors_are_sent_to_log_in(self):
        for page, method in self.cases:
            with self.subTest(page=page, method=method):
                path, response = self.request(page, method, self.goal.pk)

                self.assertRedirects(
                    response, login_redirect(path), fetch_redirect_response=False
                )
                self.assert_untouched()

    def test_another_user_gets_the_same_404_as_for_a_missing_goal(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))
        for page, method in self.cases:
            with self.subTest(page=page, method=method):
                _, response = self.request(page, method, self.goal.pk)
                _, missing = self.request(page, method, 999999)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, missing.content)
                self.assert_untouched()


class GoalEditDeleteCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        self.data = {"edit": {"title": "Changed", "status": "done"}, "delete": {}}

    def token_for(self, path):
        # GET first: sets the CSRF cookie and yields the form's token.
        page = PageParser()
        page.feed(self.csrf_client.get(path).content.decode())
        ((_, inputs),) = page.forms("main")
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        for page in ("edit", "delete"):
            with self.subTest(page=page):
                path = reverse(f"goals:{page}", args=[self.goal.pk])
                self.token_for(path)

                response = self.csrf_client.post(path, self.data[page])

                self.assertEqual(response.status_code, 403)
                self.goal.refresh_from_db()
                self.assertEqual(self.goal.title, "Learn Django")

    def test_a_post_with_the_forms_token_succeeds(self):
        for page in ("edit", "delete"):
            with self.subTest(page=page):
                path = reverse(f"goals:{page}", args=[self.goal.pk])
                tokens = self.token_for(path)
                self.assertEqual(len(tokens), 1, f"the {page} form has no CSRF token")

                response = self.csrf_client.post(
                    path, {**self.data[page], "csrfmiddlewaretoken": tokens[0]}
                )

                self.assertEqual(response.status_code, 302)


class GoalPagesEscapingTests(TestCase):
    PAYLOAD = "<script>alert(1)</script>"

    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(
            owner=alice, title=self.PAYLOAD, description=self.PAYLOAD
        )
        self.client.force_login(alice)

    def test_goal_values_are_escaped_on_every_goal_page(self):
        for page in ("detail", "edit", "delete"):
            with self.subTest(page=page):
                response = self.client.get(
                    reverse(f"goals:{page}", args=[self.goal.pk])
                )

                self.assertNotContains(response, self.PAYLOAD)
                self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")


class OwnGoalsMixinOrderTests(TestCase):
    def test_a_wrongly_ordered_mixin_fails_loudly(self):
        # Listed after the generic view, the mixin's scoped get_queryset() is
        # shadowed; with no model to fall back on, Django must refuse to serve.
        class WronglyOrdered(DetailView, OwnGoalsMixin):
            pass

        alice = get_user_model().objects.create_user("alice")
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        request = RequestFactory().get("/")
        request.user = alice

        with self.assertRaises(ImproperlyConfigured):
            WronglyOrdered.as_view()(request, pk=goal.pk)


class GoalStatusFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        bob = User.objects.create_user("bob")
        self.titles = {}
        for status in Goal.Status.values:
            Goal.objects.create(
                owner=self.alice, title=f"alice-{status}", status=status
            )
            Goal.objects.create(owner=bob, title=f"bob-{status}", status=status)
            self.titles[status] = f"alice-{status}"
        self.client.force_login(self.alice)

    def listed(self, path):
        main = get_page(self.client, path).text("main")
        return {t for t in re.findall(r"\b(?:alice|bob)-[a-z-]+\b", main)}

    def test_a_status_filters_the_list(self):
        for status in Goal.Status.values:
            with self.subTest(status=status):
                self.assertEqual(
                    self.listed(f"/goals/?status={status}"), {self.titles[status]}
                )

    def test_a_missing_empty_or_invalid_status_shows_all(self):
        for path in ("/goals/", "/goals/?status=", "/goals/?status=bogus"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
                self.assertEqual(self.listed(path), set(self.titles.values()))

    def test_the_filter_never_shows_other_users_goals(self):
        for status in Goal.Status.values:
            with self.subTest(status=status):
                listed = self.listed(f"/goals/?status={status}")

                self.assertFalse({t for t in listed if t.startswith("bob-")})

    def active_filter(self, path):
        """The text of the one aria-current="page" span (the active filter)."""
        html = self.client.get(path).content.decode()
        return re.findall(r'<span[^>]*aria-current="page"[^>]*>([^<]*)</span>', html)

    def test_filter_links_mark_the_active_filter(self):
        filters = [
            ("/goals/?status=planned", "Planned"),
            ("/goals/?status=in-progress", "In progress"),
            ("/goals/?status=done", "Done"),
        ]
        page = get_page(self.client, "/goals/")
        links = page.links("main")
        for link in filters:
            with self.subTest(link=link):
                self.assertIn(link, links)
        self.assertNotIn(("/goals/", "All"), links)
        self.assertEqual(self.active_filter("/goals/"), ["All"])

        done = get_page(self.client, "/goals/?status=done")
        self.assertIn(("/goals/", "All"), done.links("main"))
        self.assertNotIn(("/goals/?status=done", "Done"), done.links("main"))
        self.assertEqual(self.active_filter("/goals/?status=done"), ["Done"])

        self.assertEqual(self.active_filter("/goals/?status=bogus"), ["All"])


class GoalFilteredPaginationTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        for n in range(1, 22):  # d01 (oldest) .. d21 (newest), all done
            goal = Goal.objects.create(
                owner=alice, title=f"d{n:02}", status=Goal.Status.DONE
            )
            Goal.objects.filter(pk=goal.pk).update(
                created_at=datetime(2026, 1, n, tzinfo=UTC)
            )
        for n in range(5):
            Goal.objects.create(owner=alice, title=f"p{n}", status=Goal.Status.PLANNED)
        self.client.force_login(alice)

    def titles(self, page):
        return re.findall(r"\b[dp]\d\d?\b", page.text("main"))

    def test_pagination_keeps_the_filter(self):
        first = get_page(self.client, "/goals/?status=done")
        second = get_page(self.client, "/goals/?status=done&page=2")

        self.assertEqual(self.titles(first), [f"d{n:02}" for n in range(21, 1, -1)])
        self.assertIn(("?status=done&page=2", "Next"), first.links("main"))
        self.assertEqual(self.titles(second), ["d01"])
        self.assertIn(("?status=done&page=1", "Previous"), second.links("main"))

    def test_filter_links_start_at_page_one(self):
        second = get_page(self.client, "/goals/?status=done&page=2")

        filter_links = [h for h, _ in second.links("main") if h.startswith("/goals/")]
        self.assertTrue(filter_links)
        self.assertFalse([h for h in filter_links if "page=" in h])

    def test_query_parameters_are_never_reflected_raw(self):
        payload = "<script>alert(1)</script>"
        # 21 done goals, so the pagination links (which carry the query) render.
        response = self.client.get("/goals/", {"status": "done", "x": payload})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Next")
        self.assertNotContains(response, payload)


class GoalFilterEmptyStateTests(TestCase):
    def test_an_empty_filter_says_so(self):
        alice = get_user_model().objects.create_user("alice")
        Goal.objects.create(owner=alice, title="Only planned")
        self.client.force_login(alice)

        main = get_page(self.client, "/goals/?status=done").text("main")

        self.assertIn("No goals with this status.", main)
        self.assertNotIn("No goals yet.", main)

    def test_no_goals_at_all_says_no_goals_yet(self):
        self.client.force_login(get_user_model().objects.create_user("carol"))
        for path in ("/goals/", "/goals/?status=done"):
            with self.subTest(path=path):
                main = get_page(self.client, path).text("main")

                self.assertIn("No goals yet.", main)
                self.assertNotIn("No goals with this status.", main)


class GoalViewsScopingTests(TestCase):
    def test_every_goal_lookup_view_scopes_through_own_goals_mixin(self):
        User = get_user_model()
        alice = User.objects.create_user("alice")
        alices_goal = Goal.objects.create(owner=alice, title="Alice's goal")
        bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="x"
        )
        # Create looks no goal up (it sets the owner in form_valid).
        views = {
            p.name: p.callback.view_class
            for p in goal_urls.urlpatterns
            if p.name != "create"
        }

        # A new route must be added here deliberately, not slip past the check.
        self.assertEqual(
            set(views),
            {"list", "detail", "edit", "delete", "summary", "next_steps", "move"},
        )
        for name, view in views.items():
            with self.subTest(view=name):
                # A model on the view plus a wrong base order would serve
                # every user's goals silently (see CLAUDE.md, Goals).
                self.assertIsNone(view.model)
                # OwnGoalsMixin must precede Django's own get_queryset, so it
                # (or a super() chain through it, as the list's filter uses)
                # is what scopes the lookup.
                mro = view.__mro__
                django_qs = [
                    c for c in (SingleObjectMixin, MultipleObjectMixin) if c in mro
                ]
                self.assertTrue(django_qs)
                self.assertLess(
                    mro.index(OwnGoalsMixin), min(mro.index(c) for c in django_qs)
                )
                # Without an override, the lookup is the mixin's own.
                if "get_queryset" not in view.__dict__:
                    self.assertIs(view.get_queryset, OwnGoalsMixin.get_queryset)
                # With one (the list's filter) or without: only alice's goals.
                request = RequestFactory().get("/")
                request.user = alice
                instance = view()
                instance.setup(
                    request, **({} if name == "list" else {"pk": alices_goal.pk})
                )
                goals = set(instance.get_queryset())
                self.assertIn(alices_goal, goals)
                self.assertNotIn(bobs_goal, goals)


def add_session(goal, tags=(), **fields):
    fields = {"date": "2026-03-01", "duration_minutes": 15, **fields}
    session = LearningSession.objects.create(goal=goal, **fields)
    session.tags.set(Tag.objects.get_or_create_by_name(n)[0] for n in tags)
    return session


class GoalDetailSessionsTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = self.goal.get_absolute_url()

    def numbers(self, page):
        return [int(n) for n in re.findall(r"#(\d+)#", page.text("main"))]

    def test_the_five_most_recent_sessions_of_this_goal_are_shown(self):
        for n in range(1, 7):
            add_session(self.goal, date=f"2026-03-0{n}", notes=f"#{n}#")
        other = Goal.objects.create(owner=self.alice, title="Other")
        add_session(other, date="2026-03-09", notes="#99#")

        page = get_page(self.client, self.path)

        self.assertEqual(self.numbers(page), [6, 5, 4, 3, 2])

    def test_each_session_shows_its_details_and_links(self):
        session = add_session(
            self.goal,
            tags=("zebra", "Django", "apple"),
            duration_minutes=90,
            notes="Hi",
        )

        page = get_page(self.client, self.path)

        text = page.text("main")
        for shown in ("1 Mar 2026", "1 h 30 min", "apple Django zebra", "Hi"):
            self.assertIn(shown, text)
        links = page.links("main")
        self.assertIn((f"/sessions/{session.pk}/edit/", "Edit"), links)
        self.assertIn((f"/sessions/{session.pk}/delete/", "Delete"), links)

    def test_the_total_counts_every_session_not_just_those_shown(self):
        for n in range(1, 7):
            add_session(self.goal, date=f"2026-03-0{n}")
        add_session(Goal.objects.create(owner=self.alice, title="Other"))

        text = get_page(self.client, self.path).text("main")

        self.assertIn("Total: 1 h 30 min", text)

    def test_the_section_links_to_add_and_to_all_sessions(self):
        links = get_page(self.client, self.path).links("main")

        self.assertIn((f"/goals/{self.goal.pk}/sessions/new/", "Add session"), links)
        self.assertIn((f"/goals/{self.goal.pk}/sessions/", "All sessions"), links)

    def test_a_goal_without_sessions_says_so_with_a_zero_total(self):
        text = get_page(self.client, self.path).text("main")

        self.assertIn("No sessions yet.", text)
        self.assertIn("Total: 0 min", text)

    def test_session_text_is_escaped(self):
        payload = "<script>alert(1)</script>"
        add_session(self.goal, tags=(payload,), notes=payload)

        response = self.client.get(self.path)

        self.assertNotContains(response, payload)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")


def add_resource(goal, **fields):
    n = Resource.objects.count() + 1
    fields = {"url": f"https://example.com/{n}", "title": f"Resource {n}", **fields}
    return Resource.objects.create(goal=goal, **fields)


class LabelledSectionText(HTMLParser):
    """The text inside the element labelled by `heading_id` (its
    aria-labelledby), so a check can't pick up the same words elsewhere on
    the page."""

    def __init__(self, heading_id):
        super().__init__()
        self.heading_id = heading_id
        self.depth = 0
        self.pieces = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            if tag not in VOID_ELEMENTS:
                self.depth += 1
        elif dict(attrs).get("aria-labelledby") == self.heading_id:
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.pieces.append(data)

    def text(self):
        return collapse(self.pieces)


class GoalDetailResourcesTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = self.goal.get_absolute_url()

    def resources_text(self):
        section = LabelledSectionText("resources-heading")
        section.feed(self.client.get(self.path).content.decode())
        return section.text()

    def test_the_section_is_found_by_its_heading_not_by_a_word(self):
        # "Resources" elsewhere on the page must not shift what is checked.
        self.goal.title = "Resources for Django"
        self.goal.save()
        add_session(self.goal, notes="Resources: none yet")
        add_resource(self.goal, title="A tutorial")

        text = self.resources_text()

        self.assertTrue(text.startswith("Resources Articles A tutorial Delete"), text)
        self.assertNotIn("for Django", text)
        self.assertNotIn("none yet", text)

    def test_resources_are_grouped_by_type_in_a_fixed_order(self):
        add_resource(self.goal, title="The docs", type=Resource.Type.DOC)
        add_resource(self.goal, title="Older talk", type=Resource.Type.VIDEO)
        add_resource(self.goal, title="A tutorial", type=Resource.Type.ARTICLE)
        add_resource(self.goal, title="Newer talk", type=Resource.Type.VIDEO)

        text = self.resources_text()

        self.assertIn(
            "Articles A tutorial Delete Videos Newer talk Delete Older talk Delete "
            "Docs The docs Delete",
            text,
        )
        self.assertNotIn("Repos", text)

    def test_each_resource_links_to_its_url_in_a_new_tab_and_can_be_deleted(self):
        resource = add_resource(
            self.goal, url="https://docs.djangoproject.com/", title="Django docs"
        )

        page = get_page(self.client, self.path)

        links = page.links("main")
        self.assertIn(("https://docs.djangoproject.com/", "Django docs"), links)
        self.assertIn((f"/resources/{resource.pk}/delete/", "Delete"), links)
        (anchor,) = [
            a
            for t, a in page.elements
            if t == "a" and a.get("href") == "https://docs.djangoproject.com/"
        ]
        self.assertEqual(anchor.get("target"), "_blank")
        self.assertEqual(anchor.get("rel"), "noopener noreferrer")

    def test_resources_of_other_goals_never_appear(self):
        other = Goal.objects.create(owner=self.alice, title="Other")
        add_resource(other, title="Elsewhere")
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        add_resource(bobs, title="Bobs")

        text = get_page(self.client, self.path).text("main")

        self.assertNotIn("Elsewhere", text)
        self.assertNotIn("Bobs", text)

    def test_a_goal_without_resources_says_so_and_offers_the_form(self):
        page = get_page(self.client, self.path)

        self.assertIn("No resources yet.", self.resources_text())
        self.assertTrue(page.forms("main"))

    def test_the_attach_form_posts_to_the_create_route(self):
        add_resource(self.goal)

        page = get_page(self.client, self.path)

        # Found by its action: the goal page has other forms too.
        action = f"/goals/{self.goal.pk}/resources/new/"
        ((form, inputs),) = [
            (f, i) for f, i in page.forms("main") if f.get("action") == action
        ]
        self.assertEqual(form.get("method"), "post")
        names = {a.get("name") for a in inputs}
        self.assertEqual(names, {"csrfmiddlewaretoken", "url", "title"})
        (select,) = [a for t, a in page.elements if t == "select"]
        self.assertEqual(select.get("name"), "type")
        options = [a for t, a in page.elements if t == "option"]
        self.assertEqual(
            [o.get("value") for o in options], ["article", "video", "repo", "doc"]
        )
        self.assertEqual(
            [o.get("value") for o in options if "selected" in o], ["article"]
        )

    def test_resource_title_and_url_are_escaped(self):
        payload = "<script>alert(1)</script>"
        add_resource(self.goal, title=payload, url=f"https://example.com/?q={payload}")

        response = self.client.get(self.path)

        self.assertNotContains(response, payload)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;", 2)


class GoalDetailQueryCountTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(alice)
        self.small = Goal.objects.create(owner=alice, title="Small")
        add_session(self.small, tags=("a",))
        add_resource(self.small)
        self.large = Goal.objects.create(owner=alice, title="Large")
        for _ in range(6):
            add_session(self.large, tags=("a", "b", "c"))
        for value in Resource.Type.values * 2:
            add_resource(self.large, type=value)
        # The summary and next steps come with the goal row: no extra query.
        Goal.objects.filter(pk=self.large.pk).update(
            summary="A summary",
            summary_generated_at=datetime(2026, 10, 1, tzinfo=UTC),
            next_steps=["Build a form", "Read the ORM docs"],
            next_steps_generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        )

    def queries_for(self, goal):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(goal.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_the_query_count_does_not_grow_with_sessions_tags_or_resources(self):
        self.assertEqual(self.queries_for(self.large), self.queries_for(self.small))

    def test_the_goal_page_takes_a_fixed_number_of_queries(self):
        # Login session, user, goal, total, recent sessions, their tags,
        # resources.
        with self.assertNumQueries(7):
            self.client.get(self.large.get_absolute_url())


class GoalDeleteSessionWarningTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        # Sessions elsewhere must not be counted.
        add_session(Goal.objects.create(owner=self.alice, title="Other"))
        add_session(
            Goal.objects.create(owner=User.objects.create_user("bob"), title="B")
        )
        self.client.force_login(self.alice)
        self.path = reverse("goals:delete", args=[self.goal.pk])

    def test_the_confirmation_says_how_many_sessions_go_with_the_goal(self):
        for count, warning in (
            (1, "Its 1 session will be deleted too."),
            (3, "Its 3 sessions will be deleted too."),
        ):
            with self.subTest(count=count):
                while self.goal.sessions.count() < count:
                    add_session(self.goal)

                text = get_page(self.client, self.path).text("main")

                self.assertIn(warning, text)

    def test_a_goal_without_sessions_has_no_warning(self):
        text = get_page(self.client, self.path).text("main")

        self.assertNotIn("will be deleted too", text)


class GoalDeleteResourceWarningTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        # Resources elsewhere must not be counted.
        add_resource(Goal.objects.create(owner=self.alice, title="Other"))
        add_resource(
            Goal.objects.create(owner=User.objects.create_user("bob"), title="B")
        )
        self.client.force_login(self.alice)
        self.path = reverse("goals:delete", args=[self.goal.pk])

    def test_the_confirmation_says_how_many_resources_go_with_the_goal(self):
        for count, warning in (
            (1, "Its 1 resource will be deleted too."),
            (2, "Its 2 resources will be deleted too."),
        ):
            with self.subTest(count=count):
                while self.goal.resources.count() < count:
                    add_resource(self.goal)

                text = get_page(self.client, self.path).text("main")

                # Exactly once: a substring check can't see a repeated warning.
                self.assertEqual(text.count(warning), 1)

    def test_it_sits_next_to_the_sessions_warning(self):
        add_session(self.goal)
        add_resource(self.goal)

        text = get_page(self.client, self.path).text("main")

        self.assertIn(
            "Its 1 session will be deleted too. Its 1 resource will be deleted too.",
            text,
        )
        self.assertEqual(text.count("will be deleted too."), 2)

    def test_a_goal_without_resources_has_no_resource_warning(self):
        add_session(self.goal)

        text = get_page(self.client, self.path).text("main")

        self.assertNotIn("resource", text)


class SummaryTestCase(TestCase):
    """Alice, her goal, and the AI service replaced: `self.complete` is a mock
    of ai.services.complete, and building a real OpenAI client fails the
    test, so no summary test can reach the network."""

    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.path = f"/goals/{self.goal.pk}/summary/"
        self.enterContext(
            patch(
                "ai.services.OpenAI",
                side_effect=AssertionError("a test tried to build a real client"),
            )
        )
        self.complete = self.enterContext(
            patch("ai.services.complete", return_value="Keep going")
        )

    def assert_nothing_stored(self):
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.summary, "")
        self.assertIsNone(self.goal.summary_generated_at)


class GoalSummaryAccessTests(SummaryTestCase):
    def setUp(self):
        super().setUp()
        add_session(self.goal)

    def test_the_summary_route_is_under_the_goal(self):
        self.assertEqual(reverse("goals:summary", args=[self.goal.pk]), self.path)

    def test_a_get_is_not_allowed(self):
        self.client.force_login(self.alice)

        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 405)
        self.complete.assert_not_called()

    def test_anonymous_visitors_are_sent_to_log_in(self):
        response = self.client.post(self.path)

        self.assertRedirects(
            response, login_redirect(self.path), fetch_redirect_response=False
        )
        self.complete.assert_not_called()
        self.assert_nothing_stored()

    def test_another_users_goal_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))

        response = self.client.post(self.path)
        missing = self.client.post("/goals/999999/summary/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, missing.content)
        self.complete.assert_not_called()
        self.assert_nothing_stored()


class GoalSummaryGenerateTests(SummaryTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        # 12 sessions of 10 minutes on 1-12 March, then 22 resources.
        self.sessions = [
            add_session(
                self.goal,
                tags=("django",) if n == 12 else (),
                date=f"2026-03-{n:02d}",
                duration_minutes=10,
                notes=f"session {n:02d}",
            )
            for n in range(1, 13)
        ]
        self.resources = [
            add_resource(self.goal, title=f"Resource {n:02d}") for n in range(1, 23)
        ]
        other = Goal.objects.create(owner=self.alice, title="Other")
        add_session(other, notes="elsewhere")
        add_resource(other, title="Elsewhere")
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        add_session(bobs, notes="bobs session")
        add_resource(bobs, title="Bobs")

    def generate(self, at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC)):
        with patch("django.utils.timezone.now", return_value=at):
            return self.client.post(self.path)

    def test_one_call_without_retries_with_the_recent_sessions_and_resources(self):
        from goals.prompts import summary_messages

        self.generate()

        newest_ten = LearningSession.objects.filter(
            pk__in=[s.pk for s in self.sessions[2:]]
        ).with_tags()
        expected = summary_messages(
            self.goal, list(newest_ten), 120, self.resources[2:][::-1]
        )
        self.complete.assert_called_once_with(*expected, max_retries=0)
        (_, user), _ = self.complete.call_args
        self.assertIn("session 12", user)
        self.assertIn("tags: django", user)
        self.assertIn("Total time: 2 h", user)
        for absent in (
            "session 01",
            "session 02",
            "Resource 01",
            "Resource 02",
            "elsewhere",
            "Elsewhere",
            "bobs session",
            "Bobs",
        ):
            self.assertNotIn(absent, user)

    def test_the_reply_is_stored_trimmed_with_its_time(self):
        self.complete.return_value = "  Keep going \n"

        response = self.generate(at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC))

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.summary, "Keep going")
        self.assertEqual(
            self.goal.summary_generated_at, datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
        )
        self.assertContains(self.client.get(response.url), "Summary generated.")

    def test_generating_does_not_change_the_goals_updated_time(self):
        updated = Goal.objects.get(pk=self.goal.pk).updated_at

        self.generate(at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC))

        self.assertEqual(Goal.objects.get(pk=self.goal.pk).updated_at, updated)

    def test_a_new_summary_replaces_the_last_one(self):
        self.generate(at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC))
        self.complete.return_value = "Second"

        self.generate(at=datetime(2026, 10, 2, 8, 0, tzinfo=UTC))

        self.goal.refresh_from_db()
        self.assertEqual(self.goal.summary, "Second")
        self.assertEqual(
            self.goal.summary_generated_at, datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
        )


class GoalSummaryEmptyGoalTests(SummaryTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        # Another goal's data doesn't make this one summarisable.
        other = Goal.objects.create(owner=self.alice, title="Other")
        add_session(other)
        add_resource(other)

    def test_a_goal_without_sessions_or_resources_is_not_sent_to_the_ai(self):
        response = self.client.post(self.path)

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.complete.assert_not_called()
        self.assert_nothing_stored()
        self.assertContains(
            self.client.get(response.url), "Log a session or attach a resource first."
        )

    def test_one_session_or_one_resource_is_enough(self):
        for add in (add_session, add_resource):
            with self.subTest(add=add.__name__):
                goal = Goal.objects.create(owner=self.alice, title=add.__name__)
                add(goal)
                self.complete.reset_mock()

                self.client.post(f"/goals/{goal.pk}/summary/")

                self.complete.assert_called_once()


class GoalSummaryErrorTests(SummaryTestCase):
    MESSAGES = (
        "The AI service is unavailable right now. Please try again later.",
        "The AI service returned an empty reply.",
    )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        add_session(self.goal)
        self.earlier = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
        Goal.objects.filter(pk=self.goal.pk).update(
            summary="Earlier summary", summary_generated_at=self.earlier
        )

    def test_an_ai_failure_goes_back_to_the_goal_with_its_message(self):
        from ai.services import AIServiceError

        for message in self.MESSAGES:
            with self.subTest(message=message):
                # Chained like the service's own errors, which must not reach
                # a 500 page (the SDK's text can echo part of the key).
                cause = RuntimeError("sk-secret-tail")
                error = AIServiceError(message)
                error.__cause__ = cause
                self.complete.side_effect = error

                response = self.client.post(self.path)

                self.assertRedirects(
                    response,
                    self.goal.get_absolute_url(),
                    fetch_redirect_response=False,
                )
                page = self.client.get(response.url)
                self.assertContains(page, message)
                self.assertNotContains(page, "sk-secret-tail")
                self.goal.refresh_from_db()
                self.assertEqual(self.goal.summary, "Earlier summary")
                self.assertEqual(self.goal.summary_generated_at, self.earlier)


class GoalDetailSummaryTests(SummaryTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        self.detail = self.goal.get_absolute_url()

    def summary_text(self):
        section = LabelledSectionText("summary-heading")
        section.feed(self.client.get(self.detail).content.decode())
        return section.text()

    def summary_form(self):
        page = get_page(self.client, self.detail)
        forms = [(f, i) for f, i in page.forms("main") if f.get("action") == self.path]
        self.assertEqual(len(forms), 1, "one form posts to the summary route")
        return forms[0]

    def test_without_a_summary_the_section_offers_to_generate_one(self):
        text = self.summary_text()

        self.assertTrue(text.startswith("Summary"), text)
        self.assertIn("No summary yet.", text)
        self.assertIn("Generate summary", text)
        self.assertNotIn("Regenerate", text)
        form, inputs = self.summary_form()
        self.assertEqual(form.get("method"), "post")
        self.assertIn("csrfmiddlewaretoken", {a.get("name") for a in inputs})

    def test_a_stored_summary_is_shown_with_its_time_and_can_be_regenerated(self):
        Goal.objects.filter(pk=self.goal.pk).update(
            summary="Two hours so far.\nNext: forms.",
            summary_generated_at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC),
        )

        text = self.summary_text()

        self.assertIn("Two hours so far. Next: forms.", text)
        self.assertIn("Generated 1 Oct 2026, 09:30", text)
        self.assertIn("Regenerate summary", text)
        self.assertNotIn("No summary yet.", text)
        self.assertContains(self.client.get(self.detail), "Two hours so far.<br>")
        self.summary_form()

    def test_the_summary_is_escaped(self):
        payload = "<script>alert(1)</script>"
        Goal.objects.filter(pk=self.goal.pk).update(
            summary=payload, summary_generated_at=datetime(2026, 10, 1, tzinfo=UTC)
        )

        response = self.client.get(self.detail)

        self.assertNotContains(response, payload)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")


class GoalSummaryCsrfTests(SummaryTestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        super().setUp()
        add_session(self.goal)
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.alice)

    def token(self):
        # GET the goal page first: sets the CSRF cookie and yields the token
        # of the form that posts to the summary route.
        page = get_page(self.csrf_client, self.goal.get_absolute_url())
        (inputs,) = [i for f, i in page.forms("main") if f.get("action") == self.path]
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path)

        self.assertEqual(response.status_code, 403)
        self.complete.assert_not_called()

    def test_a_post_with_the_forms_token_generates(self):
        (token,) = self.token()

        response = self.csrf_client.post(self.path, {"csrfmiddlewaretoken": token})

        self.assertEqual(response.status_code, 302)
        self.complete.assert_called_once()


class NextStepsTestCase(TestCase):
    """Alice, her goal, and the AI service replaced: `self.complete_json` is a
    mock of ai.services.complete_json, and building a real OpenAI client fails
    the test, so no next-steps test can reach the network."""

    STEPS = ("Build a form", "Read the ORM docs")

    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.path = f"/goals/{self.goal.pk}/next-steps/"
        self.enterContext(
            patch(
                "ai.services.OpenAI",
                side_effect=AssertionError("a test tried to build a real client"),
            )
        )
        self.complete_json = self.enterContext(
            patch("ai.services.complete_json", return_value={"steps": list(self.STEPS)})
        )

    def assert_nothing_stored(self):
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.next_steps, [])
        self.assertIsNone(self.goal.next_steps_generated_at)


class GoalNextStepsAccessTests(NextStepsTestCase):
    def test_the_next_steps_route_is_under_the_goal(self):
        self.assertEqual(reverse("goals:next_steps", args=[self.goal.pk]), self.path)

    def test_a_get_is_not_allowed(self):
        self.client.force_login(self.alice)

        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 405)
        self.complete_json.assert_not_called()

    def test_anonymous_visitors_are_sent_to_log_in(self):
        response = self.client.post(self.path)

        self.assertRedirects(
            response, login_redirect(self.path), fetch_redirect_response=False
        )
        self.complete_json.assert_not_called()
        self.assert_nothing_stored()

    def test_another_users_goal_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))

        response = self.client.post(self.path)
        missing = self.client.post("/goals/999999/next-steps/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, missing.content)
        self.complete_json.assert_not_called()
        self.assert_nothing_stored()


class GoalNextStepsSuggestTests(NextStepsTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        # 12 sessions of 10 minutes on 1-12 March, then 22 resources.
        self.sessions = [
            add_session(
                self.goal,
                tags=("django",) if n == 12 else (),
                date=f"2026-03-{n:02d}",
                duration_minutes=10,
                notes=f"session {n:02d}",
            )
            for n in range(1, 13)
        ]
        self.resources = [
            add_resource(self.goal, title=f"Resource {n:02d}") for n in range(1, 23)
        ]
        other = Goal.objects.create(owner=self.alice, title="Other")
        add_session(other, notes="elsewhere")
        add_resource(other, title="Elsewhere")
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        add_session(bobs, notes="bobs session")
        add_resource(bobs, title="Bobs")

    def suggest(self, at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC)):
        with patch("django.utils.timezone.now", return_value=at):
            return self.client.post(self.path)

    def test_one_call_without_retries_with_the_recent_sessions_and_resources(self):
        from goals.prompts import NEXT_STEPS_SCHEMA, next_steps_messages

        self.suggest()

        newest_ten = LearningSession.objects.filter(
            pk__in=[s.pk for s in self.sessions[2:]]
        ).with_tags()
        expected = next_steps_messages(
            self.goal, list(newest_ten), 120, self.resources[2:][::-1]
        )
        self.complete_json.assert_called_once_with(
            *expected, name="next_steps", schema=NEXT_STEPS_SCHEMA, max_retries=0
        )
        (_, user), _ = self.complete_json.call_args
        self.assertIn("session 12", user)
        self.assertIn("tags: django", user)
        self.assertIn("Total time: 2 h", user)
        for absent in (
            "session 01",
            "session 02",
            "Resource 01",
            "Resource 02",
            "elsewhere",
            "Elsewhere",
            "bobs session",
            "Bobs",
        ):
            self.assertNotIn(absent, user)

    def test_the_steps_are_stored_trimmed_in_order_with_their_time(self):
        self.complete_json.return_value = {
            "steps": [" Build a form \n", "Read the ORM docs", "Write a test"]
        }

        response = self.suggest(at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC))

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.goal.refresh_from_db()
        self.assertEqual(
            self.goal.next_steps, ["Build a form", "Read the ORM docs", "Write a test"]
        )
        self.assertEqual(
            self.goal.next_steps_generated_at, datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
        )
        self.assertContains(self.client.get(response.url), "Next steps suggested.")

    def test_suggesting_does_not_change_the_goals_updated_time(self):
        updated = Goal.objects.get(pk=self.goal.pk).updated_at

        self.suggest(at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC))

        self.assertEqual(Goal.objects.get(pk=self.goal.pk).updated_at, updated)

    def test_new_steps_replace_the_last_ones(self):
        self.suggest(at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC))
        self.complete_json.return_value = {"steps": ["Second", "Third"]}

        self.suggest(at=datetime(2026, 10, 2, 8, 0, tzinfo=UTC))

        self.goal.refresh_from_db()
        self.assertEqual(self.goal.next_steps, ["Second", "Third"])
        self.assertEqual(
            self.goal.next_steps_generated_at, datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
        )


class GoalNextStepsEmptyGoalTests(NextStepsTestCase):
    def test_a_goal_without_sessions_or_resources_still_gets_steps(self):
        # Another goal's session and resource don't count.
        other = Goal.objects.create(owner=self.alice, title="Other")
        add_session(other)
        add_resource(other)
        self.client.force_login(self.alice)

        response = self.client.post(self.path)

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.complete_json.assert_called_once()
        (_, user), _ = self.complete_json.call_args
        self.assertIn("No sessions.", user.splitlines())
        self.assertIn("No resources.", user.splitlines())
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.next_steps, list(self.STEPS))


class GoalNextStepsErrorTests(NextStepsTestCase):
    MESSAGES = (
        "The AI service is unavailable right now. Please try again later.",
        "The AI service returned an empty reply.",
        "The AI service returned an unexpected reply.",
    )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        self.earlier = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
        Goal.objects.filter(pk=self.goal.pk).update(
            next_steps=["Earlier step", "Another step"],
            next_steps_generated_at=self.earlier,
        )

    def assert_back_on_the_goal_with(self, response, message):
        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        page = self.client.get(response.url)
        self.assertContains(page, message)
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.next_steps, ["Earlier step", "Another step"])
        self.assertEqual(self.goal.next_steps_generated_at, self.earlier)
        return page

    def test_an_ai_failure_goes_back_to_the_goal_with_its_message(self):
        from ai.services import AIServiceError

        for message in self.MESSAGES:
            with self.subTest(message=message):
                # Chained like the service's own errors, which must not reach
                # a 500 page (the SDK's text can echo part of the key).
                error = AIServiceError(message)
                error.__cause__ = RuntimeError("sk-secret-tail")
                self.complete_json.side_effect = error

                page = self.assert_back_on_the_goal_with(
                    self.client.post(self.path), message
                )

                self.assertNotContains(page, "sk-secret-tail")

    def test_a_reply_with_the_wrong_number_of_steps_keeps_the_last_ones(self):
        for steps in (["Only one"], ["One", "Two", "Three", "Four"]):
            with self.subTest(steps=steps):
                self.complete_json.return_value = {"steps": steps}

                self.assert_back_on_the_goal_with(
                    self.client.post(self.path),
                    "The AI service returned an unexpected reply.",
                )


class GoalDetailNextStepsTests(NextStepsTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)
        self.detail = self.goal.get_absolute_url()

    def page_html(self):
        return self.client.get(self.detail).content.decode()

    def section_text(self):
        section = LabelledSectionText("next-steps-heading")
        section.feed(self.page_html())
        return section.text()

    def section_items(self):
        """The section's ordered-list items, as raw (escaped) HTML."""
        html = self.page_html()
        start = html.index('aria-labelledby="next-steps-heading"')
        section = html[start : html.index("</section>", start)]
        (ordered,) = re.findall(r"<ol\b.*?</ol>", section, re.DOTALL)
        items = re.findall(r"<li\b[^>]*>(.*?)</li>", ordered, re.DOTALL)
        return [item.strip() for item in items]

    def next_steps_form(self):
        page = get_page(self.client, self.detail)
        forms = [(f, i) for f, i in page.forms("main") if f.get("action") == self.path]
        self.assertEqual(len(forms), 1, "one form posts to the next-steps route")
        return forms[0]

    def store(self, steps):
        Goal.objects.filter(pk=self.goal.pk).update(
            next_steps=steps,
            next_steps_generated_at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC),
        )

    def test_without_steps_the_section_offers_to_suggest_some(self):
        text = self.section_text()

        self.assertTrue(text.startswith("Next steps"), text)
        self.assertIn("No next steps yet.", text)
        self.assertIn("Suggest next steps", text)
        self.assertNotIn("new", text)
        form, inputs = self.next_steps_form()
        self.assertEqual(form.get("method"), "post")
        self.assertIn("csrfmiddlewaretoken", {a.get("name") for a in inputs})

    def test_stored_steps_are_an_ordered_list_with_their_time(self):
        self.store(["Build a form", "Read the ORM docs", "Write a test"])

        text = self.section_text()

        self.assertEqual(
            self.section_items(), ["Build a form", "Read the ORM docs", "Write a test"]
        )
        self.assertIn("Suggested 1 Oct 2026, 09:30", text)
        self.assertIn("Suggest new next steps", text)
        self.assertNotIn("No next steps yet.", text)
        self.next_steps_form()

    def test_each_step_is_escaped(self):
        payload = "<script>alert(1)</script>"
        self.store([payload, "Read"])

        self.assertNotContains(self.client.get(self.detail), payload)
        self.assertEqual(
            self.section_items(), ["&lt;script&gt;alert(1)&lt;/script&gt;", "Read"]
        )

    def test_the_section_comes_right_after_the_summary(self):
        html = self.page_html()

        summary = html.index('aria-labelledby="summary-heading"')
        next_steps = html.index('aria-labelledby="next-steps-heading"')
        sessions = html.index(">Sessions</h2>")
        self.assertLess(summary, next_steps)
        self.assertLess(next_steps, sessions)


class GoalNextStepsCsrfTests(NextStepsTestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        super().setUp()
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.alice)

    def token(self):
        # GET the goal page first: sets the CSRF cookie and yields the token
        # of the form that posts to the next-steps route.
        page = get_page(self.csrf_client, self.goal.get_absolute_url())
        (inputs,) = [i for f, i in page.forms("main") if f.get("action") == self.path]
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path)

        self.assertEqual(response.status_code, 403)
        self.complete_json.assert_not_called()
        self.assert_nothing_stored()

    def test_a_post_with_the_forms_token_suggests(self):
        (token,) = self.token()

        response = self.csrf_client.post(self.path, {"csrfmiddlewaretoken": token})

        self.assertEqual(response.status_code, 302)
        self.complete_json.assert_called_once()


BADGE = re.compile(r'<span class="([^"]*\bbadge\b[^"]*)">\s*([^<]*?)\s*</span>')
STATUS_BADGES = {
    Goal.Status.PLANNED: "badge-neutral",
    Goal.Status.IN_PROGRESS: "badge-info",
    Goal.Status.DONE: "badge-success",
}


class GoalStatusBadgeTests(TestCase):
    """A goal's status is a coloured badge that always says the status."""

    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goals = {
            status: Goal.objects.create(
                owner=self.alice, title=f"G {status}", status=status
            )
            for status in Goal.Status.values
        }
        self.client.force_login(self.alice)

    def badges(self, path):
        html = self.client.get(path).content.decode()
        return [(text, classes.split()) for classes, text in BADGE.findall(html)]

    def test_each_goal_in_the_list_has_its_status_badge(self):
        badges = self.badges(reverse("goals:list"))

        for status, variant in STATUS_BADGES.items():
            with self.subTest(status=status):
                label = Goal.Status(status).label
                (classes,) = [c for text, c in badges if text == label]
                self.assertIn(variant, classes)

    def test_the_goal_page_shows_its_status_badge(self):
        for status, variant in STATUS_BADGES.items():
            with self.subTest(status=status):
                badges = self.badges(self.goals[status].get_absolute_url())
                label = Goal.Status(status).label
                (classes,) = [c for text, c in badges if text == label]
                self.assertIn(variant, classes)

    def test_every_status_has_a_badge_colour(self):
        self.assertEqual(set(STATUS_BADGES), set(Goal.Status.values))


class GoalDetailCardTests(TestCase):
    """The goal page's sections are cards, each named by its own heading."""

    def test_summary_next_steps_sessions_and_resources_are_labelled_cards(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.client.force_login(alice)

        page = get_page(self.client, goal.get_absolute_url())

        sections = [a for t, a in page.elements if t == "section"]
        self.assertEqual(
            [a.get("aria-labelledby") for a in sections],
            [
                "summary-heading",
                "next-steps-heading",
                "sessions-heading",
                "resources-heading",
            ],
        )
        h2_ids = {a.get("id") for t, a in page.elements if t == "h2"}
        for attrs in sections:
            with self.subTest(section=attrs["aria-labelledby"]):
                self.assertIn("card", attrs.get("class", "").split())
                self.assertIn(attrs["aria-labelledby"], h2_ids)

    def test_resource_titles_wrap_between_words_not_inside_them(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        Resource.objects.create(
            goal=goal, url="https://docs.djangoproject.com/", title="Django docs"
        )
        self.client.force_login(alice)

        page = get_page(self.client, goal.get_absolute_url())

        (link,) = [
            a.get("class", "").split()
            for t, a in page.elements
            if t == "a" and a.get("href") == "https://docs.djangoproject.com/"
        ]
        self.assertIn("break-words", link)
        self.assertNotIn("break-all", link)
