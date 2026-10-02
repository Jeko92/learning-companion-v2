from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
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

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Alice Smith", status_code=404)
        self.assertNotContains(response, "Spring 2026", status_code=404)
        self.assertEqual(self.client.get("/profile/999999/").status_code, 404)


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
        self.client.force_login(fixture_user)

        response = self.client.get("/profile/")

        self.assertEqual(response.status_code, 302)
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

                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, "Alice", status_code=404)
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.name, "Alice")
