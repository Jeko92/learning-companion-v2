from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage import default_storage
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import URLResolver, get_resolver, resolve, reverse

from core import urls as core_urls
from core import views
from core.tests.html import PageParser

PITCH = (
    "Track your learning goals and sessions, and get AI-powered summaries"
    " and next steps."
)


class HomePageTests(TestCase):
    def get_page(self):
        response = self.client.get("/")
        parser = PageParser()
        parser.feed(response.content.decode())
        return parser

    def test_home_is_served_by_core_through_core_urls(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        match = resolve("/")
        self.assertIs(match.func, views.home)
        self.assertEqual(match.url_name, "home")
        self.assertIs(resolve("/", urlconf="core.urls").func, views.home)

    def test_root_urlconf_includes_core_urls_at_the_root(self):
        # resolve() gives the same match for a direct path() to the view, so
        # check the root URLconf for the include itself. include() imports the
        # module, so urlconf_name is the module, not the dotted path.
        includes = [
            str(pattern.pattern)
            for pattern in get_resolver().url_patterns
            if isinstance(pattern, URLResolver) and pattern.urlconf_name is core_urls
        ]

        self.assertEqual(includes, [""])

    def test_home_renders_home_template_extending_base(self):
        response = self.client.get("/")

        self.assertTemplateUsed(response, "home.html")
        self.assertTemplateUsed(response, "base.html")

    def test_templates_load_from_the_project_templates_dir(self):
        response = self.client.get("/")

        origins = {t.name: Path(t.origin.name) for t in response.templates}
        for name in ("base.html", "home.html"):
            with self.subTest(template=name):
                self.assertEqual(origins[name], settings.BASE_DIR / "templates" / name)

    def test_header_and_title_show_the_app_name(self):
        page = self.get_page()

        self.assertIn("Learning Companion", page.text("header"))
        self.assertIn("Learning Companion", page.text("title"))

    def test_anonymous_nav_has_no_goals_link(self):
        # "Goals" was a placeholder for everyone until goal-list-create made it
        # a link for logged-in users only (covered in accounts.tests.test_nav).
        page = self.get_page()

        self.assertNotIn("Goals", page.text("nav"))

    def test_layout_renders_messages_added_for_the_request(self):
        # No view adds messages yet, so attach the storage to a request by hand
        # and call the view directly.
        request = RequestFactory().get("/")
        SessionMiddleware(lambda request: None).process_request(request)
        request._messages = default_storage(request)
        messages.info(request, "Profile saved.")

        response = views.home(request)

        self.assertContains(response, "Profile saved.")

    def test_home_fills_the_layout_content_block_with_the_pitch(self):
        page = self.get_page()

        self.assertIn(PITCH, page.text("main"))
        self.assertNotIn(PITCH, render_to_string("base.html"))

    def test_logged_in_visitors_get_the_same_home_page_not_a_redirect(self):
        # dashboard-status sends log-in and sign-up to the dashboard, but "/"
        # stays the public home page for everyone. ui-polish gives each visitor
        # their own call to action, so only the shared content is compared.
        anonymous_main = self.get_page().text("main")
        user = get_user_model().objects.create_user("alice")
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        logged_in_main = self.get_page().text("main")
        for shared in ("Learning Companion", PITCH):
            with self.subTest(shared=shared):
                self.assertIn(shared, anonymous_main)
                self.assertIn(shared, logged_in_main)

    def test_layout_has_a_footer(self):
        page = self.get_page()

        self.assertIn("Learning Companion", page.text("footer"))

    def test_layout_links_the_tailwind_stylesheet_without_a_build(self):
        # Nothing checks that the built file exists, so this passes on a fresh
        # checkout where 'tailwind build' has never run.
        response = self.client.get("/")

        self.assertContains(
            response, '<link rel="stylesheet" href="/static/css/tailwind.css">'
        )


class HomeCallToActionTests(TestCase):
    """The home page's hero points each visitor at their next step."""

    def main_links(self):
        page = PageParser()
        page.feed(self.client.get("/").content.decode())
        links = {}
        for index, (tag, attrs) in enumerate(page.elements):
            if tag == "a" and page.inside(index, lambda t, _: t == "main"):
                links[attrs["href"]] = attrs.get("class", "").split()
        return page.links("main"), links

    def test_anonymous_visitors_are_invited_to_sign_up_or_log_in(self):
        links, classes = self.main_links()

        self.assertIn((reverse("accounts:signup"), "Sign up"), links)
        self.assertIn((reverse("accounts:login"), "Log in"), links)
        self.assertIn("btn-primary", classes[reverse("accounts:signup")])
        self.assertNotIn(reverse("dashboard:index"), classes)

    def test_logged_in_users_are_sent_to_their_dashboard(self):
        self.client.force_login(get_user_model().objects.create_user("alice"))

        links, classes = self.main_links()

        self.assertIn((reverse("dashboard:index"), "Go to your dashboard"), links)
        self.assertIn("btn-primary", classes[reverse("dashboard:index")])
        self.assertNotIn(reverse("accounts:signup"), classes)
