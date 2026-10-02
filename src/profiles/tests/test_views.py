from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


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
