# Review: ui-polish

## Verdict: PASS

This is a re-review after the FAIL of 2026-10-04 (base `796807c`, the `docs(ui-polish): review findings` commit). It covers plan steps 23–27 (the earlier findings), 28a (a deliberate test narrowing), and 28–29: the CSS-only theme switch (AC29), added at the user's request after the first review. All five earlier findings are resolved. The Playwright pass is now clean in both colour schemes at all three widths. The security review found nothing. The code review left three low findings, which are recorded below and don't block. Suite: 538 tests OK. `ruff check` and `ruff format --check` are clean, and `makemigrations --check` reports no changes.

## Acceptance criteria
- AC1: covered by `core.tests.test_theme.TailwindSourceTests`. A build from a clean detached worktree of `73dca55` produced a 112,100-byte stylesheet. It contains `.btn`, `.drawer-toggle`, `.alert-error`, `.input-error`, `.badge-success`, `.progress-primary`, `companion-dark`, `prefers-color-scheme:dark`, the `theme-controller[value=companion]` selector, `has-checked:bg-primary` and the `.menu :where(a,button):focus-visible` rule. PASS
- AC2: themes covered by `core.tests.test_theme.ThemeTests`. The faded daisyUI text is pinned by `core.tests.test_layout.FadedTextTests` and the menu focus outline by `test_theme.FocusStyleTests`. The Playwright contrast audit found no text below AA in either theme (details below). PASS
- AC3: covered by `ThemeTests.test_every_content_colour_reaches_aa_contrast_on_its_background`, `test_every_colour_is_inside_the_srgb_gamut` and `ContrastHelperTests`. PASS
- AC4: covered by `core.tests.test_layout.SkipLinkTests`. PASS
- AC5: covered by `PageStructureTests.test_every_page_has_one_header_one_main_and_one_footer` and `test_every_nav_has_an_accessible_name`. PASS
- AC6: covered by `accounts.tests.test_nav.NavCurrentPageTests`. PASS
- AC7: covered by `accounts.tests.test_nav.NavDrawerTests`, including the new `test_the_drawer_side_comes_between_the_toggle_and_the_page_content`. PASS
- AC8: covered by `NavDrawerTests.test_log_out_is_a_post_form_inside_the_drawer_nav`, `NavTests` and `accounts.tests.test_logout`. PASS
- AC9: covered by `core.tests.test_layout.MessageTests`. PASS
- AC10: covered by `core.tests.test_layout.PageTitleTests`. PASS
- AC11: covered by `PageStructureTests.test_every_page_has_exactly_one_h1` and `test_heading_levels_never_skip`. PASS
- AC12: covered by `core.tests.test_favicon.FaviconLinkTests`. PASS
- AC13: covered by `core.tests.test_favicon.FaviconRouteTests`. PASS
- AC14: covered by `core.tests.test_forms.StyledFormRenderingTests` and the new `StyledBoundFieldTests`. PASS
- AC15: covered by `core.tests.test_forms.FormErrorTests` and `StyledBoundFieldTests.test_a_field_with_errors_gets_its_widgets_error_class`. PASS
- AC16: covered by `StyledFormRenderingTests.test_help_text_stays_linked_to_its_field`. PASS
- AC17: covered by `core.tests.test_forms.AdminFormsUnchangedTests` (goal add/change and now the user change page with its profile inline) and the existing `*/tests/test_admin.py`. PASS
- AC18: covered by `core.tests.test_layout.ButtonTests`. PASS
- AC19: covered by `goals.tests.test_views.GoalStatusBadgeTests`. PASS
- AC20: covered by `learning_sessions.tests.test_views.SessionTagPillTests` and `profiles.tests.test_views.FocusAreaPillTests`. PASS
- AC21: covered by `core.tests.test_empty_states.EmptyStateTests`. PASS
- AC22: covered by `dashboard.tests.test_views.DashboardBarTests` and `DashboardQueryCountTests` (still 5 queries). PASS
- AC23: covered by `core.tests.test_layout.TableWrapperTests`. PASS
- AC24: covered by `core.tests.test_home.HomeCallToActionTests`. PASS
- AC25: covered by `goals.tests.test_views.GoalDetailCardTests`, including the new `test_resource_titles_wrap_between_words_not_inside_them`. PASS
- AC26: the full suite of 538 tests is OK, lint is clean, there are no migrations and every `assertNumQueries` pin is unchanged. Three existing tests were narrowed deliberately, each in its own commit with its intent kept: step 7 (profile checkbox), step 20a (home page) and step 28a. In 28a, the resource form's field check is scoped to `<main>`; the code reviewer judged it fair, because it still catches an extra or missing form field. PASS
- AC27: the Playwright pass below is clean. PASS
- AC28: `CLAUDE.md` and `README.md` were updated in `24a385f` and `5f189e7`, which adds the theme switch, the menu focus outline, the full-colour faded text and the drawer order. PASS
- AC29: covered by `core.tests.test_layout.ThemeSwitchTests`: three `theme-controller` radios with their values and names in order, only System checked, inside a fieldset whose legend is "Theme", in the header and outside every `nav`, `main` and `form`. Light beating an OS dark preference and Dark beating an OS light one were checked in the Playwright pass. PASS

### Playwright pass (AC27)
Run against `runserver` on port 8765, with the CSS built from `73dca55` and a scratch copy of the dev database, logged in as a throwaway user with a goal, a tagged session and a resource. It covered 17 page types: the 3 public pages logged out and 14 behind log-in.
- **Overflow, unstyled controls, contrast:** 102 page loads (17 pages × 360/768/1280 px × light/dark). No horizontal page scroll anywhere. Every form control in `<main>` has a border, and every button has `btn` padding. At 1280 px in both schemes, no visible text element is below 4.5:1 (or 3:1 for large text). The dashboard `thead`/`tfoot` text, which was 4.09:1, is now 14.8:1 light and 14.4:1 dark. The inactive filter tabs, which were 3.03:1, are now 13.8:1 light and 15.4:1 dark. The switch's checked label is 6.9:1 light and 6.3:1 dark.
- **Focus visibility:** 286 focus stops across the 14 logged-in pages in both schemes, each tabbed until the cycle repeats (up to 25 stops). Every stop shows an outline or ring. Sidebar links and Log out show a 2 px primary outline, and a focused theme radio outlines its label.
- **Drawer at 360 px** (dashboard and goal page): Tab order is skip link, then the `#nav-drawer` toggle. While closed, `.drawer-side` is hidden. Space opens it, and the next Tab is the first nav link ("Dashboard"; it was the 30th stop before). Space closes it again. At 768 px the sidebar is visible at x=0 and `<main>` starts at x=256.
- **Theme switch:** with the OS light, Dark gives the dark body background, and Light and System give the light one. With the OS dark, Light gives light, and Dark and System give dark. The arrow keys move between the radios and switch the theme. A reload starts at System, as intended (AC29).
- **Screenshots** (in the job scratch folder, not committed): the goal page at 360 px light and with Dark picked, the drawer open at 360 px, and the dashboard at 1280 px with focus on the Light option. The resource title wraps between words.

## Findings
Previous findings (review of `c447ab8`), all resolved:
- [medium] faded `thead`/`tfoot` and inactive tab text: resolved by step 23 (`text-base-content`), pinned by `FadedTextTests`, measured above.
- [medium] faint focus on sidebar menu links: resolved by step 24 (an unlayered `.menu :where(a, button):focus-visible` outline), pinned by `FocusStyleTests`, measured above.
- [medium] drawer focus order: resolved by step 25 (`.drawer-side` before `.drawer-content`), pinned by `NavDrawerTests`, measured above.
- [low] `break-all` on resource titles: resolved by step 26.
- [low] untested `StyledBoundField` paths and the narrow admin check: resolved by step 27.

New (all low, non-blocking):
- [low] `src/core/tests/test_layout.py` (`FadedTextTests`): the exact element count (3 `a`, 1 `tfoot`, 3 `thead`) fails whenever a page legitimately adds a table or a filter tab, and the failure doesn't name the page. Recommendation: when it next changes, assert per page instead. No action now.
- [low] `src/core/tests/test_theme.py` (`FocusStyleTests`): the flat-rule regex wouldn't find the rule if it were later wrapped in `@layer`/`@media`, and it would fail with a bare count message. Recommendation: add an assertion message pointing at `source.css`. No action now.
- [low] `src/templates/components/_theme_option.html`: no test pins the literal `has-checked:`/`has-focus-visible:` classes, so a typo would only show in the Playwright pass. Accepted: visual styling is the Playwright pass's job here, as for the other component classes.
- Security review: no findings (high 0, medium 0, low 0). The radios are outside every form and never submitted, and the template values are autoescaped hard-coded literals.

## Reviewed
commit 73dca55, 2026-10-04 (base 796807c, re-review)
