from django.contrib.auth import get_user_model
from django.forms.forms import NON_FIELD_ERRORS
from django.test import TestCase

from goals.models import Goal
from resources.forms import ResourceForm
from resources.models import Resource

DUPLICATE = "This goal already has this resource."


def form_for(goal, **changes):
    data = {"url": "https://example.com/guide", "title": "Guide", "type": "article"}
    return ResourceForm({**data, **changes}, instance=Resource(goal=goal))


class ResourceFormDuplicateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice")
        self.goal = Goal.objects.create(owner=self.alice, title="Learn Django")
        Resource.objects.create(
            goal=self.goal, url="https://example.com/guide", title="Guide"
        )

    def test_a_url_the_goal_already_has_is_rejected(self):
        for url in ("https://example.com/guide", "  https://example.com/guide  "):
            with self.subTest(url=url):
                form = form_for(self.goal, url=url)

                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors[NON_FIELD_ERRORS], [DUPLICATE])

    def test_the_same_url_on_another_goal_is_accepted(self):
        other = Goal.objects.create(owner=self.alice, title="Other")
        bobs = Goal.objects.create(
            owner=get_user_model().objects.create_user("bob"), title="B"
        )
        for goal in (other, bobs):
            with self.subTest(goal=goal.title):
                form = form_for(goal)

                self.assertTrue(form.is_valid(), form.errors)

    def test_another_url_on_the_same_goal_is_accepted(self):
        form = form_for(self.goal, url="https://example.com/other")

        self.assertTrue(form.is_valid(), form.errors)
