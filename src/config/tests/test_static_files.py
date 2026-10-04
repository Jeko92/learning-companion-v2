import tempfile
import warnings
from pathlib import Path

from django.core.management import call_command
from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings
from whitenoise.middleware import WhiteNoiseMiddleware


class CollectedStaticFilesTests(SimpleTestCase):
    """With DEBUG off (as in tests and the container), WhiteNoise serves what
    collectstatic gathered, gzipped for clients that accept it."""

    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.enterContext(override_settings(STATIC_ROOT=tmp_dir.name))
        call_command("collectstatic", interactive=False, verbosity=0)

    def test_a_collected_file_is_served_gzipped_when_the_client_accepts_it(self):
        response = self.client.get("/static/favicon.svg", HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Encoding"], "gzip")

    def test_a_collected_file_is_served_plain_otherwise(self):
        response = self.client.get("/static/favicon.svg")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Encoding", response.headers)
        self.assertEqual(response.headers["Content-Type"], "image/svg+xml")

    def test_static_urls_keep_their_plain_names(self):
        self.assertEqual(static("css/tailwind.css"), "/static/css/tailwind.css")


class MissingStaticRootTests(SimpleTestCase):
    """Local runs and the test suite never run collectstatic, so STATIC_ROOT
    doesn't exist there; WhiteNoise's warning about it is filtered out."""

    def test_a_missing_static_root_gives_no_warning(self):
        missing = Path(tempfile.gettempdir()) / "no-such-static-root"
        # record=True keeps the active filters (and clears the once-only
        # registry), so this sees what a real start-up would print.
        with (
            override_settings(STATIC_ROOT=missing),
            warnings.catch_warnings(record=True) as caught,
        ):
            WhiteNoiseMiddleware(get_response=lambda request: None)

        self.assertEqual([str(w.message) for w in caught], [])
