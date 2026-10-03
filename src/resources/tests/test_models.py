from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

from goals.models import Goal
from resources import models as resource_models


def make_resource(goal, **fields):
    return resource_models.Resource.objects.create(goal=goal, **fields)


class ResourceGoalTests(TestCase):
    def setUp(self):
        # Asserted first, so a missing model fails cleanly, not with an error.
        self.assertTrue(hasattr(resource_models, "Resource"))
        User = get_user_model()
        self.alice = User.objects.create_user("alice")
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        self.other_goal = Goal.objects.create(owner=self.alice, title="Learn Go")
        self.mine = [make_resource(self.goal) for _ in range(2)]
        self.other = make_resource(self.other_goal)
        bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="B"
        )
        self.theirs = make_resource(bobs_goal)

    def test_a_resource_belongs_to_one_goal(self):
        goal = resource_models.Resource._meta.get_field("goal")

        self.assertIsInstance(goal, models.ForeignKey)
        self.assertIs(goal.related_model, Goal)
        self.assertIs(goal.null, False)
        self.assertIs(goal.remote_field.on_delete, models.CASCADE)
        self.assertEqual(goal.remote_field.related_name, "resources")
        self.assertCountEqual(self.goal.resources.all(), self.mine)

    def test_deleting_a_goal_deletes_its_resources_only(self):
        self.goal.delete()

        Resource = resource_models.Resource
        self.assertFalse(Resource.objects.filter(pk__in=[r.pk for r in self.mine]))
        self.assertCountEqual(Resource.objects.all(), [self.other, self.theirs])

    def test_deleting_a_user_deletes_their_goals_resources_only(self):
        self.alice.delete()

        self.assertCountEqual(resource_models.Resource.objects.all(), [self.theirs])
