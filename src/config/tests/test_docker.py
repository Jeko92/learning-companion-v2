"""The files that build and run the container image, at the repo root."""

import importlib
import json
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
        # .env files at any depth, as .gitignore ignores them: COPY src/ would
        # otherwise take a nested src/.env or a .env.local into the image.
        "**/.env",
        "**/.env.*",
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

    def test_the_smoke_script_runs_the_image_with_an_env_file_from_the_example(self):
        # The documented `docker run --env-file .env` path, with a .env copied
        # from .env.example, must keep the database on the volume.
        script = self.SCRIPT.read_text()
        self.assertIn(".env.example", script)
        self.assertIn("--env-file", script)


DOCKERFILE = ROOT / "Dockerfile"
ENTRYPOINT = ROOT / "docker" / "entrypoint.sh"


def instructions(text):
    """(INSTRUCTION, arguments) for each Dockerfile instruction, with line
    continuations joined and comments dropped."""
    joined = re.sub(r"\\\n", " ", text)
    found = []
    for line in joined.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            instruction, _, arguments = line.partition(" ")
            found.append((instruction.upper(), " ".join(arguments.split())))
    return found


def stages(text):
    """The instructions of each build stage, split at FROM."""
    found = []
    for instruction, arguments in instructions(text):
        if instruction == "FROM":
            found.append([])
        found[-1].append((instruction, arguments))
    return found


def arguments_of(stage, wanted):
    return [arguments for instruction, arguments in stage if instruction == wanted]


class DockerfileTests(SimpleTestCase):
    """A two-stage image: the build stage makes the CSS and static files, the
    final stage serves them with gunicorn as a non-root user."""

    def setUp(self):
        self.assertTrue(DOCKERFILE.is_file(), "Dockerfile is missing")
        self.build, self.final = stages(DOCKERFILE.read_text())

    def test_both_stages_start_from_the_official_python_slim_image(self):
        self.assertEqual(
            [arguments_of(stage, "FROM") for stage in (self.build, self.final)],
            [["python:3.14-slim AS build"], ["python:3.14-slim"]],
        )

    def test_the_build_stage_installs_requirements_builds_css_and_collects(self):
        runs = " ".join(arguments_of(self.build, "RUN"))
        self.assertRegex(runs, r"pip install .*-r requirements\.txt")
        (build_run,) = [
            run for run in arguments_of(self.build, "RUN") if "tailwind build" in run
        ]
        self.assertIn("collectstatic --noinput", build_run)
        # Settings need both keys to load; dummies only for this one RUN.
        self.assertIn("SECRET_KEY=", build_run)
        self.assertIn("OPENAI_API_KEY=", build_run)

    def test_no_key_is_baked_into_the_image(self):
        for stage in (self.build, self.final):
            for instruction in ("ENV", "ARG"):
                for arguments in arguments_of(stage, instruction):
                    with self.subTest(instruction=instruction, arguments=arguments):
                        self.assertNotIn("SECRET_KEY", arguments)
                        self.assertNotIn("OPENAI_API_KEY", arguments)

    def test_the_final_stage_copies_the_virtualenv_and_static_files(self):
        copies = arguments_of(self.final, "COPY")
        self.assertIn("--from=build /opt/venv /opt/venv", copies)
        self.assertTrue(
            any(c.startswith("--from=build /app/src/staticfiles") for c in copies),
            copies,
        )

    def test_the_final_stage_runs_as_a_non_root_user(self):
        (user,) = arguments_of(self.final, "USER")
        self.assertNotIn(user.split(":")[0], ("root", "0"))

    def test_the_database_lives_on_the_data_volume(self):
        self.assertIn("/app/data", arguments_of(self.final, "VOLUME"))
        env = " ".join(arguments_of(self.final, "ENV"))
        self.assertIn("DATABASE_URL=sqlite:////app/data/db.sqlite3", env)

    def test_the_final_stage_exposes_port_8000(self):
        self.assertEqual(arguments_of(self.final, "EXPOSE"), ["8000"])

    def test_the_healthcheck_requests_the_favicon_with_python(self):
        (healthcheck,) = arguments_of(self.final, "HEALTHCHECK")
        self.assertIn("CMD", healthcheck)
        self.assertIn("python", healthcheck)
        self.assertIn("http://127.0.0.1:8000/favicon.ico", healthcheck)

    def test_the_entrypoint_and_command_are_exec_form(self):
        # Exec form makes gunicorn PID 1, so docker stop reaches it directly.
        (entrypoint,) = arguments_of(self.final, "ENTRYPOINT")
        self.assertEqual(json.loads(entrypoint), ["/app/docker/entrypoint.sh"])
        (command,) = arguments_of(self.final, "CMD")
        command = json.loads(command)
        self.assertEqual(command[0], "gunicorn")
        self.assertIn("config.wsgi:application", command)
        self.assertIn("0.0.0.0:8000", command)


class EntrypointTests(SimpleTestCase):
    """The container applies migrations, then runs its command as PID 1."""

    def test_the_entrypoint_migrates_then_execs_the_command(self):
        self.assertTrue(ENTRYPOINT.is_file(), "docker/entrypoint.sh is missing")
        self.assertTrue(os.access(ENTRYPOINT, os.X_OK), "it is not executable")
        lines = [line.strip() for line in ENTRYPOINT.read_text().splitlines()]
        code = [line for line in lines if line and not line.startswith("#")]
        self.assertIn("set -eu", code)
        self.assertIn("python src/manage.py migrate --noinput", code)
        self.assertEqual(code[-1], 'exec "$@"')
