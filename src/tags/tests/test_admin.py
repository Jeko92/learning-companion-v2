from django.contrib import admin
from django.test import SimpleTestCase

from tags.models import Tag


class TagAdminTests(SimpleTestCase):
    def test_tag_is_registered_with_a_search_on_name(self):
        self.assertIn(Tag, admin.site._registry)
        self.assertIn("name", admin.site._registry[Tag].search_fields)
