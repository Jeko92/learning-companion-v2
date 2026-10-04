from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser, has_class
from core.tests.pages import AllPagesMixin

USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


class NavTests(TestCase):
    def get_page(self):
        response = self.client.get("/")
        page = PageParser()
        page.feed(response.content.decode())
        return page

    def log_in(self):
        user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.client.force_login(user)

    def test_anonymous_nav_has_only_login_and_signup_links(self):
        # goal-list-create removed the "Goals" placeholder for anonymous
        # visitors (#2 AC4, #3 AC9 pinned it); it's a link once logged in.
        page = self.get_page()

        self.assertEqual(
            page.links("nav"),
            [
                (reverse("accounts:login"), "Log in"),
                (reverse("accounts:signup"), "Sign up"),
            ],
        )
        # Exact text guards against stray nav text. "No username for anonymous
        # visitors" holds by construction: AnonymousUser.get_username() is "".
        self.assertEqual(page.text("nav"), "Log in Sign up")

    def test_logged_in_nav_links_dashboard_goals_the_profile_and_has_logout(self):
        # profile-page made the username a link to /profile/ (#4 AC10 had no
        # links); goal-list-create made "Goals" a link to /goals/;
        # dashboard-status put "Dashboard" first.
        self.log_in()

        page = self.get_page()

        self.assertEqual(
            page.links("nav"),
            [
                (reverse("dashboard:index"), "Dashboard"),
                (reverse("goals:list"), "Goals"),
                (reverse("profiles:mine"), USERNAME),
            ],
        )
        # Exact text: Dashboard, Goals, the username and the Log out button,
        # nothing else. (#3 pinned "Goals <username>"; auth-login-logout adds
        # Log out.)
        self.assertEqual(page.text("nav"), f"Dashboard Goals {USERNAME} Log out")
        ((attrs, inputs),) = page.forms("nav")
        # Only method and action, so styling attributes can't break the test.
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), reverse("accounts:logout"))
        self.assertIn("csrfmiddlewaretoken", {a.get("name") for a in inputs})

    def test_logged_in_nav_shows_the_username(self):
        self.log_in()

        page = self.get_page()

        self.assertIn(USERNAME, page.text("nav"))


class NavCurrentPageTests(AllPagesMixin, TestCase):
    """The nav marks the section the page belongs to, for screen readers."""

    def expected_current(self, page):
        if not page.logged_in:
            return []
        if page.name == "dashboard":
            return [reverse("dashboard:index")]
        if page.name.startswith("profile"):
            return [reverse("profiles:mine")]
        # Goals, and the sessions and resources that belong to a goal.
        return [reverse("goals:list")]

    def test_only_the_current_sections_nav_link_has_aria_current(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                current = [
                    attrs["href"]
                    for tag, attrs in parser.elements
                    if tag == "a" and attrs.get("aria-current") == "page"
                ]
                self.assertEqual(current, self.expected_current(page))


def in_drawer_side(tag, attrs):
    return has_class(attrs, "drawer-side")


class NavDrawerTests(AllPagesMixin, TestCase):
    """Below md the nav is a slide-in drawer, from md up a sidebar: one nav,
    rendered once, toggled by a focusable checkbox."""

    def test_the_drawer_toggle_is_an_unnamed_checkbox_called_menu(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                (toggle,) = [
                    a for t, a in parser.elements if has_class(a, "drawer-toggle")
                ]
                self.assertEqual(toggle.get("type"), "checkbox")
                self.assertEqual(toggle.get("id"), "nav-drawer")
                self.assertEqual(toggle.get("aria-label"), "Menu")
                # Not a form field: nothing to submit.
                self.assertNotIn("name", toggle)

    def test_the_drawer_opens_from_md_up_as_a_sidebar(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                drawers = [a for t, a in parser.elements if has_class(a, "drawer")]
                self.assertEqual(len(drawers), 1)
                self.assertTrue(has_class(drawers[0], "md:drawer-open"))

    def test_the_drawer_side_comes_between_the_toggle_and_the_page_content(self):
        # Opening the drawer with Space puts its links next in the Tab order,
        # not after everything on the page it covers.
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                order = [
                    name
                    for _, attrs in parser.elements
                    for name in ("drawer-toggle", "drawer-side", "drawer-content")
                    if has_class(attrs, name)
                ]
                self.assertEqual(
                    order, ["drawer-toggle", "drawer-side", "drawer-content"]
                )

    def test_the_header_has_a_menu_button_for_the_toggle(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                buttons = [
                    a
                    for i, (t, a) in enumerate(parser.elements)
                    if t == "label"
                    and a.get("for") == "nav-drawer"
                    and has_class(a, "drawer-button")
                    and parser.inside(i, lambda tag, _: tag == "header")
                ]
                self.assertEqual(len(buttons), 1)

    def test_the_one_main_nav_sits_in_the_drawer_side(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                navs = [
                    i
                    for i, (t, a) in enumerate(parser.elements)
                    if t == "nav" and a.get("aria-label") == "Main"
                ]
                self.assertEqual(len(navs), 1)
                self.assertTrue(parser.inside(navs[0], in_drawer_side))

    def test_the_header_links_only_to_the_home_page(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                self.assertEqual(
                    [href for href, _ in parser.links("header")], [reverse("home")]
                )

    def test_log_out_is_a_post_form_inside_the_drawer_nav(self):
        self.client.force_login(self.alice)
        parser = PageParser()
        parser.feed(self.client.get(reverse("dashboard:index")).content.decode())

        (index,) = [
            i
            for i, (t, a) in enumerate(parser.elements)
            if t == "form" and a.get("action") == reverse("accounts:logout")
        ]
        self.assertEqual(parser.elements[index][1].get("method"), "post")
        self.assertTrue(parser.inside(index, lambda t, _: t == "nav"))
        self.assertTrue(parser.inside(index, in_drawer_side))
