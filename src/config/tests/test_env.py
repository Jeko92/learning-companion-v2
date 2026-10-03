import os
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.env import resolve_settings

MISSING_ENV_FILE = Path(__file__).parent / "no-such.env"


class ResolveSettingsTests(SimpleTestCase):
    def resolve(self, environ, env_file=MISSING_ENV_FILE):
        return resolve_settings(environ, env_file)

    def write_env_file(self, content):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        env_file = Path(tmp_dir.name) / ".env"
        env_file.write_text(content)
        return env_file

    def test_secret_key_comes_from_environment(self):
        settings = self.resolve({"SECRET_KEY": "from-env"})

        self.assertEqual(settings.secret_key, "from-env")

    def test_secret_key_starting_with_dollar_is_used_literally(self):
        # Generated keys can start with "$"; it must not be expanded as a
        # reference to another variable.
        settings = self.resolve({"SECRET_KEY": "$abc", "abc": "other"})

        self.assertEqual(settings.secret_key, "$abc")

    def test_missing_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve({})

    def test_empty_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve({"SECRET_KEY": ""})

    def test_whitespace_only_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve({"SECRET_KEY": "  \t "})

    def test_debug_is_parsed_as_boolean(self):
        cases = {
            "True": True,
            "1": True,
            "yes": True,
            "False": False,
            "0": False,
            "no": False,
        }
        for raw, expected in cases.items():
            with self.subTest(DEBUG=raw):
                settings = self.resolve({"SECRET_KEY": "x", "DEBUG": raw})

                self.assertIs(settings.debug, expected)

    def test_debug_defaults_to_false(self):
        settings = self.resolve({"SECRET_KEY": "x"})

        self.assertIs(settings.debug, False)

    def test_allowed_hosts_is_a_trimmed_comma_separated_list(self):
        settings = self.resolve(
            {"SECRET_KEY": "x", "ALLOWED_HOSTS": "example.com, www.example.com"}
        )

        self.assertEqual(settings.allowed_hosts, ["example.com", "www.example.com"])

    def test_allowed_hosts_drops_empty_entries(self):
        cases = {"a.com, ": ["a.com"], " , a.com,,": ["a.com"], "": []}
        for raw, expected in cases.items():
            with self.subTest(ALLOWED_HOSTS=raw):
                settings = self.resolve({"SECRET_KEY": "x", "ALLOWED_HOSTS": raw})

                self.assertEqual(settings.allowed_hosts, expected)

    def test_allowed_hosts_defaults_to_localhost(self):
        settings = self.resolve({"SECRET_KEY": "x"})

        self.assertEqual(settings.allowed_hosts, ["localhost", "127.0.0.1"])

    def test_openai_model_defaults_to_gpt_4_1_mini(self):
        for environ in (
            {"SECRET_KEY": "x"},
            {"SECRET_KEY": "x", "OPENAI_MODEL": ""},
            {"SECRET_KEY": "x", "OPENAI_MODEL": "  \t "},
        ):
            with self.subTest(environ=environ):
                settings = self.resolve(environ)

                self.assertEqual(settings.openai_model, "gpt-4.1-mini")

    def test_openai_model_is_trimmed(self):
        settings = self.resolve({"SECRET_KEY": "x", "OPENAI_MODEL": " gpt-test \n"})

        self.assertEqual(settings.openai_model, "gpt-test")

    def test_openai_model_from_environment_wins_over_env_file(self):
        env_file = self.write_env_file("OPENAI_MODEL=from-file\n")

        from_file = self.resolve({"SECRET_KEY": "x"}, env_file)
        from_env = self.resolve(
            {"SECRET_KEY": "x", "OPENAI_MODEL": "from-env"}, env_file
        )

        self.assertEqual(from_file.openai_model, "from-file")
        self.assertEqual(from_env.openai_model, "from-env")

    def test_values_come_from_env_file(self):
        env_file = self.write_env_file(
            "SECRET_KEY=from-file\nDEBUG=True\nALLOWED_HOSTS=example.com\n"
        )

        settings = self.resolve({}, env_file)

        self.assertEqual(settings.secret_key, "from-file")
        self.assertIs(settings.debug, True)
        self.assertEqual(settings.allowed_hosts, ["example.com"])

    def test_environment_wins_over_env_file(self):
        env_file = self.write_env_file("SECRET_KEY=from-file\nDEBUG=True\n")

        settings = self.resolve({"SECRET_KEY": "from-env", "DEBUG": "False"}, env_file)

        self.assertEqual(settings.secret_key, "from-env")
        self.assertIs(settings.debug, False)

    def test_does_not_mutate_the_given_mapping_or_os_environ(self):
        env_file = self.write_env_file("SECRET_KEY=x\nLC_TEST_ONLY_IN_FILE=1\n")
        environ = {"DEBUG": "False"}
        os_environ_before = dict(os.environ)

        self.resolve(environ, env_file)

        self.assertEqual(environ, {"DEBUG": "False"})
        self.assertEqual(dict(os.environ), os_environ_before)

    def test_missing_env_file_is_not_an_error(self):
        self.assertFalse(MISSING_ENV_FILE.exists())

        settings = self.resolve({"SECRET_KEY": "from-env"}, MISSING_ENV_FILE)

        self.assertEqual(settings.secret_key, "from-env")
