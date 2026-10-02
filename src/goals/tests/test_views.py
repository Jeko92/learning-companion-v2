import re
from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import Client, TestCase
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
