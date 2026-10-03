from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import Client, TestCase
from django.urls import reverse

from core.tests.html import PageParser
from profiles.models import Profile
from tags.models import Tag

USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


def login_redirect(path):
    return f"{resolve_url(settings.LOGIN_URL)}?next={path}"


class ProfileDetailTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.profile = self.alice.profile
        self.client.force_login(self.alice)

    def test_your_own_profile_page_is_served(self):
        path = f"/profile/{self.profile.pk}/"

        response = self.client.get(path)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profiles/profile_detail.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(reverse("profiles:detail", args=[self.profile.pk]), path)

    def test_shows_the_profile_values_or_placeholders(self):
        path = f"/profile/{self.profile.pk}/"
        with self.subTest(case="empty"):
            main = get_page(self.client, path).text("main")

            self.assertEqual(main.count("Not set"), 2)
            self.assertIn("No focus areas yet.", main)

        with self.subTest(case="filled"):
            self.profile.name = "Alice Smith"
            self.profile.cohort = "Spring 2026"
            self.profile.save()
            for name in ("Python", "Django"):
                self.profile.focus_areas.add(Tag.objects.get_or_create_by_name(name)[0])

            main = get_page(self.client, path).text("main")

            for value in ("Alice Smith", "Spring 2026", "Django", "Python"):
                self.assertIn(value, main)
            self.assertLess(main.index("Django"), main.index("Python"))
            self.assertNotIn("Not set", main)
            self.assertNotIn("No focus areas yet.", main)

    def test_anonymous_visitors_are_sent_to_log_in(self):
        self.client.logout()
        path = f"/profile/{self.profile.pk}/"

        response = self.client.get(path)

        self.assertRedirects(
            response, login_redirect(path), fetch_redirect_response=False
        )

    def test_another_users_profile_or_a_missing_one_is_not_found(self):
        self.profile.name = "Alice Smith"
        self.profile.cohort = "Spring 2026"
        self.profile.save()
        bob = get_user_model().objects.create_user("bob", password=PASSWORD)
        self.client.force_login(bob)

        response = self.client.get(f"/profile/{self.profile.pk}/")
        missing = self.client.get("/profile/999999/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        # Identical to a missing profile, so nothing about alice's leaks.
        self.assertEqual(response.content, missing.content)


class MyProfileTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def test_sends_you_to_your_own_profile(self):
        self.client.force_login(self.alice)

        response = self.client.get("/profile/")

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"/profile/{self.alice.profile.pk}/",
            fetch_redirect_response=False,
        )
        self.assertEqual(reverse("profiles:mine"), "/profile/")

    def test_creates_a_missing_profile_first(self):
        # loaddata saves users with raw=True, so the signal makes no profile.
        fixture_user = get_user_model()(username="fixture")
        fixture_user.save_base(raw=True)
        self.assertFalse(Profile.objects.filter(user=fixture_user).exists())
        self.client.force_login(fixture_user)

        response = self.client.get("/profile/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Profile.objects.filter(user=fixture_user).count(), 1)
        profile = Profile.objects.get(user=fixture_user)
        self.assertRedirects(
            response, f"/profile/{profile.pk}/", fetch_redirect_response=False
        )

    def test_anonymous_visitors_are_sent_to_log_in(self):
        response = self.client.get("/profile/")

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, login_redirect("/profile/"), fetch_redirect_response=False
        )


class ProfileEditTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.profile = self.alice.profile
        self.profile.name = "Alice"
        self.profile.save()
        for name in ("Python", "Django"):
            self.profile.focus_areas.add(Tag.objects.get_or_create_by_name(name)[0])
        self.path = f"/profile/{self.profile.pk}/edit/"
        self.client.force_login(self.alice)

    def test_edit_page_renders_your_profile_in_a_form(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profiles/profile_form.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(reverse("profiles:edit", args=[self.profile.pk]), self.path)
        page = PageParser()
        page.feed(response.content.decode())
        ((attrs, inputs),) = page.forms("main")
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), self.path)
        values = {a.get("name"): a.get("value") for a in inputs}
        self.assertIn("csrfmiddlewaretoken", values)
        self.assertEqual(values["name"], "Alice")
        self.assertIn("cohort", values)
        self.assertEqual(values["focus_areas"], "Django, Python")

    def test_detail_page_links_to_the_edit_page(self):
        page = get_page(self.client, f"/profile/{self.profile.pk}/")

        self.assertIn((self.path, "Edit profile"), page.links("main"))

    def test_anonymous_visitors_are_sent_to_log_in_and_nothing_is_saved(self):
        self.client.logout()
        for method in ("get", "post"):
            with self.subTest(method=method):
                # Only the POST carries data; on a GET it would land in `next`.
                data = {"name": "hacked"} if method == "post" else None
                response = getattr(self.client, method)(self.path, data)

                self.assertRedirects(
                    response, login_redirect(self.path), fetch_redirect_response=False
                )
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.name, "Alice")

    def test_another_user_cannot_see_or_change_your_profile(self):
        bob = get_user_model().objects.create_user("bob", password=PASSWORD)
        self.client.force_login(bob)
        for method in ("get", "post"):
            with self.subTest(method=method):
                # Only the POST carries data; on a GET it would land in `next`.
                data = {"name": "hacked"} if method == "post" else None
                response = getattr(self.client, method)(self.path, data)
                missing = getattr(self.client, method)("/profile/999999/edit/", data)

                self.assertEqual(response.status_code, 404)
                # Identical to a missing profile, so nothing about alice's leaks.
                self.assertEqual(response.content, missing.content)
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.name, "Alice")

    def test_a_valid_save_stores_trimmed_values_and_redirects(self):
        data = {"name": "  Alice Smith ", "cohort": " Spring 2026 ", "focus_areas": ""}

        response = self.client.post(self.path, data)

        detail = f"/profile/{self.profile.pk}/"
        self.assertRedirects(response, detail, fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertEqual(
            (self.profile.name, self.profile.cohort), ("Alice Smith", "Spring 2026")
        )
        self.assertContains(self.client.get(detail), "Profile saved.")

    def test_invalid_input_rerenders_the_form_and_saves_nothing(self):
        long_tag = "x" * 51
        cases = (
            ("blank name", {"name": ""}, "name", "This field is required."),
            ("whitespace name", {"name": "   "}, "name", "This field is required."),
            (
                "long name",
                {"name": "n" * 101},
                "name",
                "Ensure this value has at most 100 characters (it has 101).",
            ),
            (
                "long cohort",
                {"cohort": "c" * 51},
                "cohort",
                "Ensure this value has at most 50 characters (it has 51).",
            ),
            (
                "long focus area",
                {"focus_areas": f"Valid, {long_tag}"},
                "focus_areas",
                f"“{long_tag}”: Ensure this value has at most 50 characters (it has 51).",
            ),
        )
        tag_count = Tag.objects.count()
        for case, changes, field, message in cases:
            with self.subTest(case=case):
                data = {"name": "Changed", "cohort": "Changed", "focus_areas": ""}
                data.update(changes)

                response = self.client.post(self.path, data)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "profiles/profile_form.html")
                self.assertFormError(response.context["form"], field, message)
                page = PageParser()
                page.feed(response.content.decode())
                self.assertIn(message, page.text("main"))
                self.profile.refresh_from_db()
                self.assertEqual(
                    (self.profile.name, self.profile.cohort), ("Alice", "")
                )
                self.assertEqual(
                    [t.name for t in self.profile.focus_areas.all()],
                    ["Django", "Python"],
                )
                self.assertEqual(Tag.objects.count(), tag_count)


class ProfileEditCsrfTests(TestCase):
    # The default test client skips CSRF checks; this one enforces them.
    def setUp(self):
        self.alice = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.profile = self.alice.profile
        self.path = f"/profile/{self.profile.pk}/edit/"
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.alice)
        # GET first so the CSRF cookie is set: a 403 must come from the token.
        page = PageParser()
        page.feed(self.csrf_client.get(self.path).content.decode())
        ((_, inputs),) = page.forms("main")
        self.tokens = [
            a["value"] for a in inputs if a.get("name") == "csrfmiddlewaretoken"
        ]
        self.data = {"name": "Alice Smith", "cohort": "", "focus_areas": ""}

    def test_a_save_without_a_token_is_rejected(self):
        response = self.csrf_client.post(self.path, self.data)

        self.assertEqual(response.status_code, 403)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, "")

    def test_a_save_with_the_forms_token_succeeds(self):
        self.assertEqual(len(self.tokens), 1, "the edit form has no CSRF token")

        response = self.csrf_client.post(
            self.path, {**self.data, "csrfmiddlewaretoken": self.tokens[0]}
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, "Alice Smith")


class ProfilePrivacyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        python = Tag.objects.get_or_create_by_name("Python")[0]
        alice = User.objects.create_user(USERNAME, password=PASSWORD).profile
        alice.name, alice.cohort = "Alice Only", "Cohort A"
        alice.save()
        alice.focus_areas.add(python, Tag.objects.get_or_create_by_name("Haskell")[0])
        self.bob = User.objects.create_user("bob", password=PASSWORD)
        bob = self.bob.profile
        bob.name, bob.cohort = "Bob", "Cohort B"
        bob.save()
        bob.focus_areas.add(python)
        self.client.force_login(self.bob)

    def test_your_pages_never_show_other_users_data(self):
        pk = self.bob.profile.pk
        for page in ("detail", "edit"):
            with self.subTest(page=page):
                response = self.client.get(reverse(f"profiles:{page}", args=[pk]))

                self.assertEqual(response.status_code, 200)
                for value in ("Alice Only", "Cohort A", "Haskell"):
                    self.assertNotContains(response, value)

    def test_the_edit_form_offers_no_list_of_existing_tags(self):
        page = get_page(
            self.client, reverse("profiles:edit", args=[self.bob.profile.pk])
        )

        self.assertNotIn("select", [tag for tag, _ in page.elements])
        # Only the profile form: the layout's nav drawer toggle is a checkbox
        # too (ui-polish), and has nothing to do with the tags on offer.
        ((_, inputs),) = page.forms("main")
        self.assertFalse([a for a in inputs if a.get("type") == "checkbox"])


class ProfileEscapingTests(TestCase):
    PAYLOAD = "<script>alert(1)</script>"

    def setUp(self):
        alice = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.profile = alice.profile
        self.profile.name = self.profile.cohort = self.PAYLOAD
        self.profile.save()
        self.profile.focus_areas.add(Tag.objects.create(name=self.PAYLOAD))
        self.client.force_login(alice)

    def test_profile_values_are_shown_escaped(self):
        for page in ("detail", "edit"):
            with self.subTest(page=page):
                response = self.client.get(
                    reverse(f"profiles:{page}", args=[self.profile.pk])
                )

                self.assertNotContains(response, self.PAYLOAD)
                self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_a_rejected_entry_is_shown_escaped_in_the_error(self):
        response = self.client.post(
            reverse("profiles:edit", args=[self.profile.pk]),
            {"name": "Alice", "cohort": "", "focus_areas": f"{self.PAYLOAD}\u200b"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.PAYLOAD)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
