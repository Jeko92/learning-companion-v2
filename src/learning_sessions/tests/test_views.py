import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import Http404
from django.shortcuts import resolve_url
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import get_resolver, reverse
from django.utils import timezone
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from core.tests.html import PageParser
from goals.models import Goal
from learning_sessions.models import LearningSession
from tags.models import Tag, TagManager

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


class SessionCreateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/sessions/new/"

    def test_a_valid_post_adds_the_session_to_the_goal(self):
        response = self.client.post(self.path, valid_data(notes="Read the forms docs."))

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        (session,) = LearningSession.objects.all()
        self.assertEqual(session.goal, self.goal)
        self.assertEqual(str(session.date), "2026-03-01")
        self.assertEqual(session.duration_minutes, 45)
        self.assertEqual(session.notes, "Read the forms docs.")
        self.assertContains(self.client.get(response.url), "Session added.")

    def test_a_posted_goal_or_timestamps_are_ignored(self):
        other = Goal.objects.create(owner=self.alice, title="Other")
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        for goal in (other, bobs):
            with self.subTest(goal=goal.title):
                self.client.post(
                    self.path,
                    valid_data(
                        goal=goal.pk,
                        created_at="2000-01-01 00:00",
                        updated_at="2000-01-01 00:00",
                    ),
                )

                session = LearningSession.objects.latest("id")
                self.assertEqual(session.goal, self.goal)
                self.assertGreater(session.created_at.year, 2000)
                self.assertGreater(session.updated_at.year, 2000)
        self.assertFalse(LearningSession.objects.exclude(goal=self.goal).exists())

    def test_invalid_input_is_rejected_and_nothing_is_saved(self):
        tomorrow = str(timezone.localdate() + timedelta(days=1))
        cases = [
            ("future date", {"date": tomorrow}, "date",
             "A session can't be in the future."),
            ("zero minutes", {"duration_minutes": "0"}, "duration_minutes",
             "Ensure this value is greater than or equal to 1."),
            ("over a day", {"duration_minutes": "1441"}, "duration_minutes",
             "Ensure this value is less than or equal to 1440."),
            ("fraction", {"duration_minutes": "1.5"}, "duration_minutes",
             "Enter a whole number."),
            ("not a number", {"duration_minutes": "abc"}, "duration_minutes",
             "Enter a whole number."),
            ("no duration", {"duration_minutes": ""}, "duration_minutes",
             "This field is required."),
            ("long notes", {"notes": "x" * 2001}, "notes",
             "Ensure this value has at most 2000 characters (it has 2001)."),
        ]  # fmt: skip
        for case, changes, field, message in cases:
            with self.subTest(case=case):
                response = self.client.post(self.path, valid_data(**changes))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "learning_sessions/session_form.html")
                self.assertFormError(response.context["form"], field, message)
                self.assertFalse(LearningSession.objects.exists())

    def test_boundary_values_are_accepted(self):
        today = str(timezone.localdate())
        cases = {
            "today": valid_data(date=today),
            "one minute": valid_data(duration_minutes="1"),
            "a whole day": valid_data(duration_minutes="1440"),
            "date and duration only": {"date": today, "duration_minutes": "30"},
        }
        for case, data in cases.items():
            with self.subTest(case=case):
                before = LearningSession.objects.count()

                response = self.client.post(self.path, data)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(LearningSession.objects.count(), before + 1)


class SessionTagsTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.python = Tag.objects.create(name="Python")
        self.client.force_login(alice)
        self.path = f"/goals/{self.goal.pk}/sessions/new/"

    def post(self, tags):
        return self.client.post(self.path, valid_data(tags=tags))

    def test_typed_tags_are_trimmed_deduplicated_and_reused(self):
        response = self.post(" python , Machine Learning,, MACHINE learning , ")

        self.assertEqual(response.status_code, 302)
        (session,) = LearningSession.objects.all()
        self.assertEqual(
            sorted(tag.name for tag in session.tags.all()),
            ["Machine Learning", "Python"],
        )
        self.assertIn(self.python, session.tags.all())
        self.assertEqual(Tag.objects.filter(name__iexact="machine learning").count(), 1)

    def test_invalid_entries_are_named_and_nothing_is_saved(self):
        long_name = "x" * 51
        cases = {
            long_name: "Ensure this value has at most 50 characters (it has 51).",
            "Python\u200b": "Tag names can't contain control or invisible characters.",
        }
        for entry, message in cases.items():
            with self.subTest(entry=entry):
                response = self.post(f"Rust, {entry}")

                self.assertEqual(response.status_code, 200)
                self.assertFormError(
                    response.context["form"], "tags", f"“{entry}”: {message}"
                )
                self.assertFalse(LearningSession.objects.exists())
                self.assertEqual(list(Tag.objects.all()), [self.python])

    def test_too_many_tags_or_too_much_text_is_rejected(self):
        cases = {
            "21 tags": (
                ", ".join(f"t{n}" for n in range(21)),
                "You can have at most 20 tags.",
            ),
            "1001 characters": (
                "x" * 1001,
                "Ensure this value has at most 1000 characters (it has 1001).",
            ),
        }
        for case, (tags, message) in cases.items():
            with self.subTest(case=case):
                response = self.post(tags)

                self.assertEqual(response.status_code, 200)
                self.assertFormError(response.context["form"], "tags", message)
                self.assertFalse(LearningSession.objects.exists())
                self.assertEqual(list(Tag.objects.all()), [self.python])

    def test_twenty_tags_are_allowed(self):
        response = self.post(", ".join(f"t{n}" for n in range(20)))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LearningSession.objects.get().tags.count(), 20)

    def test_tags_are_created_through_get_or_create_by_name_on_save(self):
        real = TagManager.get_or_create_by_name
        calls = []

        def spy(manager, name):
            calls.append(name)
            return real(manager, name)

        with patch.object(TagManager, "get_or_create_by_name", spy):
            self.post("Rust, Go, 0" + "x" * 50)  # invalid: nothing is looked up
            self.assertEqual(calls, [])
            self.assertFalse(Tag.objects.exclude(pk=self.python.pk).exists())

            self.post("Rust, Go")

        self.assertEqual(calls, ["Rust", "Go"])
        self.assertEqual(
            sorted(t.name for t in LearningSession.objects.get().tags.all()),
            ["Go", "Rust"],
        )


class SessionCreateCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        self.path = f"/goals/{self.goal.pk}/sessions/new/"

    def token(self):
        # GET first: sets the CSRF cookie and yields the form's token.
        page = get_page(self.csrf_client, self.path)
        ((_, inputs),) = page.forms("main")
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path, valid_data())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(LearningSession.objects.exists())

    def test_a_post_with_the_forms_token_succeeds(self):
        tokens = self.token()
        self.assertEqual(len(tokens), 1)

        response = self.csrf_client.post(
            self.path, valid_data(csrfmiddlewaretoken=tokens[0])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(LearningSession.objects.exists())


def create_session(goal, tags=(), **fields):
    fields = {"date": "2026-03-01", "duration_minutes": 45, **fields}
    session = LearningSession.objects.create(goal=goal, **fields)
    session.tags.set(Tag.objects.get_or_create_by_name(n)[0] for n in tags)
    return session


class SessionEditPageTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.session = create_session(
            self.goal, tags=("zebra", "Django", "apple"), notes="Read the docs."
        )
        self.client.force_login(self.alice)
        self.path = f"/sessions/{self.session.pk}/edit/"

    def value_of(self, page, name):
        (attrs,) = [a for t, a in page.elements if a.get("name") == name]
        return attrs.get("value")

    def test_the_edit_page_has_a_route_of_its_own(self):
        self.assertEqual(
            reverse("learning_sessions:edit", args=[self.session.pk]), self.path
        )

    def test_the_form_is_prefilled_and_posts_to_itself(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning_sessions/session_form.html")
        page = get_page(self.client, self.path)

        ((form, _),) = page.forms("main")
        self.assertEqual(form.get("action"), self.path)
        # ISO, or a type="date" input would show an empty date.
        self.assertEqual(self.value_of(page, "date"), "2026-03-01")
        self.assertEqual(self.value_of(page, "duration_minutes"), "45")
        self.assertIn("Read the docs.", page.text("main"))
        # Alphabetical regardless of case.
        self.assertEqual(self.value_of(page, "tags"), "apple, Django, zebra")

    def test_the_page_names_the_goal_and_cancels_back_to_it(self):
        page = get_page(self.client, self.path)

        self.assertIn("Learn Django", page.text("main"))
        self.assertIn((self.goal.get_absolute_url(), "Cancel"), page.links("main"))

    def test_user_text_is_escaped(self):
        self.goal.title = PAYLOAD
        self.goal.save()
        self.session.notes = PAYLOAD
        self.session.save()
        self.session.tags.add(Tag.objects.get_or_create_by_name(PAYLOAD)[0])

        response = self.client.get(self.path)

        self.assertNotContains(response, PAYLOAD)
        self.assertContains(response, ESCAPED)


class SessionEditAccessTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.session = create_session(self.goal, tags=("Python",))
        self.path = f"/sessions/{self.session.pk}/edit/"

    def assert_untouched(self):
        self.session.refresh_from_db()
        self.assertEqual(self.session.duration_minutes, 45)
        self.assertEqual([t.name for t in self.session.tags.all()], ["Python"])

    def test_anonymous_visitors_are_sent_to_log_in(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                data = valid_data(tags="Rust") if method == "post" else None
                response = getattr(self.client, method)(self.path, data)

                self.assertRedirects(
                    response, login_redirect(self.path), fetch_redirect_response=False
                )
                self.assert_untouched()

    def test_another_users_session_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))
        cases = {
            "get": None,
            "valid post": valid_data(duration_minutes="90", tags="Rust"),
            "invalid post": valid_data(duration_minutes="0", date="2999-01-01"),
        }
        for case, data in cases.items():
            with self.subTest(case=case):
                method = self.client.get if data is None else self.client.post

                response = method(self.path, data)
                missing = method("/sessions/999999/edit/", data)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, missing.content)
                self.assert_untouched()


class SessionEditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.session = create_session(self.goal, tags=("Python",), notes="Old")
        self.bob = User.objects.create_user("bob")
        self.bobs_goal = Goal.objects.create(owner=self.bob, title="B")
        self.client.force_login(self.alice)
        self.path = f"/sessions/{self.session.pk}/edit/"

    def tag_names(self, session):
        return sorted(t.name for t in session.tags.all())

    def test_a_valid_post_updates_the_session_and_replaces_its_tags(self):
        response = self.client.post(
            self.path,
            valid_data(
                date="2026-02-01", duration_minutes="90", notes="New", tags="Rust, Go"
            ),
        )

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.session.refresh_from_db()
        self.assertEqual(str(self.session.date), "2026-02-01")
        self.assertEqual(self.session.duration_minutes, 90)
        self.assertEqual(self.session.notes, "New")
        self.assertEqual(self.tag_names(self.session), ["Go", "Rust"])
        self.assertContains(self.client.get(response.url), "Session updated.")

    def test_an_empty_tags_field_removes_all_tags(self):
        self.client.post(self.path, valid_data(tags=""))

        self.assertEqual(self.tag_names(self.session), [])

    def test_the_goal_cannot_be_changed(self):
        other = Goal.objects.create(owner=self.alice, title="Other")
        for goal in (other, self.bobs_goal):
            with self.subTest(goal=goal.title):
                response = self.client.post(self.path, valid_data(goal=goal.pk))

                self.assertEqual(response.status_code, 302)
                self.session.refresh_from_db()
                self.assertEqual(self.session.goal, self.goal)

    def test_an_invalid_post_changes_nothing(self):
        tomorrow = str(timezone.localdate() + timedelta(days=1))

        response = self.client.post(
            self.path, valid_data(date=tomorrow, duration_minutes="90", tags="Rust")
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "date", "A session can't be in the future."
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.duration_minutes, 45)
        self.assertEqual(self.tag_names(self.session), ["Python"])
        self.assertFalse(Tag.objects.filter(name="Rust").exists())

    def test_another_users_session_keeps_a_shared_tag(self):
        bobs_session = create_session(self.bobs_goal, tags=("python",))

        self.client.post(self.path, valid_data(tags="Rust"))

        self.assertEqual(self.tag_names(bobs_session), ["Python"])
        self.assertTrue(Tag.objects.filter(name="Python").exists())


class SessionEditCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.session = create_session(goal)
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        self.path = f"/sessions/{self.session.pk}/edit/"

    def token(self):
        # GET first: sets the CSRF cookie and yields the form's token.
        page = get_page(self.csrf_client, self.path)
        ((_, inputs),) = page.forms("main")
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path, valid_data(duration_minutes="90"))

        self.assertEqual(response.status_code, 403)
        self.session.refresh_from_db()
        self.assertEqual(self.session.duration_minutes, 45)

    def test_a_post_with_the_forms_token_succeeds(self):
        tokens = self.token()
        self.assertEqual(len(tokens), 1)

        response = self.csrf_client.post(
            self.path, valid_data(duration_minutes="90", csrfmiddlewaretoken=tokens[0])
        )

        self.assertEqual(response.status_code, 302)


class SessionDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.session = create_session(self.goal, tags=("Python",), duration_minutes=90)
        self.client.force_login(self.alice)
        self.path = f"/sessions/{self.session.pk}/delete/"

    def test_the_delete_page_has_a_route_of_its_own(self):
        self.assertEqual(
            reverse("learning_sessions:delete", args=[self.session.pk]), self.path
        )

    def test_a_get_asks_for_confirmation_and_deletes_nothing(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "learning_sessions/session_confirm_delete.html"
        )
        page = get_page(self.client, self.path)

        text = page.text("main")
        for shown in ("1 Mar 2026", "1 h 30 min", "Learn Django"):
            self.assertIn(shown, text)
        ((form, _),) = page.forms("main")
        self.assertEqual(form.get("method"), "post")
        self.assertEqual(form.get("action"), self.path)
        self.assertIn((self.goal.get_absolute_url(), "Cancel"), page.links("main"))
        self.assertTrue(LearningSession.objects.filter(pk=self.session.pk).exists())

    def test_durations_read_as_hours_and_minutes(self):
        for minutes, shown in ((45, "45 min"), (120, "2 h"), (90, "1 h 30 min")):
            with self.subTest(minutes=minutes):
                self.session.duration_minutes = minutes
                self.session.save()

                self.assertIn(shown, get_page(self.client, self.path).text("main"))

    def test_a_post_deletes_the_session_only(self):
        bobs_goal = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        bobs_session = create_session(bobs_goal, tags=("python",))

        response = self.client.post(self.path)

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.assertFalse(LearningSession.objects.filter(pk=self.session.pk).exists())
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())
        self.assertTrue(Tag.objects.filter(name="Python").exists())
        self.assertEqual([t.name for t in bobs_session.tags.all()], ["Python"])
        self.assertContains(self.client.get(response.url), "Session deleted.")

    def test_the_goal_title_is_escaped(self):
        self.goal.title = PAYLOAD
        self.goal.save()

        response = self.client.get(self.path)

        self.assertNotContains(response, PAYLOAD)
        self.assertContains(response, ESCAPED)


class SessionDeleteAccessTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.session = create_session(goal)
        self.path = f"/sessions/{self.session.pk}/delete/"

    def assert_untouched(self):
        self.assertTrue(LearningSession.objects.filter(pk=self.session.pk).exists())

    def test_anonymous_visitors_are_sent_to_log_in(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.path)

                self.assertRedirects(
                    response, login_redirect(self.path), fetch_redirect_response=False
                )
                self.assert_untouched()

    def test_another_users_session_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.path)
                missing = getattr(self.client, method)("/sessions/999999/delete/")

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, missing.content)
                self.assert_untouched()


class SessionDeleteCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.session = create_session(goal)
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        self.path = f"/sessions/{self.session.pk}/delete/"

    def token(self):
        # GET first: sets the CSRF cookie and yields the form's token.
        page = get_page(self.csrf_client, self.path)
        ((_, inputs),) = page.forms("main")
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(LearningSession.objects.filter(pk=self.session.pk).exists())

    def test_a_post_with_the_forms_token_succeeds(self):
        tokens = self.token()
        self.assertEqual(len(tokens), 1)

        response = self.csrf_client.post(self.path, {"csrfmiddlewaretoken": tokens[0]})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(LearningSession.objects.exists())


class SessionListTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/sessions/"

    def test_the_list_has_a_route_under_the_goal(self):
        self.assertEqual(
            reverse("learning_sessions:list", args=[self.goal.pk]), self.path
        )

    def test_the_page_names_the_goal_and_links_back_and_to_add(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning_sessions/session_list.html")
        page = get_page(self.client, self.path)

        self.assertIn("Learn Django", page.text("main"))
        links = page.links("main")
        self.assertIn((self.goal.get_absolute_url(), "Back to goal"), links)
        self.assertIn((f"{self.path}new/", "Add session"), links)

    def test_only_this_goals_sessions_newest_first(self):
        other = Goal.objects.create(owner=self.alice, title="Other")
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        create_session(self.goal, date="2026-02-01", notes="oldest")
        create_session(self.goal, date="2026-03-01", notes="earlier entry")
        create_session(self.goal, date="2026-03-01", notes="later entry")
        create_session(other, notes="other goal")
        create_session(bobs, notes="bobs goal")

        text = get_page(self.client, self.path).text("main")

        self.assertNotIn("other goal", text)
        self.assertNotIn("bobs goal", text)
        positions = [text.index(n) for n in ("later entry", "earlier entry", "oldest")]
        self.assertEqual(positions, sorted(positions))

    def test_each_session_shows_its_details_and_links(self):
        session = create_session(
            self.goal,
            tags=("zebra", "Django", "apple"),
            duration_minutes=90,
            notes="Read the docs.",
        )

        page = get_page(self.client, self.path)

        text = page.text("main")
        for shown in (
            "1 Mar 2026",
            "1 h 30 min",
            "apple Django zebra",
            "Read the docs.",
        ):
            self.assertIn(shown, text)
        links = page.links("main")
        self.assertIn((f"/sessions/{session.pk}/edit/", "Edit"), links)
        self.assertIn((f"/sessions/{session.pk}/delete/", "Delete"), links)

    def test_a_goal_without_sessions_says_so(self):
        self.assertIn("No sessions yet.", get_page(self.client, self.path).text("main"))

    def test_user_text_is_escaped(self):
        create_session(self.goal, tags=(PAYLOAD,), notes=PAYLOAD)

        response = self.client.get(self.path)

        self.assertNotContains(response, PAYLOAD)
        self.assertContains(response, ESCAPED)


class SessionListPaginationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        alice = User.objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        for n in range(21):
            create_session(self.goal, date=f"2026-01-{n + 1:02}", notes=f"#{n + 1}#")
        bobs = Goal.objects.create(owner=User.objects.create_user("bob"), title="B")
        for _ in range(30):
            create_session(bobs)
        self.client.force_login(alice)
        self.path = f"/goals/{self.goal.pk}/sessions/"

    def numbers(self, page):
        return [int(n) for n in re.findall(r"#(\d+)#", page.text("main"))]

    def test_twenty_sessions_per_page(self):
        first = get_page(self.client, self.path)
        second = get_page(self.client, f"{self.path}?page=2")

        self.assertEqual(self.numbers(first), list(range(21, 1, -1)))
        self.assertEqual(self.numbers(second), [1])
        self.assertIn(("?page=2", "Next"), first.links("main"))
        self.assertNotIn("Previous", first.text("main"))
        self.assertIn(("?page=1", "Previous"), second.links("main"))

    def test_pages_past_the_end_or_not_numbers_are_404(self):
        for page in ("99", "abc"):
            with self.subTest(page=page):
                response = self.client.get(self.path, {"page": page})

                self.assertEqual(response.status_code, 404)


class SessionListAccessTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        create_session(self.goal, notes="private")
        self.path = f"/goals/{self.goal.pk}/sessions/"

    def test_anonymous_visitors_are_sent_to_log_in(self):
        response = self.client.get(self.path)

        self.assertRedirects(
            response, login_redirect(self.path), fetch_redirect_response=False
        )

    def test_another_users_goal_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))

        response = self.client.get(self.path)
        missing = self.client.get("/goals/999999/sessions/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, missing.content)


class SessionListQueryCountTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(alice)
        self.small = Goal.objects.create(owner=alice, title="Small")
        create_session(self.small, tags=("a",))
        self.large = Goal.objects.create(owner=alice, title="Large")
        for _ in range(20):
            create_session(self.large, tags=("a", "b", "c"))

    def queries_for(self, goal):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"/goals/{goal.pk}/sessions/")
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_the_query_count_does_not_grow_with_sessions_or_tags(self):
        self.assertEqual(self.queries_for(self.large), self.queries_for(self.small))

    def test_the_list_takes_a_fixed_number_of_queries(self):
        # Login session, user, goal, page count, sessions, their tags.
        with self.assertNumQueries(6):
            self.client.get(f"/goals/{self.large.pk}/sessions/")


class SessionViewsScopingTests(TestCase):
    def test_every_session_view_scopes_through_the_own_sessions_mixins(self):
        routes = {p.name: p for p in session_routes()}

        # A new route must be added here deliberately, not slip past the check.
        self.assertEqual(set(routes), {"list", "create", "edit", "delete"})

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
