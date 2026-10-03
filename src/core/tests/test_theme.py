import hashlib
import math
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


THEME_BLOCK = re.compile(r'@plugin "\./daisyui-theme\.mjs"\s*\{(.*?)\}', re.S)
DECLARATION = re.compile(r"([\w-]+)\s*:\s*([^;]+);")
OKLCH = re.compile(r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)")

COLOURS = ("primary", "secondary", "accent", "neutral", "info", "success", "warning", "error")
REQUIRED = (
    "--color-base-100",
    "--color-base-200",
    "--color-base-300",
    "--color-base-content",
    *(f"--color-{name}" for name in COLOURS),
    *(f"--color-{name}-content" for name in COLOURS),
    "--radius-selector",
    "--radius-field",
    "--radius-box",
    "--size-selector",
    "--size-field",
    "--border",
    "--depth",
    "--noise",
)
# (text, background) pairs that must reach WCAG AA for normal text.
CONTRAST_PAIRS = (
    *(("base-content", base) for base in ("base-100", "base-200", "base-300")),
    *((f"{name}-content", name) for name in COLOURS),
)


def themes():
    """Each custom daisyUI theme in the source stylesheet, as {name: value}."""
    css = source_css_path().read_text()
    return [
        {key: value.strip().strip('"') for key, value in DECLARATION.findall(block)}
        for block in THEME_BLOCK.findall(css)
    ]


def theme(name):
    (found,) = [t for t in themes() if t.get("name") == name]
    return found


def oklch(value):
    match = OKLCH.fullmatch(value)
    if not match:
        raise AssertionError(f"not an oklch() colour: {value}")
    lightness, chroma, hue = map(float, match.groups())
    return lightness / 100, chroma, hue


def linear_srgb(value):
    """The linear sRGB channels of an oklch() colour, unclipped."""
    lightness, chroma, hue = oklch(value)
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    lms = (
        (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3,
        (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3,
        (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3,
    )
    rows = (
        (4.0767416621, -3.3077115913, 0.2309699292),
        (-1.2684380046, 2.6097574011, -0.3413193965),
        (-0.0041960863, -0.7034186147, 1.7076147010),
    )
    return [sum(k * c for k, c in zip(row, lms, strict=True)) for row in rows]


def luminance(value):
    """WCAG relative luminance of an oklch() colour (clipped to sRGB)."""
    red, green, blue = (min(max(c, 0.0), 1.0) for c in linear_srgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first, second):
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class ContrastHelperTests(SimpleTestCase):
    """The test's own colour maths matches known values."""

    def test_black_on_white_is_21_to_1(self):
        self.assertAlmostEqual(contrast("oklch(0% 0 0)", "oklch(100% 0 0)"), 21, places=1)

    def test_known_srgb_colours_match_their_published_contrast(self):
        # #0000ff on white is 8.59:1 and #777777 on white is 4.48:1.
        white = "oklch(100% 0 0)"
        self.assertAlmostEqual(contrast("oklch(45.2% 0.313 264.052)", white), 8.59, 2)
        self.assertAlmostEqual(contrast("oklch(56.93% 0 0)", white), 4.48, 2)


class ThemeTests(SimpleTestCase):
    """A light default theme and a dark one that follows the OS setting."""

    def test_there_are_exactly_two_custom_themes(self):
        self.assertEqual(
            sorted(t.get("name") for t in themes()), ["companion", "companion-dark"]
        )

    def test_the_built_in_themes_are_switched_off(self):
        self.assertRegex(
            source_css_path().read_text(),
            r'@plugin "\./daisyui\.mjs"\s*\{\s*themes:\s*false;\s*\}',
        )

    def test_the_light_theme_is_the_default(self):
        light = theme("companion")
        self.assertEqual(light["default"], "true")
        self.assertEqual(light["prefersdark"], "false")
        self.assertEqual(light["color-scheme"], "light")

    def test_the_dark_theme_follows_prefers_color_scheme(self):
        dark = theme("companion-dark")
        self.assertEqual(dark["default"], "false")
        self.assertEqual(dark["prefersdark"], "true")
        self.assertEqual(dark["color-scheme"], "dark")

    def test_each_theme_defines_every_variable(self):
        for each in themes():
            for variable in REQUIRED:
                with self.subTest(theme=each["name"], variable=variable):
                    self.assertIn(variable, each)

    def test_the_primary_colour_is_indigo_or_violet(self):
        for each in themes():
            with self.subTest(theme=each["name"]):
                _, chroma, hue = oklch(each["--color-primary"])
                self.assertGreater(chroma, 0.1)
                self.assertTrue(260 <= hue <= 300, hue)

    def test_every_colour_is_inside_the_srgb_gamut(self):
        # Outside sRGB, browsers gamut-map differently per display, so the
        # contrast computed below would not be the contrast people see.
        for each in themes():
            for variable, value in each.items():
                if variable.startswith("--color-"):
                    with self.subTest(theme=each["name"], variable=variable):
                        for channel in linear_srgb(value):
                            self.assertTrue(-0.001 <= channel <= 1.001, value)

    def test_every_content_colour_reaches_aa_contrast_on_its_background(self):
        for each in themes():
            for text, background in CONTRAST_PAIRS:
                with self.subTest(theme=each["name"], pair=(text, background)):
                    ratio = contrast(
                        each[f"--color-{text}"], each[f"--color-{background}"]
                    )
                    self.assertGreaterEqual(ratio, 4.5)
