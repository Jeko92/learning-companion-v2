# Review: setup-layout-tailwind
## Verdict: FAIL

AC9 is only partly proven. The test does not show that `/` is routed through `core/urls.py` *included* in the root URLconf (finding 1). Under the verdict rules, an uncovered acceptance criterion means FAIL, even though the suite is green and no finding is high.

## Acceptance criteria
- AC1 — covered by `core.tests.test_home.HomePageTests.test_home_is_served_by_core_through_core_urls` (status 200) and `test_home_renders_home_template_extending_base` — PASS
- AC2 — covered by `test_templates_load_from_the_project_templates_dir` (guard; mutation check recorded in plan step 4) — PASS
- AC3 — covered by `test_header_and_title_show_the_app_name` — PASS
- AC4 — covered by `test_nav_shows_placeholders_that_are_not_links` (a mutation that turned "Goals" into a link went red) — PASS
- AC5 — covered by `test_layout_renders_messages_added_for_the_request` — PASS
- AC6 — covered by `test_home_fills_the_layout_content_block_with_the_pitch` — PASS
- AC7 — covered by `test_layout_has_a_footer` — PASS
- AC8 — covered by `test_layout_links_the_tailwind_stylesheet_without_a_build`. Green on a fresh `git archive` checkout with no built CSS and no binary, and green with the built CSS moved away — PASS
- AC9 — `core.tests.test_apps.InstalledAppsTests.test_core_app_is_installed` and `test_tailwind_cli_app_is_installed` prove the installed apps. The `include` of `core.urls` at `/` is **not proven** (finding 1) — FAIL

Suite: 32 tests green. `ruff check` and `ruff format --check` clean. `manage.py check` reports no issues.

## Findings
Code review:
1. [medium] src/core/tests/test_home.py:62-69 — The AC9 routing test would still pass if `config/urls.py` replaced `include("core.urls")` with `path("", views.home, name="home")`. `resolve("/").func` and `url_name` are the same either way, and `resolve("/", urlconf="core.urls")` checks `core.urls` on its own, not that the root URLconf includes it. — Assert that the root URLconf (`get_resolver().url_patterns`) contains a `URLResolver` with `urlconf_name == "core.urls"` and an empty pattern. Plan step 13.
2. [low] src/core/tests/test_home.py:15 — `VOID_ELEMENTS` is missing `area`, `col`, `embed`, `track` and `param`. A bare `<area href>` would stay on the open-tag stack, so later text would count as link text and AC4 could fail on valid markup. — Use the full HTML void-element list. Plan step 14.
3. [low] src/core/tests/test_home.py:16, 117-120 — The plan's design decision says the parser collects `<footer>` text, but the implementation checks `seen_tags` instead. That's adequate for AC7, but the deviation isn't recorded. — Add `footer` to `SECTIONS` and make AC7 check the footer section. Plan step 14.
4. [low] src/core/tests/test_home.py:88-89 vs 114 — Whitespace is collapsed only for the `<main>` check. Reformatting a template, for example wrapping the app name across two lines, would turn AC3 or AC4 red with no change in behaviour. — Collapse whitespace in one place in the parser and use it for every section. Plan step 14.
5. [low] src/core/tests/test_home.py:46-52 — Text pieces are joined with no separator (nav text is `"GoalsLog in"`), so a substring could match across element boundaries. — Join pieces with a space, together with finding 4. Plan step 14.

Security review (0 high, 0 medium):
6. [low] src/config/settings.py:128 — The Tailwind binary is downloaded over HTTPS (certificate verified), but there is no checksum or signature check before it is made executable and run. The version pin narrows the risk but does not remove it. — Out of scope for this ticket: verify a pinned SHA-256, or disable the automatic download and provide a verified binary in the `docker` and `ci-tests` tickets. Not a plan step.
7. [low] requirements.txt:3 — The ranged pins and unpinned transitive dependencies (`click`, `django-click`, `semver`) follow the project's existing style, but there is no lock file or hash checking. — Out of scope: add a hashed lock file (`pip-compile --generate-hashes`, `--require-hashes`) with the `ci-tests` or `docker` ticket. Not a plan step.

Also outside this diff: production hardening settings (`SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, secure cookies) belong to the deployment ticket.

## Reviewed
commit 4c87311, 2026-10-02
