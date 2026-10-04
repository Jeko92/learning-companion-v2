from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings


@override_settings(SECURE_SSL_REDIRECT=True)
class SslRedirectTests(TestCase):
    """The suite runs with the redirect off (config.runner); these turn it on,
    as it is in production."""

    def test_a_plain_http_page_request_is_redirected_to_https(self):
        response = self.client.get("/accounts/login/?next=/goals/")

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"], "https://testserver/accounts/login/?next=/goals/"
        )

    def test_an_https_request_is_not_redirected(self):
        response = self.client.get("/accounts/login/", secure=True)

        self.assertEqual(response.status_code, 200)

    def test_the_favicon_is_served_over_plain_http(self):
        # The container's HEALTHCHECK requests it over HTTP; urllib would
        # follow a redirect to https://, which gunicorn doesn't serve.
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 200)

    def test_only_the_favicon_itself_is_exempt(self):
        for path in (
            "/favicon.ico/",
            "/static/favicon.ico",
            "/favicon.icon",
            "/favicon.ico%0A",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 301)


@override_settings(SECURE_HSTS_SECONDS=3600)
class HstsTests(TestCase):
    """Django's SecurityMiddleware sends the header; these pin its shape."""

    def test_an_https_response_carries_hsts_without_subdomains_or_preload(self):
        response = self.client.get("/", secure=True)

        self.assertEqual(response["Strict-Transport-Security"], "max-age=3600")

    def test_a_plain_http_response_carries_no_hsts(self):
        response = self.client.get("/")

        self.assertNotIn("Strict-Transport-Security", response)


class HstsScopeSettingsTests(SimpleTestCase):
    def test_hsts_covers_neither_subdomains_nor_the_preload_list(self):
        # Both commit the whole domain, beyond this app: out of scope.
        self.assertIs(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS, False)
        self.assertIs(settings.SECURE_HSTS_PRELOAD, False)
