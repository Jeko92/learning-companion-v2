from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

from goals.models import Goal


class GoalFieldTests(TestCase):
    def test_goal_has_the_agreed_fields(self):
        field = Goal._meta.get_field

        owner = field("owner")
        self.assertIsInstance(owner, models.ForeignKey)
        self.assertIs(owner.related_model, get_user_model())
        self.assertIs(owner.remote_field.on_delete, models.CASCADE)
        self.assertEqual(owner.remote_field.related_name, "goals")
        self.assertEqual(field("title").max_length, 200)
        self.assertIsInstance(field("description"), models.TextField)
        self.assertIs(field("description").blank, True)
        self.assertIsInstance(field("status"), models.CharField)
        self.assertEqual(field("status").max_length, 20)
        self.assertIs(field("created_at").auto_now_add, True)
        self.assertIs(field("updated_at").auto_now, True)

    def test_description_is_optional(self):
        owner = get_user_model().objects.create_user("alice")

        Goal(owner=owner, title="Learn Django", description="").full_clean()
