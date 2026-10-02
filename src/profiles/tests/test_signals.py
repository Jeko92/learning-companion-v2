from django.contrib.auth import get_user_model
from django.test import TestCase

from profiles.models import Profile

USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"


class ProfileAutoCreationTests(TestCase):
    def assert_has_one_empty_profile(self, user):
        profiles = Profile.objects.filter(user=user)
        self.assertEqual(profiles.count(), 1)
        profile = profiles.get()
        self.assertEqual((profile.name, profile.cohort), ("", ""))
        self.assertFalse(profile.focus_areas.exists())

    def test_every_new_user_gets_one_empty_profile(self):
        User = get_user_model()

        def sign_up(username):
            self.client.post(
                "/accounts/signup/",
                {"username": username, "password1": PASSWORD, "password2": PASSWORD},
            )
            return User.objects.get(username=username)

        creators = {
            "create_user": lambda name: User.objects.create_user(
                name, password=PASSWORD
            ),
            "create_superuser": lambda name: User.objects.create_superuser(
                name, password=PASSWORD
            ),
            "sign-up": sign_up,
        }
        for path, create in creators.items():
            with self.subTest(path=path):
                user = create(f"{USERNAME}-{path}")

                self.assert_has_one_empty_profile(user)
