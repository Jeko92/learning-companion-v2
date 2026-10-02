from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
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


class GoalStatusTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("alice")

    def test_status_is_planned_in_progress_or_done(self):
        self.assertTrue(hasattr(Goal, "Status"))
        self.assertEqual(Goal.Status.values, ["planned", "in-progress", "done"])
        self.assertEqual(Goal.Status.labels, ["Planned", "In progress", "Done"])
        self.assertEqual(Goal(owner=self.owner, title="x").status, Goal.Status.PLANNED)

    def test_any_other_status_is_rejected(self):
        goal = Goal.objects.create(owner=self.owner, title="Learn Django")
        goal.status = "bogus"

        with self.assertRaises(ValidationError) as caught:
            goal.full_clean()
        self.assertIn(
            "Value 'bogus' is not a valid choice.",
            caught.exception.error_dict["status"][0],
        )
        # The database enforces it too, so update() can't bypass the choices.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Goal.objects.filter(pk=goal.pk).update(status="bogus")

    def test_every_status_value_passes_the_database_constraint(self):
        # Meta can't see the nested Status, so the constraint lists the values
        # itself; this keeps the two in step.
        goal = Goal.objects.create(owner=self.owner, title="Learn Django")
        for value in Goal.Status.values:
            with self.subTest(value=value):
                Goal.objects.filter(pk=goal.pk).update(status=value)

                goal.refresh_from_db()
                self.assertEqual(goal.status, value)
