import struct
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from core.tests.pages import AllPagesMixin

ASSETS = Path(settings.STATICFILES_DIRS[0])


def png_size(data):
    """(width, height) from a PNG's IHDR chunk."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def ico_sizes(data):
    """The (width, height) of each image in an ICO file (0 means 256)."""
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1), "not an ICO"
    return [tuple(data[6 + 16 * i : 8 + 16 * i]) for i in range(count)]


class FaviconLinkTests(AllPagesMixin, TestCase):
    """Every page points browsers at the app's own icons."""

    def icon_links(self, parser):
        return [
            (attrs.get("rel"), attrs.get("href"), attrs.get("type"), attrs.get("sizes"))
            for tag, attrs in parser.elements
            if tag == "link" and "icon" in attrs.get("rel", "")
        ]

    def test_every_page_links_the_svg_ico_and_apple_touch_icons(self):
        for page, parser in self.walk():
            with self.subTest(page=page.name):
                self.assertEqual(
                    self.icon_links(parser),
                    [
                        ("icon", "/static/favicon.ico", None, "32x32"),
                        ("icon", "/static/favicon.svg", "image/svg+xml", None),
                        (
                            "apple-touch-icon",
                            "/static/apple-touch-icon.png",
                            None,
                            None,
                        ),
                    ],
                )

    def test_the_svg_icon_is_a_committed_svg(self):
        svg = (ASSETS / "favicon.svg").read_text()
        self.assertIn("<svg", svg)
        self.assertIn('viewBox="0 0 32 32"', svg)

    def test_the_apple_touch_icon_is_a_180_pixel_square_png(self):
        self.assertEqual(
            png_size((ASSETS / "apple-touch-icon.png").read_bytes()), (180, 180)
        )

    def test_the_ico_holds_16_32_and_48_pixel_images(self):
        self.assertEqual(
            ico_sizes((ASSETS / "favicon.ico").read_bytes()),
            [(16, 16), (32, 32), (48, 48)],
        )


class FaviconRouteTests(TestCase):
    """Browsers and tools that ask for /favicon.ico get the real icon."""

    def test_favicon_ico_serves_the_committed_icon_to_anyone(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            response["Content-Type"], ("image/x-icon", "image/vnd.microsoft.icon")
        )
        self.assertEqual(
            b"".join(response.streaming_content),
            (ASSETS / "favicon.ico").read_bytes(),
        )

    def test_favicon_ico_may_be_cached_for_a_day(self):
        response = self.client.get("/favicon.ico")

        self.assertIn("max-age=86400", response["Cache-Control"])
        self.assertIn("public", response["Cache-Control"])
