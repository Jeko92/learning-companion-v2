from itertools import pairwise

from django.test import TestCase

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
