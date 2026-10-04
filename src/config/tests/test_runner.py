import os
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.test.runner import DiscoverRunner
from django.test.utils import get_runner


class TestRunnerTests(SimpleTestCase):
    """The HTTPS settings follow DEBUG, which CI leaves unset (off), so the
    SSL redirect would turn every plain-HTTP test client request into a 301.
    The project's runner keeps the suite on plain HTTP whatever DEBUG is."""

    def test_the_project_runner_is_configured(self):
        self.assertEqual(settings.TEST_RUNNER, "config.runner.TestRunner")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_the_runner_turns_the_ssl_redirect_off_for_the_run(self):
        runner = get_runner(settings)()
        # The test environment is already set up for this run: only the
        # project's own additions run here.
        with (
            mock.patch.object(DiscoverRunner, "setup_test_environment"),
            mock.patch.object(DiscoverRunner, "teardown_test_environment"),
        ):
            runner.setup_test_environment()
            try:
                self.assertIs(settings.SECURE_SSL_REDIRECT, False)
            finally:
                runner.teardown_test_environment()

        self.assertIs(settings.SECURE_SSL_REDIRECT, True)

    def test_parallel_workers_load_their_settings_without_the_ssl_redirect(self):
        # A spawned --parallel worker loads the settings afresh: its setup
        # runs before django.setup(), so it sets the environment variable the
        # settings read.
        suite_class = get_runner(settings).parallel_test_suite
        with mock.patch.dict(os.environ, {"SECURE_SSL_REDIRECT": "True"}):
            suite_class.process_setup(*suite_class.process_setup_args)

            self.assertEqual(os.environ["SECURE_SSL_REDIRECT"], "False")
