from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase

from goals.models import Goal
from learning_sessions.models import LearningSession


class LearningSessionGoalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice")
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.mine = [
            LearningSession.objects.create(goal=self.goal, duration_minutes=30)
            for _ in range(2)
        ]
        bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="B"
        )
        self.theirs = LearningSession.objects.create(
            goal=bobs_goal, duration_minutes=30
        )

    def test_a_session_belongs_to_one_goal(self):
        goal = LearningSession._meta.get_field("goal")

        self.assertIsInstance(goal, models.ForeignKey)
        self.assertIs(goal.related_model, Goal)
        self.assertIs(goal.null, False)
        self.assertIs(goal.remote_field.on_delete, models.CASCADE)
        self.assertEqual(goal.remote_field.related_name, "sessions")
        self.assertCountEqual(self.goal.sessions.all(), self.mine)

    def test_deleting_a_goal_deletes_its_sessions(self):
        self.goal.delete()

        self.assertFalse(
            LearningSession.objects.filter(pk__in=[s.pk for s in self.mine])
        )
        self.assertTrue(LearningSession.objects.filter(pk=self.theirs.pk))

    def test_deleting_a_user_deletes_their_sessions(self):
        self.alice.delete()

        self.assertFalse(
            LearningSession.objects.filter(pk__in=[s.pk for s in self.mine])
        )
        self.assertTrue(LearningSession.objects.filter(pk=self.theirs.pk))


class LearningSessionDurationTests(TestCase):
    def setUp(self):
        self.assertIn(
            "duration_minutes", {f.name for f in LearningSession._meta.get_fields()}
        )
        owner = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=owner, title="Learn Django")

    def test_duration_is_whole_minutes(self):
        self.assertIsInstance(
            LearningSession._meta.get_field("duration_minutes"),
            models.PositiveIntegerField,
        )

    def test_duration_is_from_1_to_1440_minutes(self):
        for minutes in (1, 1440):
            with self.subTest(minutes=minutes):
                LearningSession(goal=self.goal, duration_minutes=minutes).full_clean()

        for minutes in (0, 1441, None):
            with self.subTest(minutes=minutes):
                session = LearningSession(goal=self.goal, duration_minutes=minutes)
                with self.assertRaises(ValidationError) as caught:
                    session.full_clean()
                self.assertIn("duration_minutes", caught.exception.error_dict)

    def test_the_database_rejects_a_duration_outside_1_to_1440(self):
        session = LearningSession.objects.create(goal=self.goal, duration_minutes=30)
        sessions = LearningSession.objects.filter(pk=session.pk)

        for minutes in (0, 1441):
            with (
                self.subTest(minutes=minutes),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                sessions.update(duration_minutes=minutes)

        for minutes in (1, 1440):
            with self.subTest(minutes=minutes):
                sessions.update(duration_minutes=minutes)
                session.refresh_from_db()
                self.assertEqual(session.duration_minutes, minutes)
