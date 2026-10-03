import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

VENDORED = ("daisyui.mjs", "daisyui-theme.mjs")


def source_css_path():
    return Path(settings.BASE_DIR) / settings.TAILWIND_CLI_SRC_CSS


class TailwindSourceTests(SimpleTestCase):
    """The Tailwind build reads a committed stylesheet that loads daisyUI."""

    def test_the_source_stylesheet_setting_points_to_an_existing_file(self):
        self.assertTrue(source_css_path().is_file())

    def test_the_source_stylesheet_is_not_published_as_a_static_file(self):
        assets = Path(settings.STATICFILES_DIRS[0]).resolve()
        self.assertNotIn(assets, source_css_path().resolve().parents)

    def test_the_source_stylesheet_loads_the_vendored_daisyui_plugin(self):
        css = source_css_path().read_text()
        self.assertIn('@import "tailwindcss";', css)
        self.assertIn('@plugin "./daisyui.mjs"', css)

    def test_the_vendored_plugin_files_are_not_scanned_for_classes(self):
        self.assertIn('@source not "./daisyui{,*}.mjs";', source_css_path().read_text())

    def test_the_vendored_files_match_the_sha256_recorded_in_the_stylesheet(self):
        css = source_css_path().read_text()
        recorded = dict(re.findall(r"sha256 (\S+\.mjs): ([0-9a-f]{64})", css))
        self.assertEqual(set(recorded), set(VENDORED))
        for name in VENDORED:
            with self.subTest(name=name):
                data = (source_css_path().parent / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), recorded[name])

    def test_the_stylesheet_records_the_daisyui_version(self):
        css = source_css_path().read_text()
        self.assertRegex(css, r"daisyUI \d+\.\d+\.\d+")
