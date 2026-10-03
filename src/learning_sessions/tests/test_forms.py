from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from goals.models import Goal
from learning_sessions.forms import LearningSessionForm
from learning_sessions.models import LearningSession
from tags.models import Tag, TagManager


def failing_on_second_tag():
    """A get_or_create_by_name that creates the first tag, then fails."""
    real = TagManager.get_or_create_by_name
    calls = []

    def get_or_create_by_name(manager, name):
        calls.append(name)
        if len(calls) == 2:
            raise RuntimeError("database went away")
        return real(manager, name)

    return patch.object(TagManager, "get_or_create_by_name", get_or_create_by_name)


class LearningSessionFormAtomicTests(TestCase):
    def setUp(self):
        alice = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.data = {"date": "2026-03-01", "duration_minutes": "45", "tags": "Rust, Go"}

    def test_a_failing_tag_step_leaves_no_new_session_or_tags(self):
        form = LearningSessionForm(self.data, instance=LearningSession(goal=self.goal))
        self.assertTrue(form.is_valid(), form.errors)

        with failing_on_second_tag(), self.assertRaises(RuntimeError):
            form.save()

        self.assertFalse(LearningSession.objects.exists())
        self.assertFalse(Tag.objects.filter(name="Rust").exists())

    def test_a_failing_tag_step_leaves_an_edited_session_as_it_was(self):
        session = LearningSession.objects.create(goal=self.goal, duration_minutes=30)
        session.tags.set([Tag.objects.get_or_create_by_name("Python")[0]])
        form = LearningSessionForm(self.data, instance=session)
        self.assertTrue(form.is_valid(), form.errors)

        with failing_on_second_tag(), self.assertRaises(RuntimeError):
            form.save()

        session.refresh_from_db()
        self.assertEqual(session.duration_minutes, 30)
        self.assertEqual([t.name for t in session.tags.all()], ["Python"])
        self.assertFalse(Tag.objects.filter(name="Rust").exists())
