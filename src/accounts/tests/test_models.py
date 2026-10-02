from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.management import call_command
from django.test import TestCase


class UserModelTests(TestCase):
    def test_project_uses_the_custom_user_model(self):
        User = get_user_model()

        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertEqual(User._meta.label, "accounts.User")
        self.assertTrue(issubclass(User, AbstractUser))

    def test_custom_user_model_adds_no_fields(self):
        # Profile data goes into a Profile model, not onto the user.
        User = get_user_model()

        self.assertEqual(
            {f.name for f in User._meta.fields},
            {f.name for f in AbstractUser._meta.fields} | {"id"},
        )


class MigrationsTests(TestCase):
    def test_no_model_change_is_missing_a_migration(self):
        # makemigrations --check exits with status 1 when a migration is missing.
        try:
            call_command("makemigrations", "--check", "--dry-run", verbosity=0)
        except SystemExit:
            self.fail("A model change has no migration; run makemigrations.")
