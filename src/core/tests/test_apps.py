from django.apps import apps
from django.test import SimpleTestCase


class InstalledAppsTests(SimpleTestCase):
    def test_core_app_is_installed(self):
        self.assertIs(apps.is_installed("core"), True)
