from django.conf import settings
from django.test import SimpleTestCase

ENV_EXAMPLE = settings.BASE_DIR.parent / ".env.example"
VARIABLES = [
    "SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
]
# Documented as a commented-out example, never a live NAME= line: copied into
# .env and passed with docker run --env-file, a blank DATABASE_URL= would
# override the image's own value and leave the app without a writable database.
COMMENTED_EXAMPLES = ["DATABASE_URL"]


class EnvExampleTests(SimpleTestCase):
    def read_lines(self):
        self.assertTrue(ENV_EXAMPLE.is_file(), f"{ENV_EXAMPLE} is missing")
        return ENV_EXAMPLE.read_text().splitlines()

    def assignments(self):
        return dict(
            line.split("=", 1)
            for line in self.read_lines()
            if line.strip() and not line.lstrip().startswith("#")
        )

    def test_defines_every_variable(self):
        live = [name for name in VARIABLES if name not in COMMENTED_EXAMPLES]
        self.assertEqual(sorted(self.assignments()), sorted(live))

    def test_database_url_is_only_a_commented_out_example(self):
        lines = self.read_lines()
        self.assertNotIn("DATABASE_URL", self.assignments())
        self.assertIn("# DATABASE_URL=sqlite:////app/data/db.sqlite3", lines)

    def test_each_variable_has_a_comment_above_it(self):
        lines = self.read_lines()
        for name in VARIABLES:
            with self.subTest(variable=name):
                prefix = f"# {name}=" if name in COMMENTED_EXAMPLES else f"{name}="
                index = next(
                    (i for i, line in enumerate(lines) if line.startswith(prefix)),
                    None,
                )
                self.assertIsNotNone(index, f"{name} is not defined")
                self.assertTrue(index > 0 and lines[index - 1].startswith("#"))

    def test_debug_is_on_for_local_development(self):
        self.assertEqual(self.assignments()["DEBUG"], "True")

    def test_the_openai_key_is_an_obvious_placeholder(self):
        # Never a real key in a committed file; a dummy is enough for tests.
        self.assertEqual(self.assignments().get("OPENAI_API_KEY"), "sk-dummy")

    def test_the_openai_model_shows_the_default(self):
        self.assertEqual(self.assignments().get("OPENAI_MODEL"), "gpt-4.1-mini")
