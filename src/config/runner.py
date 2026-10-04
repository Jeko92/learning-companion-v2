"""The project's test runner (settings.TEST_RUNNER)."""

from django.test import override_settings
from django.test.runner import DiscoverRunner


class TestRunner(DiscoverRunner):
    """Keeps the suite on plain HTTP whatever DEBUG is: the SSL redirect
    follows DEBUG (on in CI, which leaves it unset) and would answer every
    test client request with a 301. Secure cookies and HSTS change nothing
    for the test client. Tests of the redirect turn it on themselves."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._plain_http = override_settings(SECURE_SSL_REDIRECT=False)
        self._plain_http.enable()

    def teardown_test_environment(self, **kwargs):
        self._plain_http.disable()
        super().teardown_test_environment(**kwargs)
