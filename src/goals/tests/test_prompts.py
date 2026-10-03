import importlib
import importlib.util

from django.contrib.auth import get_user_model
from django.test import TestCase

from goals.models import Goal
from learning_sessions.models import LearningSession
from resources.models import Resource
from tags.models import Tag


class PromptTestCase(TestCase):
    def setUp(self):
        # Asserted first, so a missing module fails cleanly, not with an error.
        self.assertIsNotNone(
            importlib.util.find_spec("goals.prompts"), "goals.prompts is missing"
        )
        self.prompts = importlib.import_module("goals.prompts")
        self.goal = Goal.objects.create(
            owner=get_user_model().objects.create_user("alice"),
            title="Learn Django",
            description="Parts 1-7 of the tutorial",
            status=Goal.Status.IN_PROGRESS,
        )

    def add_session(self, tags=(), **fields):
        fields = {"date": "2026-03-01", "duration_minutes": 60, **fields}
        session = LearningSession.objects.create(goal=self.goal, **fields)
        session.tags.set(Tag.objects.get_or_create_by_name(n)[0] for n in tags)
        return session

    def messages_from(self, build, sessions=(), total_minutes=0, resources=()):
        sessions = LearningSession.objects.filter(
            pk__in=[s.pk for s in sessions]
        ).with_tags()
        return build(self.goal, list(sessions), total_minutes, list(resources))


class SummaryMessagesTests(PromptTestCase):
    def messages(self, *args, **kwargs):
        return self.messages_from(self.prompts.summary_messages, *args, **kwargs)

    def test_the_system_prompt_asks_for_a_short_progress_summary(self):
        system, _ = self.messages()

        for asked in ("progress summary", "time spent", "covered", "next focus"):
            self.assertIn(asked, system)

    def test_the_goal_is_described(self):
        _, user = self.messages()

        self.assertIn("Goal: Learn Django", user)
        self.assertIn("Status: In progress", user)
        self.assertIn("Description: Parts 1-7 of the tutorial", user)

    def test_each_session_is_one_line_in_the_given_order(self):
        older = self.add_session(date="2026-03-01", duration_minutes=60)
        newer = self.add_session(
            date="2026-03-02",
            duration_minutes=45,
            tags=("forms", "Django"),
            notes="Read the\nforms docs.",
        )

        _, user = self.messages(sessions=[newer, older], total_minutes=105)

        newer_line = (
            "- 2026-03-02, 45 min, tags: Django, forms. Notes: Read the forms docs."
        )
        older_line = "- 2026-03-01, 1 h"
        self.assertIn(newer_line, user.splitlines())
        self.assertIn(older_line, user.splitlines())
        self.assertLess(user.index(newer_line), user.index(older_line))
        self.assertIn("Total time: 1 h 45 min", user)

    def test_each_resource_is_one_line_with_its_type_and_url(self):
        resource = Resource.objects.create(
            goal=self.goal,
            url="https://docs.djangoproject.com/",
            title="Django docs",
            type=Resource.Type.DOC,
        )

        _, user = self.messages(resources=[resource])

        self.assertIn(
            "- Django docs (Doc): https://docs.djangoproject.com/", user.splitlines()
        )

    def test_missing_parts_are_named_rather_than_left_blank(self):
        self.goal.description = ""

        _, user = self.messages()

        self.assertIn("Description: No description.", user)
        self.assertIn("No sessions.", user)
        self.assertIn("No resources.", user)
        self.assertIn("Total time: 0 min", user)


class NextStepsMessagesTests(PromptTestCase):
    def next_steps(self, *args, **kwargs):
        return self.messages_from(
            getattr(self.prompts, "next_steps_messages", None), *args, **kwargs
        )

    def summary(self, *args, **kwargs):
        return self.messages_from(self.prompts.summary_messages, *args, **kwargs)

    def test_the_system_prompt_asks_for_2_to_3_concrete_steps_as_json(self):
        self.assertTrue(hasattr(self.prompts, "next_steps_messages"))
        system, _ = self.next_steps()

        for asked in (
            "2 to 3",
            "concrete, actionable next learning steps",
            "build on what has been done",
            "resources already attached",
            "how to start",
            "JSON object",
            "`steps` list",
        ):
            self.assertIn(asked, system)

    def test_the_user_message_describes_the_goal_as_the_summary_does(self):
        self.assertTrue(hasattr(self.prompts, "next_steps_messages"))
        session = self.add_session(tags=("forms",), notes="Read the forms docs.")
        resource = Resource.objects.create(
            goal=self.goal, url="https://docs.djangoproject.com/", title="Docs"
        )
        cases = {
            "with sessions and resources": {
                "sessions": [session],
                "total_minutes": 60,
                "resources": [resource],
            },
            "an empty goal": {},
        }
        for case, data in cases.items():
            with self.subTest(case=case):
                _, user = self.next_steps(**data)

                self.assertEqual(user, self.summary(**data)[1])

        _, empty = self.next_steps()
        self.assertIn("No sessions.", empty.splitlines())
        self.assertIn("No resources.", empty.splitlines())

    def test_the_schema_asks_for_a_steps_list_of_strings_and_nothing_else(self):
        self.assertEqual(
            getattr(self.prompts, "NEXT_STEPS_SCHEMA", None),
            {
                "type": "object",
                "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
                "required": ["steps"],
                "additionalProperties": False,
            },
        )
