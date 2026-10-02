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

    def test_an_invisible_character_is_a_field_error_and_saves_nothing(self):
        tag_count = Tag.objects.count()

        response = self.save("Rust, Python\u200b")

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "focus_areas",
            "“Python\u200b”: Tag names can't contain control or invisible characters.",
        )
        self.assertEqual(Tag.objects.count(), tag_count)
        self.assertEqual([t.name for t in self.profile.focus_areas.all()], ["Django"])

    def test_focus_area_input_is_bounded_before_any_database_work(self):
        cases = (
            (
                "too long",
                "x" * 1001,
                "Ensure this value has at most 1000 characters (it has 1001).",
            ),
            (
                "too many",
                ", ".join(f"t{n}" for n in range(1, 22)),
                "You can have at most 20 focus areas.",
            ),
        )
        tag_count = Tag.objects.count()
        for case, focus_areas, message in cases:
            with self.subTest(case=case):
                response = self.save(focus_areas)

                self.assertEqual(response.status_code, 200)
                self.assertFormError(response.context["form"], "focus_areas", message)
                self.assertEqual(Tag.objects.count(), tag_count)
                self.assertEqual(
                    [t.name for t in self.profile.focus_areas.all()], ["Django"]
                )

    def test_twenty_focus_areas_are_allowed(self):
        response = self.save(", ".join(f"t{n}" for n in range(1, 21)))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.profile.focus_areas.count(), 20)

    def test_full_width_commas_separate_entries(self):
        response = self.save("Python\uff0cDjango")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [t.name for t in self.profile.focus_areas.all()], ["Django", "Python"]
        )
