from itertools import pairwise

from django.contrib import messages
from django.contrib.messages.storage import default_storage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from core import views
from core.tests.html import PageParser, has_class
from core.tests.pages import AllPagesMixin


def is_focusable(tag, attrs):
    if "tabindex" in attrs:
        return attrs["tabindex"] != "-1"
    if tag == "a":
        return "href" in attrs
    if tag == "input":
        return attrs.get("type") != "hidden"
    return tag in ("button", "select", "textarea", "summary")


class SkipLinkTests(AllPagesMixin, TestCase):
    """Keyboard users can jump past the header and nav to the content."""

    def test_the_first_focusable_element_is_a_skip_link_to_main(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                tag, attrs = next(
                    (t, a) for t, a in parser.elements if is_focusable(t, a)
                )
                self.assertEqual((tag, attrs.get("href")), ("a", "#main"))

    def test_the_skip_link_target_is_the_main_element(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                targets = [t for t, a in parser.elements if a.get("id") == "main"]
                self.assertEqual(targets, ["main"])


HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


class PageStructureTests(AllPagesMixin, TestCase):
    """Every page has the same landmarks and a clean heading outline."""

    def test_every_page_has_one_header_one_main_and_one_footer(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                tags = [tag for tag, _ in parser.elements]
                for landmark in ("header", "main", "footer"):
                    self.assertEqual(tags.count(landmark), 1, landmark)

    def test_every_nav_has_an_accessible_name(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                navs = [attrs for tag, attrs in parser.elements if tag == "nav"]
                self.assertTrue(navs)
                for attrs in navs:
                    self.assertTrue(
                        attrs.get("aria-label") or attrs.get("aria-labelledby"), attrs
                    )

    def test_every_page_has_exactly_one_h1(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                tags = [tag for tag, _ in parser.elements]
                self.assertEqual(tags.count("h1"), 1)

    def test_heading_levels_never_skip(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                levels = [int(t[1]) for t, _ in parser.elements if t in HEADINGS]
                self.assertEqual(levels[0], 1)
                for previous, level in pairwise(levels):
                    self.assertLessEqual(level, previous + 1, levels)


class MessageTests(TestCase):
    """Flash messages look like their level and are announced."""

    def render_with_message(self, level, text):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda request: None).process_request(request)
        request._messages = default_storage(request)
        messages.add_message(request, level, text)
        response = views.home(request)
        self.assertContains(response, text)
        parser = PageParser()
        parser.feed(response.content.decode())
        return [
            attrs
            for _, attrs in parser.elements
            if "alert" in attrs.get("class", "").split()
        ]

    def test_each_level_renders_as_its_daisyui_alert_with_the_right_role(self):
        cases = (
            (messages.SUCCESS, "alert-success", "status"),
            (messages.INFO, "alert-info", "status"),
            (messages.WARNING, "alert-warning", "status"),
            (messages.ERROR, "alert-error", "alert"),
        )
        for level, css_class, role in cases:
            with self.subTest(css_class=css_class):
                (alert,) = self.render_with_message(level, "Something happened.")
                self.assertIn(css_class, alert["class"].split())
                self.assertEqual(alert.get("role"), role)


SITE = "Learning Companion"


class PageTitleTests(AllPagesMixin, TestCase):
    """Each page type has its own title, so tabs and history are told apart."""

    def test_the_home_page_title_is_the_site_name(self):
        titles = {page.name: parser.text("title") for page, parser in self.walk()}
        self.assertEqual(titles["home"], SITE)
        self.assertEqual(titles["dashboard"], f"Dashboard · {SITE}")

    def test_every_other_page_title_names_the_page_then_the_site(self):
        for page, parser in self.walk():
            if page.name != "home":
                with self.subTest(page=page.name):
                    title = parser.text("title")
                    self.assertTrue(title.endswith(f" · {SITE}"), title)
                    self.assertNotEqual(title, f" · {SITE}")

    def test_the_page_titles_are_all_different(self):
        titles = [parser.text("title") for _, parser in self.walk()]
        self.assertEqual(len(set(titles)), len(titles), titles)


DELETE_PAGES = {"goal delete", "session delete", "resource delete"}


def in_main(tag, attrs):
    return tag == "main"


def is_button(tag, attrs):
    return tag == "button" or (tag == "input" and attrs.get("type") == "submit")


class ButtonTests(AllPagesMixin, TestCase):
    """Every button looks like one; the page's own actions stand out."""

    def test_every_button_has_the_btn_class(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                for tag, attrs in parser.elements:
                    if is_button(tag, attrs):
                        self.assertTrue(has_class(attrs, "btn"), attrs)

    def test_actions_in_main_are_primary_and_deletes_are_error_buttons(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                wanted = "btn-error" if page.name in DELETE_PAGES else "btn-primary"
                for index, (tag, attrs) in enumerate(parser.elements):
                    if is_button(tag, attrs) and parser.inside(index, in_main):
                        self.assertTrue(has_class(attrs, wanted), attrs)


class TableWrapperTests(AllPagesMixin, TestCase):
    """Tables scroll inside their own box on a narrow screen, not the page."""

    def test_every_table_is_a_daisyui_table_in_a_scrollable_wrapper(self):
        tables = 0
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                for index, (tag, attrs) in enumerate(parser.elements):
                    if tag == "table":
                        tables += 1
                        self.assertTrue(has_class(attrs, "table"), attrs)
                        self.assertTrue(
                            parser.inside(
                                index, lambda t, a: has_class(a, "overflow-x-auto")
                            )
                        )
        # The dashboard has three (the fixture logs a tagged session).
        self.assertEqual(tables, 3)
