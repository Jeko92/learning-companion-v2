from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser, has_class
from core.tests.pages import AllPagesMixin
from goals.models import Goal

FORM_PAGES = {
    "log in",
    "sign up",
    "profile edit",
    "goal create",
    "goal edit",
    "goal detail",  # the inline attach-resource form
    "session create",
    "session edit",
    "resource create",
}
DAISY_FIELD_CLASSES = {"input", "select", "textarea", "checkbox", "radio"}


def in_main(tag, attrs):
    return tag == "main"


def in_fieldset(tag, attrs):
    return has_class(attrs, "fieldset")


def controls(parser):
    """(index in parser.elements, tag, attrs) of every visible form control
    inside <main>."""
    found = []
    for index, (tag, attrs) in enumerate(parser.elements):
        if tag not in ("input", "select", "textarea"):
            continue
        if attrs.get("type") in ("hidden", "submit", "button"):
            continue
        if parser.inside(index, in_main):
            found.append((index, tag, attrs))
    return found


def expected_class(tag, attrs):
    if tag == "input":
        kind = attrs.get("type")
        return kind if kind in ("checkbox", "radio") else "input"
    return tag


class StyledFormRenderingTests(AllPagesMixin, TestCase):
    """Every form outside the admin renders through the project's form
    templates: daisyUI controls, each with its own label."""

    def form_pages(self):
        pages = [(p, parser) for p, parser in self.walk() if p.name in FORM_PAGES]
        self.assertEqual({p.name for p, _ in pages}, FORM_PAGES)
        return pages

    def test_every_control_has_its_daisyui_class(self):
        for page, parser in self.form_pages():
            with self.subTest(page=page.name):
                found = controls(parser)
                self.assertTrue(found)
                for _, tag, attrs in found:
                    self.assertTrue(
                        has_class(attrs, expected_class(tag, attrs)),
                        (attrs.get("name"), attrs.get("class")),
                    )

    def test_every_control_has_a_label_for_its_id(self):
        for page, parser in self.form_pages():
            with self.subTest(page=page.name):
                label_targets = {
                    a.get("for") for t, a in parser.elements if t == "label"
                }
                for _, _, attrs in controls(parser):
                    self.assertIn(attrs.get("id"), label_targets, attrs.get("name"))

    def test_every_field_sits_in_a_daisyui_fieldset(self):
        for page, parser in self.form_pages():
            with self.subTest(page=page.name):
                for index, _, attrs in controls(parser):
                    self.assertTrue(parser.inside(index, in_fieldset), attrs)

    def test_help_text_stays_linked_to_its_field(self):
        cases = (("sign up", "id_password1"), ("session create", "id_tags"))
        parsed = {p.name: parser for p, parser in self.walk()}
        for page, control_id in cases:
            with self.subTest(page=page):
                elements = parsed[page].elements
                (control,) = [a for _, a in elements if a.get("id") == control_id]
                helptext_id = f"{control_id}_helptext"
                self.assertIn(helptext_id, control["aria-describedby"].split())
                self.assertIn(helptext_id, [a.get("id") for _, a in elements])


class AdminFormsUnchangedTests(TestCase):
    """The admin keeps Django's own form rendering."""

    def setUp(self):
        admin = get_user_model().objects.create_superuser("admin", password="x")
        self.goal = Goal.objects.create(owner=admin, title="Learn Django")
        self.client.force_login(admin)

    def test_admin_goal_pages_use_no_project_form_markup(self):
        paths = (
            reverse("admin:goals_goal_add"),
            reverse("admin:goals_goal_change", args=[self.goal.pk]),
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                parser = PageParser()
                parser.feed(response.content.decode())
                for tag, attrs in parser.elements:
                    classes = set(attrs.get("class", "").split())
                    self.assertFalse(classes & {"fieldset", "fieldset-legend"})
                    if tag in ("input", "select", "textarea"):
                        self.assertFalse(classes & DAISY_FIELD_CLASSES, attrs)
