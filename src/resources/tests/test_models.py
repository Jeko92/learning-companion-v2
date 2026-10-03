from itertools import count

from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase

from goals.models import Goal
from resources import models as resource_models

_numbers = count(1)


def build_resource(goal, **fields):
    """An unsaved resource with a distinct URL and title, unless given."""
    n = next(_numbers)
    defaults = {"url": f"https://example.com/{n}", "title": f"Resource {n}"}
    return resource_models.Resource(goal=goal, **{**defaults, **fields})


def make_resource(goal, **fields):
    resource = build_resource(goal, **fields)
    resource.save()
    return resource


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


class ResourceUrlTests(TestCase):
    def setUp(self):
        fields = {f.name for f in resource_models.Resource._meta.get_fields()}
        self.assertIn("url", fields)
        alice = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")

    def test_the_url_field_holds_long_urls(self):
        url = resource_models.Resource._meta.get_field("url")

        self.assertIsInstance(url, models.URLField)
        self.assertEqual(url.max_length, 2048)

    def test_http_and_https_urls_are_accepted(self):
        long_url = "https://example.com/" + "x" * (2048 - len("https://example.com/"))
        for value in (
            "https://docs.djangoproject.com/en/6.1/",
            "http://example.com",
            "HTTPS://EXAMPLE.COM/x",
            long_url,
        ):
            with self.subTest(url=value[:40]):
                build_resource(self.goal, url=value).full_clean()

    def test_a_url_over_2048_characters_is_rejected(self):
        too_long = "https://example.com/" + "x" * (2049 - len("https://example.com/"))
        resource = build_resource(self.goal, url=too_long)

        with self.assertRaises(ValidationError) as caught:
            resource.full_clean()

        self.assertIn(
            "Ensure this value has at most 2048 characters (it has 2049).",
            caught.exception.message_dict["url"],
        )

    def test_other_schemes_and_non_urls_are_rejected_once(self):
        for value in (
            "javascript:alert(1)",
            "data:text/html,x",
            "ftp://example.com/f",
            "mailto:a@example.com",
            "/relative/path",
            "",
        ):
            with self.subTest(url=value[:40]):
                resource = build_resource(self.goal, url=value)

                with self.assertRaises(ValidationError) as caught:
                    resource.full_clean()

                self.assertIn("url", caught.exception.error_dict)
                # One validator, not Django's default one plus ours.
                self.assertEqual(len(caught.exception.error_dict["url"]), 1)

    def test_the_url_is_stored_trimmed(self):
        resource = build_resource(self.goal, url="  https://example.com/a  ")
        resource.full_clean()
        self.assertEqual(resource.url, "https://example.com/a")

        saved = make_resource(self.goal, url=" https://example.com/b ")
        saved.refresh_from_db()
        self.assertEqual(saved.url, "https://example.com/b")

    def test_the_database_only_takes_http_and_https_urls(self):
        resources = resource_models.Resource.objects.filter(
            pk=make_resource(self.goal).pk
        )
        # update() skips validators: the database must refuse other schemes.
        for url in ("javascript:alert(1)", "data:text/html,x", "ftp://example.com"):
            with (
                self.subTest(url=url),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                resources.update(url=url)
        for url in ("http://example.com/a", "https://example.com/b", "HTTP://X.COM/c"):
            with self.subTest(url=url):
                resources.update(url=url)
                self.assertEqual(resources.get().url, url)


class ResourceTitleTests(TestCase):
    def setUp(self):
        fields = {f.name for f in resource_models.Resource._meta.get_fields()}
        self.assertIn("title", fields)
        alice = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")

    def test_the_title_is_a_required_short_text(self):
        title = resource_models.Resource._meta.get_field("title")

        self.assertIsInstance(title, models.CharField)
        self.assertEqual(title.max_length, 200)
        self.assertIs(title.blank, False)

    def test_the_title_is_stored_trimmed(self):
        resource = build_resource(self.goal, title="  Read the docs ")
        resource.full_clean()
        self.assertEqual(resource.title, "Read the docs")

        saved = make_resource(self.goal, title=" Watch the talk  ")
        saved.refresh_from_db()
        self.assertEqual(saved.title, "Watch the talk")

    def test_blank_or_too_long_titles_are_rejected(self):
        for title in ("", "   ", "x" * 201):
            with self.subTest(title=title[:5]):
                resource = build_resource(self.goal, title=title)

                with self.assertRaises(ValidationError) as caught:
                    resource.full_clean()

                self.assertIn("title", caught.exception.error_dict)

    def test_a_200_character_title_is_accepted(self):
        build_resource(self.goal, title="x" * 200).full_clean()


class ResourceTypeTests(TestCase):
    def setUp(self):
        fields = {f.name for f in resource_models.Resource._meta.get_fields()}
        self.assertIn("type", fields)
        alice = get_user_model().objects.create_user("alice")
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")

    def test_the_types_are_article_video_repo_and_doc(self):
        Type = resource_models.Resource.Type

        self.assertEqual(Type.values, ["article", "video", "repo", "doc"])
        self.assertEqual(Type.labels, ["Article", "Video", "Repo", "Doc"])

    def test_a_new_resource_is_an_article(self):
        resource = make_resource(self.goal)

        self.assertEqual(resource.type, resource_models.Resource.Type.ARTICLE)

    def test_an_unknown_type_is_rejected(self):
        resource = build_resource(self.goal, type="book")

        with self.assertRaises(ValidationError) as caught:
            resource.full_clean()

        self.assertIn(
            "Value 'book' is not a valid choice.", caught.exception.message_dict["type"]
        )

    def test_the_database_only_takes_known_types(self):
        resources = resource_models.Resource.objects.filter(
            pk=make_resource(self.goal).pk
        )
        # update() skips the choices check: the database must refuse it.
        with self.assertRaises(IntegrityError), transaction.atomic():
            resources.update(type="book")
        # Every enum value passes, so the constraint's list keeps up with it.
        for value in resource_models.Resource.Type.values:
            with self.subTest(type=value):
                resources.update(type=value)
                self.assertEqual(resources.get().type, value)


class ResourceUniquenessTests(TestCase):
    URL = "https://docs.djangoproject.com/en/6.1/"

    def setUp(self):
        User = get_user_model()
        alice = User.objects.create_user("alice")
        self.goal = Goal.objects.create(owner=alice, title="Learn Django")
        self.other_goal = Goal.objects.create(owner=alice, title="Learn Go")
        self.bobs_goal = Goal.objects.create(
            owner=User.objects.create_user("bob"), title="B"
        )
        make_resource(self.goal, url=self.URL)

    def test_the_same_url_twice_on_one_goal_is_rejected(self):
        duplicate = build_resource(self.goal, url=self.URL)

        with self.assertRaises(ValidationError) as caught:
            duplicate.full_clean()

        self.assertEqual(
            caught.exception.message_dict.get(NON_FIELD_ERRORS),
            ["This goal already has this resource."],
        )

    def test_the_database_refuses_the_same_url_twice_on_one_goal(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_resource(self.goal, url=self.URL)

    def test_the_same_url_on_another_goal_is_allowed(self):
        for goal in (self.other_goal, self.bobs_goal):
            with self.subTest(goal=goal.title):
                resource = build_resource(goal, url=self.URL)
                resource.full_clean()
                resource.save()
