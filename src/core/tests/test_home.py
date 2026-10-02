from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import resolve

from core import views

# Elements that never get an end tag, so they must not stay on the open stack.
VOID_ELEMENTS = {"base", "br", "hr", "img", "input", "link", "meta", "source", "wbr"}
SECTIONS = ("title", "header")


class PageParser(HTMLParser):
    """Collects the text inside each of SECTIONS, so tests check structure, not
    just that a string appears somewhere on the page."""

    def __init__(self):
        super().__init__()
        self.open_tags = []
        self.text = dict.fromkeys(SECTIONS, "")

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_ELEMENTS:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self.open_tags:
            last = len(self.open_tags) - 1 - self.open_tags[::-1].index(tag)
            del self.open_tags[last:]

    def handle_data(self, data):
        for section in SECTIONS:
            if section in self.open_tags:
                self.text[section] += data


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

        self.assertIn("Learning Companion", page.text["header"])
        self.assertIn("Learning Companion", page.text["title"])
