from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

LOGOUT_PATH = "/accounts/logout/"
USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


class LogoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.client.force_login(self.user)

    def test_post_logs_out_and_redirects_with_a_message(self):
        response = self.client.post(LOGOUT_PATH)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(reverse("accounts:logout"), LOGOUT_PATH)
        self.assertEqual(settings.LOGOUT_REDIRECT_URL, "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False
        )

    def test_landing_page_says_the_user_logged_out(self):
        response = self.client.post(LOGOUT_PATH, follow=True)

        self.assertContains(response, "You have been logged out.")

    def test_get_is_not_allowed_and_keeps_the_user_logged_in(self):
        response = self.client.get(LOGOUT_PATH)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
