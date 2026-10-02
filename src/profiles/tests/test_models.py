from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

from profiles.models import Profile
from tags.models import Tag


class ProfileFieldTests(TestCase):
    def test_profile_has_the_agreed_fields(self):
        user = Profile._meta.get_field("user")
        name = Profile._meta.get_field("name")
        cohort = Profile._meta.get_field("cohort")
        focus_areas = Profile._meta.get_field("focus_areas")

        self.assertIsInstance(user, models.OneToOneField)
        self.assertIs(user.related_model, get_user_model())
        self.assertIs(user.remote_field.on_delete, models.CASCADE)
        self.assertEqual(user.remote_field.related_name, "profile")
        self.assertEqual((name.max_length, name.blank), (100, True))
        self.assertEqual((cohort.max_length, cohort.blank), (50, True))
        self.assertIsInstance(focus_areas, models.ManyToManyField)
        self.assertIs(focus_areas.related_model, Tag)
        self.assertIs(focus_areas.blank, True)
        self.assertEqual(focus_areas.remote_field.related_name, "profiles")


class ProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("alice")
        self.profile = self.user.profile

    def test_deleting_the_user_deletes_the_profile(self):
        self.user.delete()

        self.assertFalse(Profile.objects.filter(pk=self.profile.pk).exists())

    def test_shows_the_name_or_else_the_username(self):
        for name, expected in (("", "alice"), ("Alice Smith", "Alice Smith")):
            with self.subTest(name=name):
                self.profile.name = name

                self.assertEqual(str(self.profile), expected)
