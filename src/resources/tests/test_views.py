from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import resolve_url
from django.test import Client, RequestFactory, TestCase
from django.urls import get_resolver, reverse
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from core.tests.html import PageParser
from goals.models import Goal
from resources.forms import ResourceForm
from resources.models import Resource

PASSWORD = "Tr4ck-Learning!"
PAYLOAD = "<script>alert(1)</script>"
ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


def resource_routes():
    """The resource URL patterns, found through the root URLconf, so a route
    that isn't mounted fails an assertion rather than an import."""
    for pattern in get_resolver().url_patterns:
        if getattr(pattern, "namespace", None) == "resources":
            return pattern.url_patterns
    return []


def valid_data(**changes):
    return {
        "url": "https://docs.djangoproject.com/",
        "title": "Django docs",
        "type": "doc",
        **changes,
    }


class ResourceCreatePageTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def test_the_create_page_has_a_route_under_the_goal(self):
        self.assertEqual(reverse("resources:create", args=[self.goal.pk]), self.path)

    def test_the_form_posts_to_itself_with_the_allowed_fields_only(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources/resource_form.html")
        page = get_page(self.client, self.path)

        ((form, _),) = page.forms("main")
        self.assertEqual(form.get("method"), "post")
        self.assertEqual(form.get("action"), self.path)
        # The page's own controls; the header's theme switch isn't a form field.
        names = {
            a.get("name")
            for i, (t, a) in enumerate(page.elements)
            if t in ("input", "select", "textarea")
            and a.get("name")
            and page.inside(i, lambda tag, _: tag == "main")
        }
        self.assertEqual(names, {"csrfmiddlewaretoken", "url", "title", "type"})

    def test_the_type_is_a_select_of_the_four_types_defaulting_to_article(self):
        page = get_page(self.client, self.path)

        options = [a for t, a in page.elements if t == "option"]
        self.assertEqual(
            [o.get("value") for o in options], ["article", "video", "repo", "doc"]
        )
        selected = [o.get("value") for o in options if "selected" in o]
        self.assertEqual(selected, ["article"])

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


class ResourceCreateAccessTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def test_anonymous_visitors_are_sent_to_log_in(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                # Only the POST carries data; on a GET it would land in `next`.
                data = valid_data() if method == "post" else None
                response = getattr(self.client, method)(self.path, data)

                self.assertRedirects(
                    response, login_redirect(self.path), fetch_redirect_response=False
                )
                self.assertFalse(Resource.objects.exists())

    def test_another_users_goal_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))
        cases = {
            "get": None,
            "valid post": valid_data(),
            "invalid post": valid_data(url="javascript:alert(1)", title=""),
        }
        for case, data in cases.items():
            with self.subTest(case=case):
                method = self.client.get if data is None else self.client.post

                response = method(self.path, data)
                missing = method("/goals/999999/resources/new/", data)

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, missing.content)
                self.assertFalse(Resource.objects.exists())


class ResourceCreateTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def test_a_valid_post_attaches_the_resource_to_the_goal(self):
        response = self.client.post(
            self.path,
            valid_data(url="  https://www.djangoproject.com/  ", title="  Docs  "),
        )

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        (resource,) = Resource.objects.all()
        self.assertEqual(resource.goal, self.goal)
        self.assertEqual(resource.url, "https://www.djangoproject.com/")
        self.assertEqual(resource.title, "Docs")
        self.assertEqual(resource.type, Resource.Type.DOC)
        self.assertContains(self.client.get(response.url), "Resource added.")

    def test_a_url_without_a_scheme_is_stored_as_https(self):
        # Django's URLField form field assumes https; pinned so a change shows.
        self.client.post(self.path, valid_data(url="example.com/guide"))

        self.assertEqual(Resource.objects.get().url, "https://example.com/guide")

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
                        url=f"https://example.com/{goal.pk}",
                        goal=goal.pk,
                        created_at="2000-01-01 00:00",
                        updated_at="2000-01-01 00:00",
                    ),
                )

                resource = Resource.objects.latest("id")
                self.assertEqual(resource.goal, self.goal)
                self.assertGreater(resource.created_at.year, 2000)
                self.assertGreater(resource.updated_at.year, 2000)
        self.assertEqual(Resource.objects.filter(goal=self.goal).count(), 2)
        self.assertFalse(Resource.objects.exclude(goal=self.goal).exists())


class ResourceCreateCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def token(self):
        # GET first: sets the CSRF cookie and yields the form's token.
        page = get_page(self.csrf_client, self.path)
        ((_, inputs),) = page.forms("main")
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path, valid_data())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Resource.objects.exists())

    def test_a_post_with_the_forms_token_succeeds(self):
        tokens = self.token()
        self.assertEqual(len(tokens), 1)

        response = self.csrf_client.post(
            self.path, valid_data(csrfmiddlewaretoken=tokens[0])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Resource.objects.exists())


class ResourceCreateValidationTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def test_invalid_input_is_rejected_and_nothing_is_saved(self):
        required = "This field is required."
        bad_url = "Enter a valid URL."
        cases = [
            ("no url", {"url": ""}, "url", required),
            ("no title", {"title": ""}, "title", required),
            ("blank title", {"title": "   "}, "title", required),
            ("malformed url", {"url": "https://"}, "url", bad_url),
            ("javascript url", {"url": "javascript:alert(1)"}, "url", bad_url),
            ("data url", {"url": "data:text/html,hi"}, "url", bad_url),
            ("ftp url", {"url": "ftp://example.com/file"}, "url", bad_url),
            ("long title", {"title": "x" * 201}, "title",
             "Ensure this value has at most 200 characters (it has 201)."),
            ("long url", {"url": "https://example.com/" + "a" * 2029}, "url",
             "Ensure this value has at most 2048 characters (it has 2049)."),
            ("unknown type", {"type": "podcast"}, "type",
             "Select a valid choice. podcast is not one of the available choices."),
        ]  # fmt: skip
        for case, changes, field, message in cases:
            with self.subTest(case=case):
                response = self.client.post(self.path, valid_data(**changes))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "resources/resource_form.html")
                # assertIn, not assertFormError: an over-long URL also fails
                # URLValidator's own length check, so it gets two errors.
                self.assertIn(message, response.context["form"].errors[field])
                self.assertFalse(Resource.objects.exists())

    def test_a_url_with_another_scheme_gets_exactly_one_error(self):
        for url in ("javascript:alert(1)", "data:text/html,hi", "ftp://example.com/f"):
            with self.subTest(url=url):
                response = self.client.post(self.path, valid_data(url=url))

                form = response.context["form"]
                self.assertEqual(form.errors.get_json_data()["url"], [
                    {"message": "Enter a valid URL.", "code": "invalid"}
                ])  # fmt: skip
                self.assertEqual(list(form.errors), ["url"])

    def test_an_invalid_post_keeps_the_entered_values(self):
        response = self.client.post(
            self.path, valid_data(title="Django docs", url="ftp://example.com/x")
        )

        page = PageParser()
        page.feed(response.content.decode())
        values = {
            a.get("name"): a.get("value") for t, a in page.elements if t == "input"
        }
        self.assertEqual(values["title"], "Django docs")
        self.assertEqual(values["url"], "ftp://example.com/x")
        selected = [a.get("value") for t, a in page.elements
                    if t == "option" and "selected" in a]  # fmt: skip
        self.assertEqual(selected, ["doc"])

    def test_an_entered_title_is_escaped_when_the_form_comes_back(self):
        response = self.client.post(self.path, valid_data(title=PAYLOAD, url=""))

        self.assertNotContains(response, PAYLOAD)
        self.assertContains(response, ESCAPED)

    def test_boundary_values_are_accepted(self):
        long_url = "https://example.com/" + "a" * 2028
        self.assertEqual(len(long_url), 2048)
        cases = {
            "200-character title": valid_data(title="x" * 200),
            "2,048-character url": valid_data(url=long_url),
            "uppercase scheme": valid_data(url="HTTPS://EXAMPLE.COM/upper"),
            **{
                f"type {value}": valid_data(url=f"https://example.com/{value}",
                                            type=value)
                for value in Resource.Type.values
            },
        }  # fmt: skip
        for case, data in cases.items():
            with self.subTest(case=case):
                response = self.client.post(self.path, data)

                self.assertRedirects(
                    response,
                    self.goal.get_absolute_url(),
                    fetch_redirect_response=False,
                )
        self.assertEqual(Resource.objects.count(), len(cases))


class ResourceCreateDuplicateTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        Resource.objects.create(goal=self.goal, url=valid_data()["url"], title="Docs")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def test_a_url_the_goal_already_has_is_a_form_error(self):
        response = self.client.post(self.path, valid_data(title="Again"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources/resource_form.html")
        self.assertFormError(
            response.context["form"], None, "This goal already has this resource."
        )
        self.assertContains(response, "This goal already has this resource.")
        self.assertEqual(Resource.objects.count(), 1)


class ResourceCreateRaceTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.client.force_login(self.alice)
        self.path = f"/goals/{self.goal.pk}/resources/new/"

    def test_a_duplicate_only_the_database_catches_is_a_form_error(self):
        Resource.objects.create(goal=self.goal, url=valid_data()["url"], title="Docs")

        # As if another request attached the URL between validation and insert.
        with patch.object(ResourceForm, "validate_constraints", lambda form: None):
            response = self.client.post(self.path, valid_data(title="Again"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources/resource_form.html")
        self.assertFormError(
            response.context["form"], None, "This goal already has this resource."
        )
        self.assertEqual(Resource.objects.count(), 1)

    def test_another_integrity_error_is_not_reported_as_a_duplicate(self):
        def failing_save(resource, *args, **kwargs):
            raise IntegrityError("some other constraint")

        with (
            patch.object(Resource, "save", failing_save),
            self.assertRaises(IntegrityError),
        ):
            self.client.post(self.path, valid_data())

        self.assertFalse(Resource.objects.exists())


def create_resource(goal, **fields):
    fields = {"url": "https://docs.djangoproject.com/", "title": "Django docs",
              "type": Resource.Type.DOC, **fields}  # fmt: skip
    return Resource.objects.create(goal=goal, **fields)


class ResourceDeleteTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.resource = create_resource(self.goal)
        self.client.force_login(self.alice)
        self.path = f"/resources/{self.resource.pk}/delete/"

    def test_the_delete_page_has_a_route_of_its_own(self):
        self.assertEqual(
            reverse("resources:delete", args=[self.resource.pk]), self.path
        )

    def test_a_get_asks_for_confirmation_and_deletes_nothing(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources/resource_confirm_delete.html")
        page = get_page(self.client, self.path)

        text = page.text("main")
        for shown in ("Django docs", "https://docs.djangoproject.com/", "Learn Django"):
            self.assertIn(shown, text)
        ((form, _),) = page.forms("main")
        self.assertEqual(form.get("method"), "post")
        self.assertEqual(form.get("action"), self.path)
        self.assertIn((self.goal.get_absolute_url(), "Cancel"), page.links("main"))
        self.assertTrue(Resource.objects.filter(pk=self.resource.pk).exists())

    def test_a_post_deletes_the_resource_only(self):
        other = create_resource(self.goal, url="https://example.com/other")

        response = self.client.post(self.path)

        self.assertRedirects(
            response, self.goal.get_absolute_url(), fetch_redirect_response=False
        )
        self.assertFalse(Resource.objects.filter(pk=self.resource.pk).exists())
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())
        self.assertEqual(list(Resource.objects.all()), [other])
        self.assertContains(self.client.get(response.url), "Resource deleted.")

    def test_the_title_url_and_goal_title_are_escaped(self):
        self.goal.title = PAYLOAD
        self.goal.save()
        for field, value in (
            ("title", PAYLOAD),
            ("url", f"https://example.com/?q={PAYLOAD}"),
        ):
            with self.subTest(field=field):
                Resource.objects.filter(pk=self.resource.pk).update(**{field: value})

                response = self.client.get(self.path)

                self.assertNotContains(response, PAYLOAD)
                self.assertContains(response, ESCAPED)


class ResourceDeleteAccessTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.resource = create_resource(goal)
        self.path = f"/resources/{self.resource.pk}/delete/"

    def assert_untouched(self):
        self.assertTrue(Resource.objects.filter(pk=self.resource.pk).exists())

    def test_anonymous_visitors_are_sent_to_log_in(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.path)

                self.assertRedirects(
                    response, login_redirect(self.path), fetch_redirect_response=False
                )
                self.assert_untouched()

    def test_another_users_resource_is_the_same_404_as_a_missing_one(self):
        self.client.force_login(get_user_model().objects.create_user("bob"))
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.path)
                missing = getattr(self.client, method)("/resources/999999/delete/")

                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, missing.content)
                self.assert_untouched()


class ResourceDeleteCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.resource = create_resource(goal)
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(alice)
        self.path = f"/resources/{self.resource.pk}/delete/"

    def token(self):
        # GET first: sets the CSRF cookie and yields the form's token.
        page = get_page(self.csrf_client, self.path)
        ((_, inputs),) = page.forms("main")
        return [a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"]

    def test_a_post_without_a_token_is_rejected(self):
        self.token()

        response = self.csrf_client.post(self.path)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Resource.objects.filter(pk=self.resource.pk).exists())

    def test_a_post_with_the_forms_token_succeeds(self):
        tokens = self.token()
        self.assertEqual(len(tokens), 1)

        response = self.csrf_client.post(self.path, {"csrfmiddlewaretoken": tokens[0]})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Resource.objects.exists())


class ResourceViewsScopingTests(TestCase):
    def test_every_resource_view_scopes_through_the_own_resources_mixins(self):
        routes = {p.name: p for p in resource_routes()}

        # A new route must be added here deliberately, not slip past the check.
        self.assertEqual(set(routes), {"create", "delete"})

        from resources.views import GoalResourcesMixin, OwnResourcesMixin

        User = get_user_model()
        alice = User.objects.create_user("alice")
        alices_goal = Goal.objects.create(owner=alice, title="Alice's goal")
        alices_other_goal = Goal.objects.create(owner=alice, title="Other")
        bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="B"
        )
        mine, other, bobs = (
            Resource.objects.create(goal=goal, url="https://example.com/", title="R")
            for goal in (alices_goal, alices_other_goal, bobs_goal)
        )
        for name, pattern in routes.items():
            view = pattern.callback.view_class
            with self.subTest(view=name):
                # A model on the view plus a wrong base order would serve
                # every user's resources silently (as for goals, see CLAUDE.md).
                self.assertIsNone(view.model)
                mro = view.__mro__
                django_qs = [
                    c for c in (SingleObjectMixin, MultipleObjectMixin) if c in mro
                ]
                self.assertTrue(django_qs)
                self.assertLess(
                    mro.index(OwnResourcesMixin), min(mro.index(c) for c in django_qs)
                )
                if "get_queryset" not in view.__dict__:
                    self.assertIn(
                        view.get_queryset,
                        (
                            OwnResourcesMixin.get_queryset,
                            GoalResourcesMixin.get_queryset,
                        ),
                    )
                request = RequestFactory().get("/")
                request.user = alice
                instance = view()
                if "goal_pk" in pattern.pattern.converters:
                    # Routes under a goal look the goal up through the owner.
                    self.assertTrue(issubclass(view, GoalResourcesMixin))
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
