from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.html import PageParser
from tags.models import Tag

USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


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
