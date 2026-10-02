from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
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
        # Profile data goes into a Profile model, not onto the user. _meta.fields
        # leaves out many-to-many fields, so compare those too.
        def field_names(model):
            return {f.name for f in model._meta.fields + model._meta.many_to_many}

        self.assertEqual(
            field_names(get_user_model()), field_names(AbstractUser) | {"id"}
        )


class UserAdminTests(TestCase):
    def test_user_model_is_registered_with_user_admin(self):
        model_admin = admin.site._registry.get(get_user_model())

        self.assertIsInstance(model_admin, UserAdmin)


class MigrationsTests(TestCase):
    def test_no_model_change_is_missing_a_migration(self):
        # makemigrations --check exits with status 1 when a migration is missing.
        try:
            call_command("makemigrations", "--check", "--dry-run", verbosity=0)
        except SystemExit:
            self.fail("A model change has no migration; run makemigrations.")
