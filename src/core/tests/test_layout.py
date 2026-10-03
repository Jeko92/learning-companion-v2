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
