from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import resolve

from core import views


class HomePageTests(TestCase):
    def test_home_is_served_by_core_through_core_urls(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        match = resolve("/")
        self.assertIs(match.func, views.home)
        self.assertEqual(match.url_name, "home")
        self.assertIs(resolve("/", urlconf="core.urls").func, views.home)

    def test_home_renders_home_template_extending_base(self):
        response = self.client.get("/")

        self.assertTemplateUsed(response, "home.html")
        self.assertTemplateUsed(response, "base.html")

    def test_templates_load_from_the_project_templates_dir(self):
        response = self.client.get("/")

        origins = {t.name: Path(t.origin.name) for t in response.templates}
        for name in ("base.html", "home.html"):
            with self.subTest(template=name):
                self.assertEqual(origins[name], settings.BASE_DIR / "templates" / name)
