import re

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

REQUIREMENTS = settings.BASE_DIR.parent / "requirements.txt"


class AiAppTests(SimpleTestCase):
    def test_ai_app_is_installed(self):
        self.assertIs(apps.is_installed("ai"), True)

    def test_the_openai_sdk_is_a_range_pinned_requirement(self):
        lines = REQUIREMENTS.read_text().splitlines()

        (line,) = [line for line in lines if re.match(r"openai\b", line)]
        self.assertRegex(line, r"^openai>=[\d.]+,<[\d.]+$")
