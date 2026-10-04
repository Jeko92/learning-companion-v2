"""The files that build and run the container image, at the repo root."""

import importlib
import os
import re
import subprocess

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


class SmokeScriptTests(SimpleTestCase):
    """scripts/docker-smoke.sh builds and runs the image and checks it serves
    the app. It needs Docker and takes minutes, so the suite only checks the
    script is there and parses; final-review (and later CI) runs it."""

    SCRIPT = ROOT / "scripts" / "docker-smoke.sh"

    def test_the_smoke_script_is_an_executable_bash_script(self):
        self.assertTrue(self.SCRIPT.is_file(), "scripts/docker-smoke.sh is missing")
        self.assertTrue(os.access(self.SCRIPT, os.X_OK), "it is not executable")
        self.assertTrue(self.SCRIPT.read_text().startswith("#!/usr/bin/env bash\n"))

    def test_the_smoke_script_parses(self):
        result = subprocess.run(
            ["bash", "-n", str(self.SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
