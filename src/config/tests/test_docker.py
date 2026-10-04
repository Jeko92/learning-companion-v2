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


class DockerignoreTests(SimpleTestCase):
    """Secrets, local state and build output stay out of the build context."""

    EXCLUDED = (
        ".env",
        ".git",
        ".venv",
        "**/__pycache__",
        ".ruff_cache",
        "**/*.sqlite3*",
        "src/assets/css/tailwind.css",
        "src/.django_tailwind_cli",
        "src/staticfiles",
        "work",
        ".claude",
    )

    def test_secrets_local_state_and_build_output_are_excluded(self):
        path = ROOT / ".dockerignore"
        self.assertTrue(path.is_file(), ".dockerignore is missing")
        entries = {
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        for entry in self.EXCLUDED:
            with self.subTest(entry=entry):
                self.assertIn(entry, entries)
