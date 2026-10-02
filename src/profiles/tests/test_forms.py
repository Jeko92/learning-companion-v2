from django.contrib.auth import get_user_model
from django.test import TestCase

from tags.models import Tag

PASSWORD = "Tr4ck-Learning!"


class FocusAreasInputTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice", password=PASSWORD)
        self.profile = self.alice.profile
        self.profile.focus_areas.add(Tag.objects.get_or_create_by_name("Django")[0])
        self.python = Tag.objects.create(name="Python")
        self.path = f"/profile/{self.profile.pk}/edit/"
        self.client.force_login(self.alice)

    def save(self, focus_areas):
        return self.client.post(
            self.path, {"name": "Alice", "cohort": "", "focus_areas": focus_areas}
        )

    def test_focus_areas_are_set_from_comma_separated_text(self):
        response = self.save(" python , Machine Learning,, MACHINE learning , ")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [tag.name for tag in self.profile.focus_areas.all()],
            ["Machine Learning", "Python"],
        )
        # The existing tag is reused with its spelling, the new one made once.
        self.assertIn(self.python, self.profile.focus_areas.all())
        self.assertEqual(Tag.objects.filter(name__iexact="machine learning").count(), 1)
        # Django left the profile, but the shared tag itself stays.
        self.assertTrue(Tag.objects.filter(name="Django").exists())
