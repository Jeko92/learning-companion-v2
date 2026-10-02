from django.test import TestCase

from tags.models import Tag


class TagModelTests(TestCase):
    def test_tag_has_a_short_name_and_shows_it(self):
        tag = Tag.objects.create(name="Python")

        self.assertEqual(Tag._meta.get_field("name").max_length, 50)
        self.assertEqual(str(tag), "Python")
