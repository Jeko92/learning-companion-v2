from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser
from profiles.models import Profile

PASSWORD = "Tr4ck-Learning!"


class UserAdminProfileInlineTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser("admin", password=PASSWORD)
        )
        self.alice = User.objects.create_user("alice", password=PASSWORD)

    def field_names(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        page = PageParser()
        page.feed(response.content.decode())
        return {
            attrs.get("name")
            for tag, attrs in page.elements
            if tag in ("input", "select")
        }

    def test_user_change_page_shows_the_profile_inline(self):
        names = self.field_names(
            reverse("admin:accounts_user_change", args=[self.alice.pk])
        )

        self.assertLessEqual(
            {"profile-0-name", "profile-0-cohort", "profile-0-focus_areas"}, names
        )
        self.assertIsInstance(
            admin.site._registry[get_user_model()], auth_admin.UserAdmin
        )

    def test_focus_areas_are_picked_with_the_tag_autocomplete(self):
        response = self.client.get(
            reverse("admin:accounts_user_change", args=[self.alice.pk])
        )
        page = PageParser()
        page.feed(response.content.decode())

        (select,) = [
            attrs
            for tag, attrs in page.elements
            if tag == "select" and attrs.get("name") == "profile-0-focus_areas"
        ]
        self.assertIn("admin-autocomplete", select.get("class", "").split())
        # The widget names the field it serves; the server resolves Tag from it.
        self.assertEqual(
            (select.get("data-model-name"), select.get("data-field-name")),
            ("profile", "focus_areas"),
        )

    def test_adding_a_user_in_the_admin_creates_exactly_one_profile(self):
        # The inline is hidden on the add page: a filled-in inline would save a
        # second profile next to the one the post_save signal creates.
        add_path = reverse("admin:accounts_user_add")
        self.assertNotIn("profile-TOTAL_FORMS", self.field_names(add_path))

        response = self.client.post(
            add_path,
            {
                "username": "bob",
                "usable_password": "true",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        # A rejected form re-renders with 200; a saved user redirects.
        self.assertEqual(response.status_code, 302)
        bob = get_user_model().objects.get(username="bob")
        self.assertEqual(Profile.objects.filter(user=bob).count(), 1)
