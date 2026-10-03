from datetime import UTC, date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase

from goals.models import Goal
from learning_sessions.models import LearningSession
from tags.models import Tag


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


# Late in the day, so a date taken from UTC is checked near midnight.
NOW = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)


class LearningSessionDateTests(TestCase):
    def setUp(self):
        self.assertIn("date", {f.name for f in LearningSession._meta.get_fields()})
        owner = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=owner, title="Learn Django")

    def test_date_defaults_to_today(self):
        self.assertIsInstance(LearningSession._meta.get_field("date"), models.DateField)
        with patch("django.utils.timezone.now", return_value=NOW):
            session = LearningSession.objects.create(
                goal=self.goal, duration_minutes=30
            )

        session.refresh_from_db()
        self.assertEqual(session.date, date(2026, 3, 10))

    def test_a_future_date_is_rejected(self):
        with patch("django.utils.timezone.now", return_value=NOW):
            for day in (date(2026, 3, 10), date(2025, 1, 1)):
                with self.subTest(day=day):
                    LearningSession(
                        goal=self.goal, date=day, duration_minutes=30
                    ).full_clean()

            tomorrow = LearningSession(
                goal=self.goal, date=date(2026, 3, 11), duration_minutes=30
            )
            with self.assertRaises(ValidationError) as caught:
                tomorrow.full_clean()

        self.assertIn("date", caught.exception.error_dict)


class LearningSessionNotesTests(TestCase):
    def setUp(self):
        self.assertIn("notes", {f.name for f in LearningSession._meta.get_fields()})
        owner = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=owner, title="Learn Django")

    def session(self, notes):
        return LearningSession(goal=self.goal, duration_minutes=30, notes=notes)

    def test_notes_are_optional_free_text(self):
        notes = LearningSession._meta.get_field("notes")

        self.assertIsInstance(notes, models.TextField)
        self.assertIs(notes.blank, True)
        self.session("").full_clean()

    def test_notes_are_capped_at_2000_characters(self):
        self.session("n" * 2000).full_clean()

        with self.assertRaises(ValidationError) as caught:
            self.session("n" * 2001).full_clean()

        self.assertIn("notes", caught.exception.error_dict)


class LearningSessionTagTests(TestCase):
    def setUp(self):
        self.assertIn("tags", {f.name for f in LearningSession._meta.get_fields()})

    def test_tags_are_shared_tags(self):
        tags = LearningSession._meta.get_field("tags")

        self.assertIsInstance(tags, models.ManyToManyField)
        self.assertIs(tags.related_model, Tag)
        self.assertIs(tags.blank, True)
        self.assertEqual(tags.remote_field.related_name, "sessions")

    def test_a_tag_is_shared_across_sessions_and_users(self):
        User = get_user_model()
        mine, theirs = (
            LearningSession.objects.create(
                goal=Goal.objects.create(
                    owner=User.objects.create_user(name), title="G"
                ),
                duration_minutes=30,
            )
            for name in ("alice", "bob")
        )
        python, django = (
            Tag.objects.create(name="python"),
            Tag.objects.create(name="django"),
        )

        mine.tags.add(python, django)
        theirs.tags.add(python)

        self.assertQuerySetEqual(mine.tags.all(), [django, python], ordered=False)
        self.assertQuerySetEqual(python.sessions.all(), [mine, theirs], ordered=False)

        python.delete()

        self.assertQuerySetEqual(mine.tags.all(), [django])
        self.assertTrue(LearningSession.objects.filter(pk=theirs.pk).exists())


class LearningSessionOrderingTests(TestCase):
    def setUp(self):
        fields = {f.name for f in LearningSession._meta.get_fields()}
        self.assertLessEqual({"created_at", "updated_at"}, fields)
        owner = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=owner, title="Learn Django")

    def session(self, day):
        return LearningSession.objects.create(
            goal=self.goal, date=day, duration_minutes=30
        )

    def test_timestamps_record_creation_and_the_last_change(self):
        later = datetime(2026, 3, 11, 8, 0, tzinfo=UTC)
        with patch("django.utils.timezone.now", return_value=NOW):
            session = self.session(date(2026, 3, 10))
        with patch("django.utils.timezone.now", return_value=later):
            session.save()

        session.refresh_from_db()
        self.assertEqual((session.created_at, session.updated_at), (NOW, later))

    def test_sessions_are_newest_first_by_date(self):
        older = self.session(date(2026, 3, 1))
        newer = self.session(date(2026, 3, 9))
        oldest = self.session(date(2026, 2, 1))

        self.assertEqual(list(LearningSession.objects.all()), [newer, older, oldest])

    def test_sessions_on_one_date_are_newest_recorded_first(self):
        day = date(2026, 3, 9)
        first, second, third = (self.session(day) for _ in range(3))
        earlier = datetime(2026, 3, 9, 8, 0, tzinfo=UTC)
        LearningSession.objects.filter(pk=second.pk).update(created_at=earlier)
        LearningSession.objects.filter(pk__in=[first.pk, third.pk]).update(
            created_at=NOW
        )

        # Same created_at: the id breaks the tie.
        self.assertEqual(list(LearningSession.objects.all()), [third, first, second])


class LearningSessionStrTests(TestCase):
    def test_str_names_the_goal_date_and_duration(self):
        owner = get_user_model().objects.create_user("alice")
        goal = Goal(owner=owner, title="Learn Django")
        session = LearningSession(
            goal=goal, date=date(2026, 3, 10), duration_minutes=45
        )

        self.assertEqual(str(session), "Learn Django · 2026-03-10 · 45 min")


class OwnedByTests(TestCase):
    def setUp(self):
        self.assertTrue(hasattr(LearningSession.objects, "owned_by"))
        User = get_user_model()
        self.alice, self.bob = (User.objects.create_user(n) for n in ("alice", "bob"))
        self.django, self.docker = (
            Goal.objects.create(owner=self.alice, title=t) for t in ("Django", "Docker")
        )
        bobs_goal = Goal.objects.create(owner=self.bob, title="Rust")
        self.alices = [
            LearningSession.objects.create(goal=goal, duration_minutes=30)
            for goal in (self.django, self.django, self.docker)
        ]
        self.bobs = [
            LearningSession.objects.create(goal=bobs_goal, duration_minutes=30)
            for _ in range(2)
        ]
        self.shared = Tag.objects.create(name="shared")
        self.alice_only = Tag.objects.create(name="alice-only")
        self.alices[0].tags.add(self.shared, self.alice_only)
        self.bobs[0].tags.add(self.shared)

    def test_owned_by_returns_only_that_users_sessions(self):
        owned_by = LearningSession.objects.owned_by

        self.assertEqual(set(owned_by(self.alice)), set(self.alices))
        self.assertEqual(set(owned_by(self.bob)), set(self.bobs))
        self.assertEqual(
            set(owned_by(self.alice).filter(goal=self.docker)), {self.alices[2]}
        )

    def test_tags_reached_through_owned_by_never_leak_another_users(self):
        bobs_sessions = LearningSession.objects.owned_by(self.bob)

        tags = Tag.objects.filter(sessions__in=bobs_sessions).distinct()

        self.assertQuerySetEqual(tags, [self.shared])


class AggregateTestCase(TestCase):
    """Alice and bob, each with one goal, and a helper to log sessions."""

    def setUp(self):
        User = get_user_model()
        self.alice, self.bob = (User.objects.create_user(n) for n in ("alice", "bob"))
        self.goals = {
            user: Goal.objects.create(owner=user, title="Learn")
            for user in (self.alice, self.bob)
        }

    def add_session(self, user, minutes, tags=(), day=date(2026, 9, 1)):
        session = LearningSession.objects.create(
            goal=self.goals[user], duration_minutes=minutes, date=day
        )
        session.tags.set(Tag.objects.get_or_create_by_name(n)[0] for n in tags)
        return session


class MinutesPerTagTests(AggregateTestCase):
    def test_totals_per_tag_largest_first_ties_by_name_ignoring_case(self):
        self.add_session(self.alice, 30, ["python"])
        self.add_session(self.alice, 45, ["python"])
        self.add_session(self.alice, 45, ["django"])
        # Several tags: the session counts in full under each of them.
        self.add_session(self.alice, 60, ["django", "python"])
        self.add_session(self.alice, 45, ["Zebra"])
        self.add_session(self.alice, 45, ["apple"])
        # Bob's time on a shared tag and his own tag never show up.
        self.add_session(self.bob, 500, ["python"])
        self.add_session(self.bob, 10, ["bob-only"])

        totals = LearningSession.objects.owned_by(self.alice).minutes_per_tag()

        self.assertEqual(
            totals,
            [("python", 135), ("django", 105), ("apple", 45), ("Zebra", 45)],
        )

    def test_untagged_time_comes_last_in_one_query_whatever_the_ordering(self):
        self.add_session(self.alice, 90, ["big"])
        self.add_session(self.alice, 20)
        self.add_session(self.alice, 25, day=date(2026, 9, 2))
        self.add_session(self.alice, 10, ["small"])
        self.add_session(self.bob, 500)

        # An explicit ordering on the incoming queryset must not split groups.
        sessions = LearningSession.objects.owned_by(self.alice).order_by("-date")
        with self.assertNumQueries(1):
            totals = sessions.minutes_per_tag()

        self.assertEqual(totals, [("big", 90), ("small", 10), (None, 45)])
