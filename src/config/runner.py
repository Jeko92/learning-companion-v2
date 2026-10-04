"""The project's test runner (settings.TEST_RUNNER)."""

import os

from django.test import override_settings
from django.test.runner import DiscoverRunner, ParallelTestSuite


def _plain_http_worker_setup(*args):
    """Runs in each spawned --parallel worker before django.setup(), so the
    worker's settings load with the SSL redirect off (config.env reads it)."""
    os.environ["SECURE_SSL_REDIRECT"] = "False"


class PlainHttpParallelTestSuite(ParallelTestSuite):
    process_setup = _plain_http_worker_setup


class TestRunner(DiscoverRunner):
    """Keeps the suite on plain HTTP whatever DEBUG is: the SSL redirect
    follows DEBUG (on in CI, which leaves it unset) and would answer every
    test client request with a 301. Secure cookies and HSTS change nothing
    for the test client. Tests of the redirect turn it on themselves."""

    parallel_test_suite = PlainHttpParallelTestSuite

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._plain_http = override_settings(SECURE_SSL_REDIRECT=False)
        self._plain_http.enable()

    def teardown_test_environment(self, **kwargs):
        self._plain_http.disable()
        super().teardown_test_environment(**kwargs)
