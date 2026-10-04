import re

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import URLResolver, get_resolver, include, path

PASSWORD = "Tr4ck-Learning!"
LOGIN_PATH = "/accounts/login/"

# The only views an anonymous visitor may reach. A new public view needs
# @login_not_required and an entry here, added deliberately.
PUBLIC_ROUTES = {
    "home",
    "favicon",
    "accounts:signup",
    "accounts:login",
    "accounts:logout",
    "admin:login",
}

# Sample values for path converters; the middleware answers before the view
# looks anything up, so the objects needn't exist. An unknown converter is a
# KeyError, so a new kind gets a sample on purpose.
SAMPLE_VALUES = {"int": "1"}


def unprotected(request):
    return HttpResponse("unprotected")


# For UnprotectedViewTests: a view with no login check of its own, plus the
# accounts URLs so LOGIN_URL ("accounts:login") still resolves.
urlpatterns = [
    path("unprotected/", unprotected),
    path("accounts/", include("accounts.urls")),
]


def routes(patterns=None, prefix="", namespaces=()):
    """(route, name, callback) for every URL pattern of the root URLconf,
    include()s and the admin's included. name is "namespace:name", with the
    route in place of the name for an unnamed pattern."""
    if patterns is None:
        patterns = get_resolver().url_patterns
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            inner = namespaces + ((pattern.namespace,) if pattern.namespace else ())
            yield from routes(pattern.url_patterns, route, inner)
        else:
            name = ":".join((*namespaces, pattern.name or route))
            yield route, name, pattern.callback


def sample_path(route):
    return "/" + re.sub(
        r"<(?:(?P<converter>\w+):)?\w+>",
        lambda match: SAMPLE_VALUES[match["converter"]],
        route,
    )


def login_redirect(url):
    return f"{LOGIN_PATH}?next={url}"


@override_settings(ROOT_URLCONF=__name__)
class UnprotectedViewTests(TestCase):
    """A view whose author forgot LoginRequiredMixin still fails closed."""

    def test_anonymous_visitors_are_sent_to_log_in(self):
        response = self.client.get("/unprotected/")

        self.assertRedirects(
            response, login_redirect("/unprotected/"), fetch_redirect_response=False
        )

    def test_logged_in_users_get_the_view(self):
        alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.client.force_login(alice)

        response = self.client.get("/unprotected/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"unprotected")


class PublicPagesTests(TestCase):
    """The allow-listed views still serve anonymous visitors."""

    def test_public_pages_answer_anonymous_get_requests(self):
        for url in ("/", "/favicon.ico", "/accounts/signup/", LOGIN_PATH):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_the_favicon_answers_an_anonymous_head_request(self):
        self.assertEqual(self.client.head("/favicon.ico").status_code, 200)

    def test_an_anonymous_log_out_lands_on_the_home_page(self):
        response = self.client.post("/accounts/logout/")

        self.assertRedirects(response, "/", fetch_redirect_response=False)


class LoginRequiredRouteTests(TestCase):
    """Every route requires a logged-in user unless it is allow-listed."""

    def test_only_the_allow_listed_routes_are_public(self):
        public = {
            name
            for _, name, callback in routes()
            if not getattr(callback, "login_required", True)
        }

        self.assertEqual(public, PUBLIC_ROUTES)

    def test_every_other_route_sends_anonymous_visitors_to_log_in(self):
        checked = set()
        for route, name, _ in routes():
            # The admin's regex routes are pinned in AdminLoginRequiredTests.
            if name in PUBLIC_ROUTES or name.startswith("admin:"):
                continue
            url = sample_path(route)
            with self.subTest(route=name, url=url):
                response = self.client.get(url)

                self.assertRedirects(
                    response, login_redirect(url), fetch_redirect_response=False
                )
            checked.add(name)

        # Guards against a walk that silently finds nothing.
        self.assertIn("goals:detail", checked)
        self.assertIn("learning_sessions:edit", checked)
        self.assertIn("dashboard:index", checked)


class AdminLoginRequiredTests(TestCase):
    """Django's admin under the middleware: its own views keep their admin
    log-in, model admin pages go to the app's log-in."""

    def test_the_admin_index_sends_anonymous_visitors_to_the_admin_log_in(self):
        response = self.client.get("/admin/")

        self.assertRedirects(
            response, "/admin/login/?next=/admin/", fetch_redirect_response=False
        )

    def test_model_admin_pages_send_anonymous_visitors_to_the_app_log_in(self):
        response = self.client.get("/admin/goals/goal/")

        self.assertRedirects(
            response,
            login_redirect("/admin/goals/goal/"),
            fetch_redirect_response=False,
        )

    def test_the_admin_log_in_stays_public(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
