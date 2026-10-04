import os
import tempfile
import warnings
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.env import resolve_settings

MISSING_ENV_FILE = Path(__file__).parent / "no-such.env"
TEST_OPENAI_API_KEY = "sk-test-env"


def environ(**values):
    """A process environment with a dummy OPENAI_API_KEY plus the given
    values, so tests about other variables don't trip over the key."""
    return {"OPENAI_API_KEY": TEST_OPENAI_API_KEY, **values}


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
        settings = self.resolve(environ(SECRET_KEY="from-env"))

        self.assertEqual(settings.secret_key, "from-env")

    def test_secret_key_starting_with_dollar_is_used_literally(self):
        # Generated keys can start with "$"; it must not be expanded as a
        # reference to another variable.
        settings = self.resolve(environ(SECRET_KEY="$abc", abc="other"))

        self.assertEqual(settings.secret_key, "$abc")

    def test_missing_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve(environ())

    def test_empty_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve(environ(SECRET_KEY=""))

    def test_whitespace_only_secret_key_raises_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self.resolve(environ(SECRET_KEY="  \t "))

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
                settings = self.resolve(environ(SECRET_KEY="x", DEBUG=raw))

                self.assertIs(settings.debug, expected)

    def test_debug_defaults_to_false(self):
        settings = self.resolve(environ(SECRET_KEY="x"))

        self.assertIs(settings.debug, False)

    def test_allowed_hosts_is_a_trimmed_comma_separated_list(self):
        settings = self.resolve(
            environ(SECRET_KEY="x", ALLOWED_HOSTS="example.com, www.example.com")
        )

        self.assertEqual(settings.allowed_hosts, ["example.com", "www.example.com"])

    def test_allowed_hosts_drops_empty_entries(self):
        cases = {"a.com, ": ["a.com"], " , a.com,,": ["a.com"], "": []}
        for raw, expected in cases.items():
            with self.subTest(ALLOWED_HOSTS=raw):
                settings = self.resolve(environ(SECRET_KEY="x", ALLOWED_HOSTS=raw))

                self.assertEqual(settings.allowed_hosts, expected)

    def test_allowed_hosts_defaults_to_localhost(self):
        settings = self.resolve(environ(SECRET_KEY="x"))

        self.assertEqual(settings.allowed_hosts, ["localhost", "127.0.0.1"])

    def test_openai_api_key_comes_from_environment(self):
        settings = self.resolve(environ(SECRET_KEY="x"))

        self.assertEqual(settings.openai_api_key, TEST_OPENAI_API_KEY)

    def test_openai_api_key_starting_with_dollar_is_used_literally(self):
        settings = self.resolve(
            {"SECRET_KEY": "x", "OPENAI_API_KEY": "$abc", "abc": "other"}
        )

        self.assertEqual(settings.openai_api_key, "$abc")

    def test_a_missing_or_blank_openai_api_key_raises_improperly_configured(self):
        for given in (
            {"SECRET_KEY": "x"},
            {"SECRET_KEY": "x", "OPENAI_API_KEY": ""},
            {"SECRET_KEY": "x", "OPENAI_API_KEY": "  \t "},
        ):
            with self.subTest(environ=given):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    self.resolve(given)

                # A fixed message: it names the variable and never echoes a value.
                self.assertEqual(
                    str(raised.exception),
                    "The OPENAI_API_KEY environment variable must be set and not empty",
                )

    def test_openai_api_key_from_environment_wins_over_env_file(self):
        env_file = self.write_env_file("OPENAI_API_KEY=sk-from-file\n")

        from_file = self.resolve({"SECRET_KEY": "x"}, env_file)
        from_env = self.resolve(environ(SECRET_KEY="x"), env_file)

        self.assertEqual(from_file.openai_api_key, "sk-from-file")
        self.assertEqual(from_env.openai_api_key, TEST_OPENAI_API_KEY)

    def test_openai_model_defaults_to_gpt_4_1_mini(self):
        for given in (
            environ(SECRET_KEY="x"),
            environ(SECRET_KEY="x", OPENAI_MODEL=""),
            environ(SECRET_KEY="x", OPENAI_MODEL="  \t "),
        ):
            with self.subTest(environ=given):
                settings = self.resolve(given)

                self.assertEqual(settings.openai_model, "gpt-4.1-mini")

    def test_openai_model_is_trimmed(self):
        settings = self.resolve(environ(SECRET_KEY="x", OPENAI_MODEL=" gpt-test \n"))

        self.assertEqual(settings.openai_model, "gpt-test")

    def test_openai_model_from_environment_wins_over_env_file(self):
        env_file = self.write_env_file("OPENAI_MODEL=from-file\n")

        from_file = self.resolve(environ(SECRET_KEY="x"), env_file)
        from_env = self.resolve(
            environ(SECRET_KEY="x", OPENAI_MODEL="from-env"), env_file
        )

        self.assertEqual(from_file.openai_model, "from-file")
        self.assertEqual(from_env.openai_model, "from-env")

    def test_database_is_none_when_database_url_is_unset_or_blank(self):
        # None means settings.py keeps its own default database.
        for raw in (None, "", "  "):
            with self.subTest(DATABASE_URL=raw):
                values = {} if raw is None else {"DATABASE_URL": raw}
                settings = self.resolve(environ(SECRET_KEY="x", **values))

                self.assertIsNone(settings.database)

    def test_database_url_is_parsed_into_a_database_config(self):
        cases = {
            "sqlite:////app/data/db.sqlite3": (
                "django.db.backends.sqlite3",
                "/app/data/db.sqlite3",
            ),
            "postgres://user:pw@db:5432/companion": (
                "django.db.backends.postgresql",
                "companion",
            ),
        }
        for raw, (engine, name) in cases.items():
            with self.subTest(DATABASE_URL=raw):
                settings = self.resolve(environ(SECRET_KEY="x", DATABASE_URL=raw))

                self.assertEqual(settings.database["ENGINE"], engine)
                self.assertEqual(settings.database["NAME"], name)

    def test_database_url_from_environment_wins_over_env_file(self):
        env_file = self.write_env_file("DATABASE_URL=sqlite:////from/file.sqlite3\n")

        from_file = self.resolve(environ(SECRET_KEY="x"), env_file)
        from_env = self.resolve(
            environ(SECRET_KEY="x", DATABASE_URL="sqlite:////from/env.sqlite3"),
            env_file,
        )

        self.assertEqual(from_file.database["NAME"], "/from/file.sqlite3")
        self.assertEqual(from_env.database["NAME"], "/from/env.sqlite3")

    def test_an_unparseable_database_url_raises_improperly_configured(self):
        # django-environ only warns about the first three (Django would fail
        # later, at the first query, without naming the variable), and raises
        # a ValueError quoting part of the URL for a port it can't read, as
        # with a password holding an unencoded "/".
        unparseable = (
            "not-a-url",
            "foo://host/db",
            "http://example.com/db",
            "postgres://user:pw@host:abc/db",
            "postgres://user:pa/ss@db/companion",
        )
        for raw in unparseable:
            with self.subTest(DATABASE_URL=raw):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    with self.assertRaises(ImproperlyConfigured) as raised:
                        self.resolve(environ(SECRET_KEY="x", DATABASE_URL=raw))

                # A fixed message: a URL can carry a password, so never echo it,
                # nor chain an exception that does.
                self.assertEqual(
                    str(raised.exception),
                    "The DATABASE_URL environment variable is not a valid database URL",
                )
                self.assertIsNone(raised.exception.__cause__)
                self.assertTrue(raised.exception.__suppress_context__)
                self.assertEqual(caught, [])

    def test_csrf_trusted_origins_is_a_trimmed_comma_separated_list(self):
        cases = {
            "https://a.example, http://b.example:8000": [
                "https://a.example",
                "http://b.example:8000",
            ],
            " , https://a.example,,": ["https://a.example"],
            "": [],
        }
        for raw, expected in cases.items():
            with self.subTest(CSRF_TRUSTED_ORIGINS=raw):
                settings = self.resolve(
                    environ(SECRET_KEY="x", CSRF_TRUSTED_ORIGINS=raw)
                )

                self.assertEqual(settings.csrf_trusted_origins, expected)

    def test_csrf_trusted_origins_defaults_to_an_empty_list(self):
        settings = self.resolve(environ(SECRET_KEY="x"))

        self.assertEqual(settings.csrf_trusted_origins, [])

    def test_csrf_trusted_origins_from_environment_wins_over_env_file(self):
        env_file = self.write_env_file("CSRF_TRUSTED_ORIGINS=https://file.example\n")

        from_file = self.resolve(environ(SECRET_KEY="x"), env_file)
        from_env = self.resolve(
            environ(SECRET_KEY="x", CSRF_TRUSTED_ORIGINS="https://env.example"),
            env_file,
        )

        self.assertEqual(from_file.csrf_trusted_origins, ["https://file.example"])
        self.assertEqual(from_env.csrf_trusted_origins, ["https://env.example"])

    def test_a_csrf_trusted_origin_without_http_or_https_raises(self):
        for raw in ("example.com", "https://ok.example, ftp://files.example"):
            with self.subTest(CSRF_TRUSTED_ORIGINS=raw):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    self.resolve(environ(SECRET_KEY="x", CSRF_TRUSTED_ORIGINS=raw))

                # A fixed message: it names the variable, never the value.
                self.assertEqual(
                    str(raised.exception),
                    "The CSRF_TRUSTED_ORIGINS environment variable must list "
                    "origins that start with http:// or https://",
                )

    def test_ssl_redirect_defaults_to_the_opposite_of_debug(self):
        for debug, expected in (("False", True), ("True", False)):
            with self.subTest(DEBUG=debug):
                for raw in (None, "", "  "):
                    values = {"SECRET_KEY": "x", "DEBUG": debug}
                    if raw is not None:
                        values["SECURE_SSL_REDIRECT"] = raw
                    with self.subTest(SECURE_SSL_REDIRECT=raw):
                        settings = self.resolve(environ(**values))

                        self.assertIs(settings.ssl_redirect, expected)

    def test_an_explicit_ssl_redirect_wins_over_the_debug_default(self):
        cases = {
            "True": True,
            "true": True,
            " yes ": True,
            "on": True,
            "1": True,
            "False": False,
            "false": False,
            "no": False,
            "OFF": False,
            "0": False,
        }
        for debug in ("True", "False"):
            for raw, expected in cases.items():
                with self.subTest(DEBUG=debug, SECURE_SSL_REDIRECT=raw):
                    settings = self.resolve(
                        environ(SECRET_KEY="x", DEBUG=debug, SECURE_SSL_REDIRECT=raw)
                    )

                    self.assertIs(settings.ssl_redirect, expected)

    def test_an_unknown_ssl_redirect_value_raises(self):
        # A typo must never quietly turn HTTPS off.
        for raw in ("maybe", "Ture", "2"):
            with self.subTest(SECURE_SSL_REDIRECT=raw):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    self.resolve(environ(SECRET_KEY="x", SECURE_SSL_REDIRECT=raw))

                self.assertEqual(
                    str(raised.exception),
                    "The SECURE_SSL_REDIRECT environment variable must be true or false",
                )

    def test_secure_cookies_follow_the_same_rules_as_the_ssl_redirect(self):
        for name, field in (
            ("SESSION_COOKIE_SECURE", "session_cookie_secure"),
            ("CSRF_COOKIE_SECURE", "csrf_cookie_secure"),
        ):
            cases = (
                ({"DEBUG": "False"}, True),
                ({"DEBUG": "True"}, False),
                ({"DEBUG": "False", name: ""}, True),
                ({"DEBUG": "True", name: " "}, False),
                ({"DEBUG": "False", name: "false"}, False),
                ({"DEBUG": "True", name: "yes"}, True),
            )
            for values, expected in cases:
                with self.subTest(**values):
                    settings = self.resolve(environ(SECRET_KEY="x", **values))

                    self.assertIs(getattr(settings, field), expected)
            with self.subTest(name=name, value="maybe"):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    self.resolve(environ(SECRET_KEY="x", **{name: "maybe"}))

                self.assertEqual(
                    str(raised.exception),
                    f"The {name} environment variable must be true or false",
                )

    def test_hsts_seconds_default_to_an_hour_unless_debug(self):
        cases = (
            ({"DEBUG": "False"}, 3600),
            ({"DEBUG": "True"}, 0),
            ({"DEBUG": "False", "SECURE_HSTS_SECONDS": ""}, 3600),
            ({"DEBUG": "True", "SECURE_HSTS_SECONDS": "  "}, 0),
        )
        for values, expected in cases:
            with self.subTest(**values):
                settings = self.resolve(environ(SECRET_KEY="x", **values))

                self.assertEqual(settings.hsts_seconds, expected)

    def test_explicit_hsts_seconds_win_over_the_debug_default(self):
        cases = (
            ({"DEBUG": "False", "SECURE_HSTS_SECONDS": "0"}, 0),
            ({"DEBUG": "False", "SECURE_HSTS_SECONDS": " 31536000 "}, 31536000),
            ({"DEBUG": "True", "SECURE_HSTS_SECONDS": "60"}, 60),
        )
        for values, expected in cases:
            with self.subTest(**values):
                settings = self.resolve(environ(SECRET_KEY="x", **values))

                self.assertEqual(settings.hsts_seconds, expected)

    def test_hsts_seconds_that_are_not_a_whole_number_0_or_more_raise(self):
        for raw in ("abc", "1.5", "-1", "1e3"):
            with self.subTest(SECURE_HSTS_SECONDS=raw):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    self.resolve(environ(SECRET_KEY="x", SECURE_HSTS_SECONDS=raw))

                self.assertEqual(
                    str(raised.exception),
                    "The SECURE_HSTS_SECONDS environment variable must be a "
                    "whole number of seconds, 0 or more",
                )

    def test_the_proxy_ssl_header_is_opt_in_whatever_debug_is(self):
        cases = (
            ({"DEBUG": "False"}, False),
            ({"DEBUG": "True"}, False),
            ({"DEBUG": "False", "SECURE_PROXY_SSL_HEADER": ""}, False),
            ({"DEBUG": "False", "SECURE_PROXY_SSL_HEADER": "true"}, True),
            ({"DEBUG": "True", "SECURE_PROXY_SSL_HEADER": "1"}, True),
            ({"DEBUG": "False", "SECURE_PROXY_SSL_HEADER": "no"}, False),
        )
        for values, expected in cases:
            with self.subTest(**values):
                settings = self.resolve(environ(SECRET_KEY="x", **values))

                self.assertIs(settings.proxy_ssl_header, expected)

    def test_an_unknown_proxy_ssl_header_value_raises(self):
        with self.assertRaises(ImproperlyConfigured) as raised:
            self.resolve(environ(SECRET_KEY="x", SECURE_PROXY_SSL_HEADER="https"))

        self.assertEqual(
            str(raised.exception),
            "The SECURE_PROXY_SSL_HEADER environment variable must be true or false",
        )

    def test_values_come_from_env_file(self):
        env_file = self.write_env_file(
            "SECRET_KEY=from-file\nDEBUG=True\nALLOWED_HOSTS=example.com\n"
        )

        settings = self.resolve(environ(), env_file)

        self.assertEqual(settings.secret_key, "from-file")
        self.assertIs(settings.debug, True)
        self.assertEqual(settings.allowed_hosts, ["example.com"])

    def test_environment_wins_over_env_file(self):
        env_file = self.write_env_file("SECRET_KEY=from-file\nDEBUG=True\n")

        settings = self.resolve(environ(SECRET_KEY="from-env", DEBUG="False"), env_file)

        self.assertEqual(settings.secret_key, "from-env")
        self.assertIs(settings.debug, False)

    def test_does_not_mutate_the_given_mapping_or_os_environ(self):
        env_file = self.write_env_file("SECRET_KEY=x\nLC_TEST_ONLY_IN_FILE=1\n")
        given = environ(DEBUG="False")
        given_before = dict(given)
        os_environ_before = dict(os.environ)

        self.resolve(given, env_file)

        self.assertEqual(given, given_before)
        self.assertEqual(dict(os.environ), os_environ_before)

    def test_missing_env_file_is_not_an_error(self):
        self.assertFalse(MISSING_ENV_FILE.exists())

        settings = self.resolve(environ(SECRET_KEY="from-env"), MISSING_ENV_FILE)

        self.assertEqual(settings.secret_key, "from-env")
