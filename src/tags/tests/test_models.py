from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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
