# Review: ui-polish

## Verdict: FAIL

AC2 is not met in the rendered UI. The light theme's own colours pass the unit-tested contrast pairs (AC3), but daisyUI fades two components on top of them: the dashboard table headers and footer, and the inactive goal-filter tabs. Both measure below 4.5:1. The Playwright pass also found two keyboard issues that AC2 and AC27 are about: a faint focus indicator on the sidebar links, and the focus order of the open mobile drawer. The suite is green, and the security review found nothing. The findings below are new plan steps 23–27.

## Acceptance criteria
- AC1: covered by `core.tests.test_theme.TailwindSourceTests`. A build from a clean detached worktree of `c447ab8` downloaded the pinned binary and produced a 111,497-byte stylesheet (the same size as the local one) with `.btn`, `.drawer-toggle`, `.alert-error`, `.input-error`, `.badge-success`, `.progress-primary`, `companion-dark` and `prefers-color-scheme:dark`. PASS
- AC2: themes covered by `core.tests.test_theme.ThemeTests`. PASS for the theme definition, but **FAIL in the rendered light theme**: the Playwright contrast audit measured the dashboard `thead`/`tfoot` text at 4.09:1 and the inactive filter tabs at 3.03:1 (see Findings). FAIL
- AC3: covered by `ThemeTests.test_every_content_colour_reaches_aa_contrast_on_its_background`, `test_every_colour_is_inside_the_srgb_gamut` and `ContrastHelperTests`. PASS
- AC4: covered by `core.tests.test_layout.SkipLinkTests`. PASS
- AC5: covered by `PageStructureTests.test_every_page_has_one_header_one_main_and_one_footer` and `test_every_nav_has_an_accessible_name`. PASS
- AC6: covered by `accounts.tests.test_nav.NavCurrentPageTests`. PASS
- AC7: covered by `accounts.tests.test_nav.NavDrawerTests`. PASS
- AC8: covered by `NavDrawerTests.test_log_out_is_a_post_form_inside_the_drawer_nav`, `NavTests` and `accounts.tests.test_logout`. PASS
- AC9: covered by `core.tests.test_layout.MessageTests`. PASS
- AC10: covered by `core.tests.test_layout.PageTitleTests`. PASS
- AC11: covered by `PageStructureTests.test_every_page_has_exactly_one_h1` and `test_heading_levels_never_skip`. PASS
- AC12: covered by `core.tests.test_favicon.FaviconLinkTests`. PASS
- AC13: covered by `core.tests.test_favicon.FaviconRouteTests`. PASS
- AC14: covered by `core.tests.test_forms.StyledFormRenderingTests` (class, label and fieldset tests). PASS
- AC15: covered by `core.tests.test_forms.FormErrorTests`. PASS
- AC16: covered by `StyledFormRenderingTests.test_help_text_stays_linked_to_its_field`. PASS
- AC17: covered by `core.tests.test_forms.AdminFormsUnchangedTests` and the existing `*/tests/test_admin.py`. PASS
- AC18: covered by `core.tests.test_layout.ButtonTests`. PASS
- AC19: covered by `goals.tests.test_views.GoalStatusBadgeTests`. PASS
- AC20: covered by `learning_sessions.tests.test_views.SessionTagPillTests` and `profiles.tests.test_views.FocusAreaPillTests`. PASS
- AC21: covered by `core.tests.test_empty_states.EmptyStateTests`. PASS
- AC22: covered by `dashboard.tests.test_views.DashboardBarTests` and `DashboardQueryCountTests` (still 5 queries). PASS
- AC23: covered by `core.tests.test_layout.TableWrapperTests`. PASS
- AC24: covered by `core.tests.test_home.HomeCallToActionTests`. PASS
- AC25: covered by `goals.tests.test_views.GoalDetailCardTests`. PASS
- AC26: full suite 526 tests OK, `ruff check` and `ruff format --check` clean, `makemigrations --check` reports no changes, and every `assertNumQueries` pin is unchanged. PASS
- AC27: Playwright pass on the dev server with the built CSS (details below). The overflow, styling and drawer-toggle checks pass; the focus visibility and drawer focus order findings are open. FAIL
- AC28: `CLAUDE.md` and `README.md` updated in `24a385f`; the README's favicon regeneration commands were re-run and reproduce the committed ICO byte for byte. PASS

### Playwright pass (AC27)
Run against `runserver` on port 8765 with the dev database (logged in as alice). It covered 17 page types: the 3 public pages and 14 behind log-in.
- **Overflow and unstyled controls:** 102 page loads (17 pages × 360/768/1280 px × light/dark). No horizontal page scroll anywhere. Every form control in `<main>` has a visible border, and every button has `btn` padding. The dark theme applies through `prefers-color-scheme` (body `oklch(0.175 0.03 266)` against `oklch(0.975 0.006 255)` in light).
- **Text contrast (1280 px, 15 logged-in pages, both schemes):** the dark theme has no failures. In the light theme, the dashboard `thead`/`tfoot` text is 4.09:1 and the inactive filter tabs are 3.03:1.
- **Focus visibility (Tab through each page, up to 25 stops):** 164 focus stops were checked. All buttons, form controls, tabs and content links show an outline. The inactive sidebar menu links only get a very faint background (about 1.1:1 against white).
- **Drawer at 360 px:** Tab order is skip link, then the `#nav-drawer` toggle ("Menu", with a 2 px outline on the menu button), then the page. Space opens the drawer (`.drawer-side` becomes visible) and Space closes it again. While closed, no nav link takes focus. While open, the first nav link is the **30th** Tab stop, because `.drawer-side` comes after all the page content in the DOM.
- **Screenshots** (in the job scratch folder, not committed): the drawer open at 360 px light, the goal page at 360 px dark, the dashboard at 1280 px dark, and the goal list at 1280 px light with focus on a sidebar link. Visually: cards, badges, pills, empty states and progress bars render as intended in both themes. On mobile, long resource titles break mid-word.

## Findings
- [medium] `src/templates/dashboard/dashboard.html` (`thead`/`tfoot` of the three tables): daisyUI's `.table` fades header and footer text, giving 4.09:1 in the light theme, below the 4.5:1 AC2 requires. Recommendation: give the header and footer rows full `base-content` colour, and pin it with a template-level test. Plan step 23.
- [medium] `src/templates/goals/goal_list.html` (inactive `.tab` links): daisyUI's inactive tab text is 3.03:1 in the light theme. Recommendation: the same fix for the inactive tabs, pinned in step 23.
- [medium] `src/templates/base.html` (sidebar `.menu` links): keyboard focus on an inactive link shows only a faint background change (about 1.1:1), not a visible indicator (AC2 and AC27, WCAG 2.4.7/1.4.11). Recommendation: a clear `:focus-visible` outline on menu links and buttons, for example in `src/tailwind/source.css`. Plan step 24.
- [medium] `src/templates/base.html`: `.drawer-side` follows `.drawer-content`, so after opening the drawer with Space, keyboard users tab through about 29 covered page elements before reaching the first nav link (WCAG 2.4.3 focus order). Recommendation: move `.drawer-side` right after the toggle, before `.drawer-content`. daisyUI places both in the same grid cell, and its `.drawer-toggle:checked ~ .drawer-side` selector still matches. Check the desktop sidebar and the mobile drawer again in the re-review. Plan step 25.
- [low] `src/templates/goals/goal_detail.html` (resource title link): `break-all` splits titles mid-word on narrow screens ("offic/ial"). Recommendation: `break-words` for the title; the delete page's raw URL keeps `break-all`. Plan step 26.
- [low] `src/core/forms.py:32-48`: the class merge with a widget's own `class`, the hidden-widget skip and the `select-error`/`textarea-error`/`checkbox-error` variants have no direct test (only `input-error` is asserted). Recommendation: a `SimpleTestCase` with an ad-hoc `StyledFormMixin` form. Plan step 27.
- [low] `src/core/tests/test_forms.py` (`AdminFormsUnchangedTests`): only the goals admin is checked under the new `TemplatesSetting` renderer. Recommendation: also check the user change page (profile inline, tag autocomplete). Plan step 27.
- [low] `src/profiles/tests/test_views.py:322-328` (step 7) and `src/core/tests/test_home.py:104-110` (step 20a): the two deliberately narrowed tests keep their intent; `HomeCallToActionTests` covers what 20a dropped. Accepted, no action.
- [low] `src/templates/base.html` and `src/assets/favicon.svg`: `theme-color` and the favicon fill hard-code the light primary (`#4b31ee`), and the dark theme keeps it. Accepted: the icon is the brand mark and the browser-chrome tint is cosmetic.
- [low] `src/templates/base.html`: with no JavaScript, the drawer has no Escape-to-close and no focus trap. Accepted limitation of the CSS-only drawer (ticket notes). Step 25 fixes the focus order, which is the part that hurts keyboard users.
- [low] `src/core/views.py` (`favicon`): it returns a 500 if the committed `favicon.ico` is missing. The file is pinned by tests; no action.
- Security review: no findings (high 0, medium 0, low 0).

## Reviewed
commit c447ab8, 2026-10-04 (base 5e4e556)
