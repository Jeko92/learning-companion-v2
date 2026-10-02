from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

from goals.models import Goal
from learning_sessions.models import LearningSession


class LearningSessionGoalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice")
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.mine = [LearningSession.objects.create(goal=self.goal) for _ in range(2)]
        bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="B"
        )
        self.theirs = LearningSession.objects.create(goal=bobs_goal)

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
