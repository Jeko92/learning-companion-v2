from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.test import TestCase

from tags.models import Tag


class TagModelTests(TestCase):
    def test_tag_has_a_short_name_and_shows_it(self):
        tag = Tag.objects.create(name="Python")

        self.assertEqual(Tag._meta.get_field("name").max_length, 50)
        self.assertEqual(str(tag), "Python")

    def test_name_is_stored_trimmed(self):
        tag = Tag.objects.create(name="  Python ")

        tag.refresh_from_db()
        self.assertEqual(tag.name, "Python")

    def test_blank_or_whitespace_only_name_is_invalid(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as caught:
                    Tag(name=name).full_clean()

                self.assertIn("name", caught.exception.error_dict)

    def test_names_are_unique_regardless_of_case(self):
        Tag.objects.create(name="Python")

        # Enforced by the database, not only by validation.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tag.objects.create(name="python")
        with self.assertRaises(ValidationError) as caught:
            Tag(name="PYTHON").full_clean()
        self.assertIn("A tag with this name already exists.", caught.exception.messages)

    def test_a_missing_name_is_invalid_not_a_crash(self):
        with self.assertRaises(ValidationError) as caught:
            Tag(name=None).full_clean()

        self.assertIn("name", caught.exception.error_dict)


class GetOrCreateByNameTests(TestCase):
    def setUp(self):
        self.python = Tag.objects.create(name="Python")

    def test_finds_an_existing_tag_whatever_the_case_and_whitespace(self):
        tag, created = Tag.objects.get_or_create_by_name(" PYTHON ")

        self.assertEqual((tag, created), (self.python, False))
        self.assertEqual(tag.name, "Python")
        self.assertEqual(Tag.objects.count(), 1)

    def test_creates_a_trimmed_tag_when_none_matches(self):
        tag, created = Tag.objects.get_or_create_by_name(" Django ")

        self.assertIs(created, True)
        self.assertEqual(Tag.objects.get(pk=tag.pk).name, "Django")

    def test_blank_name_is_rejected_and_creates_nothing(self):
        with self.assertRaises(ValidationError):
            Tag.objects.get_or_create_by_name("   ")

        self.assertEqual(Tag.objects.count(), 1)

    def test_losing_a_creation_race_returns_the_existing_tag(self):
        # Make the initial lookup miss once, as if another request created
        # "Python" right after it: the create must then find the winner.
        real_first = QuerySet.first
        missed = []

        def first_missing_once(queryset):
            if not missed:
                missed.append(True)
                return None
            return real_first(queryset)

        with (
            patch.object(QuerySet, "first", first_missing_once),
            transaction.atomic(),
        ):
            tag, created = Tag.objects.get_or_create_by_name("python")
            # The caller's transaction must still be usable.
            count = Tag.objects.count()

        self.assertEqual((tag, created), (self.python, False))
        self.assertEqual(count, 1)

    def test_a_missing_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            Tag.objects.get_or_create_by_name(None)

        self.assertEqual(Tag.objects.count(), 1)


class NameNormalisationTests(TestCase):
    def setUp(self):
        self.python = Tag.objects.create(name="Python")

    def test_full_width_letters_find_the_existing_tag(self):
        tag, created = Tag.objects.get_or_create_by_name("ＰＹＴＨＯＮ")

        self.assertEqual((tag, created), (self.python, False))

    def test_composed_and_decomposed_spellings_are_one_tag(self):
        first, _ = Tag.objects.get_or_create_by_name("cafe\u0301")
        second, created = Tag.objects.get_or_create_by_name("café")

        self.assertEqual((second, created), (first, False))

    def test_inner_whitespace_collapses_to_one_space(self):
        tag, _ = Tag.objects.get_or_create_by_name("Machine \t  Learning")
        saved = Tag.objects.create(name=" Data\u00a0 Science ")

        self.assertEqual(Tag.objects.get(pk=tag.pk).name, "Machine Learning")
        self.assertEqual(Tag.objects.get(pk=saved.pk).name, "Data Science")

    def test_control_and_invisible_characters_are_rejected(self):
        message = "Tag names can't contain control or invisible characters."
        for name in ("Py\x00thon", "Python\u200b", "\ufeffPython"):
            with self.subTest(name=repr(name)):
                with self.assertRaises(ValidationError) as caught:
                    Tag.objects.get_or_create_by_name(name)

                self.assertIn(message, caught.exception.messages)
                self.assertEqual(Tag.objects.count(), 1)
