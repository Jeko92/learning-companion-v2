from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.storage import default_storage
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import URLResolver, get_resolver, resolve

from core import urls as core_urls
from core import views

# HTML void elements never get an end tag, so they must not stay on the open stack.
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SECTIONS = ("title", "header", "nav", "main", "footer")
PITCH = (
    "Track your learning goals and sessions, and get AI-powered summaries"
    " and next steps."
)


def collapse(pieces):
    """Joins text pieces with a space and collapses whitespace, so template
    formatting can't change a check and text can't match across elements."""
    return " ".join(" ".join(pieces).split())


class PageParser(HTMLParser):
    """Collects the text inside each of SECTIONS and the text inside any element
    with an href, so tests check structure, not just that a string appears
    somewhere on the page."""

    def __init__(self):
        super().__init__()
        self.open_tags = []
        self.pieces = {section: [] for section in SECTIONS}
        self.href_pieces = []

    def text(self, section):
        return collapse(self.pieces[section])

    def href_text(self):
        return collapse(self.href_pieces)

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_ELEMENTS:
            has_href = any(name == "href" for name, _ in attrs)
            self.open_tags.append((tag, has_href))

    def handle_endtag(self, tag):
        names = [name for name, _ in self.open_tags]
        if tag in names:
            del self.open_tags[len(names) - 1 - names[::-1].index(tag) :]

    def handle_data(self, data):
        names = {name for name, _ in self.open_tags}
        for section in SECTIONS:
            if section in names:
                self.pieces[section].append(data)
        if any(has_href for _, has_href in self.open_tags):
            self.href_pieces.append(data)


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

    def test_nav_shows_placeholders_that_are_not_links(self):
        page = self.get_page()

        for placeholder in ("Goals", "Log in"):
            with self.subTest(placeholder=placeholder):
                self.assertIn(placeholder, page.text("nav"))
                self.assertNotIn(placeholder, page.href_text())

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
