from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase
from django.urls import get_resolver, reverse
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from core.tests.html import PageParser
from goals.models import Goal
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
        names = {
            a.get("name")
            for t, a in page.elements
            if t in ("input", "select", "textarea") and a.get("name")
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


class ResourceViewsScopingTests(TestCase):
    def test_every_resource_view_scopes_through_the_own_resources_mixins(self):
        routes = {p.name: p for p in resource_routes()}

        # A new route must be added here deliberately, not slip past the check.
        self.assertEqual(set(routes), {"create"})

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
