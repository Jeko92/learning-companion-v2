"""The files that build and run the container image, at the repo root."""

import importlib
import re

from django.conf import settings
from django.test import SimpleTestCase

ROOT = settings.BASE_DIR.parent
REQUIREMENTS = ROOT / "requirements.txt"


class RequirementsTests(SimpleTestCase):
    """The container serves static files with WhiteNoise and runs gunicorn."""

    def test_whitenoise_and_gunicorn_are_range_pinned_requirements(self):
        lines = REQUIREMENTS.read_text().splitlines()
        for package in ("whitenoise", "gunicorn"):
            with self.subTest(package=package):
                (line,) = [line for line in lines if re.match(rf"{package}\b", line)]
                self.assertRegex(line, rf"^{package}>=[\d.]+,<[\d.]+$")

    def test_whitenoise_and_gunicorn_are_installed(self):
        for module in ("whitenoise", "gunicorn"):
            with self.subTest(module=module):
                importlib.import_module(module)
