from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser

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
