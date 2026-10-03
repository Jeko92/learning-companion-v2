from datetime import UTC, datetime
from unittest.mock import patch

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


class GoalTitleTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("alice")

    def test_title_is_stored_trimmed(self):
        goal = Goal.objects.create(owner=self.owner, title="  Learn Django ")

        goal.refresh_from_db()
        self.assertEqual(goal.title, "Learn Django")

    def test_title_is_required_and_at_most_200_characters(self):
        for title in ("", "   ", "x" * 201):
            with self.subTest(title=title[:5]):
                with self.assertRaises(ValidationError) as caught:
                    Goal(owner=self.owner, title=title).full_clean()

                self.assertIn("title", caught.exception.error_dict)
        Goal(owner=self.owner, title="x" * 200).full_clean()


class GoalTimestampTests(TestCase):
    def test_created_at_is_set_once_and_updated_at_on_every_save(self):
        owner = get_user_model().objects.create_user("alice")
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)

        with patch("django.utils.timezone.now", return_value=t1):
            goal = Goal.objects.create(owner=owner, title="Learn Django")
        self.assertEqual((goal.created_at, goal.updated_at), (t1, t1))

        with patch("django.utils.timezone.now", return_value=t2):
            goal.title = "Learn Django well"
            goal.save()
        goal.refresh_from_db()
        self.assertEqual((goal.created_at, goal.updated_at), (t1, t2))


class GoalOrderingTests(TestCase):
    def test_goals_are_newest_first_with_ties_broken_by_id(self):
        owner = get_user_model().objects.create_user("alice")
        a, b, c = (Goal.objects.create(owner=owner, title=t) for t in "abc")
        older = datetime(2026, 1, 1, tzinfo=UTC)
        newer = datetime(2026, 1, 2, tzinfo=UTC)
        Goal.objects.filter(pk=a.pk).update(created_at=older)
        Goal.objects.filter(pk__in=[b.pk, c.pk]).update(created_at=newer)

        self.assertEqual(list(Goal.objects.all()), [c, b, a])


class GoalStrTests(TestCase):
    def test_shows_its_title(self):
        owner = get_user_model().objects.create_user("bob")

        self.assertEqual(str(Goal(owner=owner, title="Learn Django")), "Learn Django")


class GoalOwnershipTests(TestCase):
    def test_goals_belong_to_their_owner_and_go_with_them(self):
        User = get_user_model()
        alice, bob = User.objects.create_user("alice"), User.objects.create_user("bob")
        mine = [Goal.objects.create(owner=alice, title=t) for t in ("A1", "A2")]
        theirs = Goal.objects.create(owner=bob, title="B1")

        self.assertCountEqual(alice.goals.all(), mine)

        alice.delete()

        self.assertFalse(Goal.objects.filter(pk__in=[g.pk for g in mine]).exists())
        self.assertTrue(Goal.objects.filter(pk=theirs.pk).exists())


class OwnedByTests(TestCase):
    def test_owned_by_returns_only_that_users_goals_newest_first(self):
        self.assertTrue(hasattr(Goal.objects, "owned_by"))
        User = get_user_model()
        alice, bob = User.objects.create_user("alice"), User.objects.create_user("bob")
        older = Goal.objects.create(owner=alice, title="Older")
        newer = Goal.objects.create(owner=alice, title="Newer", status=Goal.Status.DONE)
        Goal.objects.create(owner=bob, title="Bob's")
        Goal.objects.filter(pk=older.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=UTC)
        )

        self.assertEqual(list(Goal.objects.owned_by(alice)), [newer, older])
        self.assertEqual(
            list(Goal.objects.owned_by(alice).filter(status=Goal.Status.DONE)), [newer]
        )


class GoalStatusCountsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")

    def add_goals(self, *statuses):
        # Distinct created_at values, so ordering by it could split a group.
        for day, status in enumerate(statuses, start=1):
            goal = Goal.objects.create(owner=self.alice, title="Mine", status=status)
            Goal.objects.filter(pk=goal.pk).update(
                created_at=datetime(2026, 1, day, tzinfo=UTC)
            )

    def test_counts_every_status_in_choice_order_with_zeros(self):
        self.add_goals(Goal.Status.PLANNED, Goal.Status.DONE, Goal.Status.PLANNED)
        for status in Goal.Status.values:
            Goal.objects.create(owner=self.bob, title="Bob's", status=status)

        counts = Goal.objects.owned_by(self.alice).status_counts()

        self.assertEqual(
            list(counts.items()), [("planned", 2), ("in-progress", 0), ("done", 1)]
        )

    def test_an_explicit_ordering_does_not_split_the_counts(self):
        # Meta.ordering stays out of GROUP BY, but an explicit order_by() on the
        # incoming queryset would add its columns; status_counts() clears it.
        self.add_goals(Goal.Status.PLANNED, Goal.Status.PLANNED, Goal.Status.DONE)

        counts = Goal.objects.owned_by(self.alice).order_by("-created_at")
        counts = counts.status_counts()

        self.assertEqual(counts, {"planned": 2, "in-progress": 0, "done": 1})

    def test_a_user_without_goals_gets_zero_for_every_status_in_one_query(self):
        Goal.objects.create(owner=self.bob, title="Bob's")

        with self.assertNumQueries(1):
            counts = Goal.objects.owned_by(self.alice).status_counts()

        self.assertEqual(counts, {"planned": 0, "in-progress": 0, "done": 0})


class GoalUrlTests(TestCase):
    def test_a_goal_knows_its_detail_url(self):
        self.assertTrue(hasattr(Goal, "get_absolute_url"))
        goal = Goal.objects.create(
            owner=get_user_model().objects.create_user("alice"), title="Learn Django"
        )

        self.assertEqual(goal.get_absolute_url(), f"/goals/{goal.pk}/")


class GoalSummaryFieldTests(TestCase):
    def setUp(self):
        self.goal = Goal.objects.create(
            owner=get_user_model().objects.create_user("alice"), title="Learn Django"
        )

    def test_a_new_goal_has_no_summary(self):
        self.goal.refresh_from_db()

        self.assertEqual(getattr(self.goal, "summary", None), "")
        self.assertIsNone(getattr(self.goal, "summary_generated_at", "missing"))

    def test_a_summary_and_its_time_are_stored(self):
        generated = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
        self.goal.summary = "Five hours on Django so far.\nNext: forms."
        self.goal.summary_generated_at = generated
        self.goal.save()

        # A fresh instance: refresh_from_db() would keep non-field attributes.
        stored = Goal.objects.get(pk=self.goal.pk)
        self.assertEqual(
            getattr(stored, "summary", None),
            "Five hours on Django so far.\nNext: forms.",
        )
        self.assertEqual(getattr(stored, "summary_generated_at", None), generated)


class GoalNextStepsFieldTests(TestCase):
    def setUp(self):
        self.goal = Goal.objects.create(
            owner=get_user_model().objects.create_user("alice"), title="Learn Django"
        )

    def test_a_new_goal_has_no_next_steps(self):
        self.goal.refresh_from_db()

        self.assertEqual(getattr(self.goal, "next_steps", None), [])
        self.assertIsNone(getattr(self.goal, "next_steps_generated_at", "missing"))

    def test_next_steps_and_their_time_are_stored_in_order(self):
        generated = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
        steps = ["Build a form", "Read the ORM docs", "Write a test"]
        self.goal.next_steps = steps
        self.goal.next_steps_generated_at = generated
        self.goal.save()

        # A fresh instance: refresh_from_db() would keep non-field attributes.
        stored = Goal.objects.get(pk=self.goal.pk)
        self.assertEqual(getattr(stored, "next_steps", None), steps)
        self.assertEqual(getattr(stored, "next_steps_generated_at", None), generated)
