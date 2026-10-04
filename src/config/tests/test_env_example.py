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
        self.assertEqual(sorted(self.assignments()), sorted(VARIABLES))

    def test_each_variable_has_a_comment_above_it(self):
        lines = self.read_lines()
        for name in VARIABLES:
            with self.subTest(variable=name):
                index = next(
                    (i for i, line in enumerate(lines) if line.startswith(f"{name}=")),
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
