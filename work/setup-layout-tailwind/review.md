# Review: setup-layout-tailwind
## Verdict: PASS

Round 2 (commit 5576b47). There are no high or medium findings. Every acceptance criterion is proven by a test that can fail, the suite is green, and the round 1 findings 1–5 are resolved by plan steps 13 and 14. The three new low findings and the two deferred security lows don't block the verdict.

## Acceptance criteria
- AC1 — covered by `core.tests.test_home.HomePageTests.test_home_is_served_by_core_through_core_urls` (status 200) and `test_home_renders_home_template_extending_base` — PASS
- AC2 — covered by `test_templates_load_from_the_project_templates_dir` (a guard; its mutation check is recorded in plan step 4) — PASS
- AC3 — covered by `test_header_and_title_show_the_app_name` — PASS
- AC4 — covered by `test_nav_shows_placeholders_that_are_not_links` — PASS (see low finding 8)
- AC5 — covered by `test_layout_renders_messages_added_for_the_request` — PASS
- AC6 — covered by `test_home_fills_the_layout_content_block_with_the_pitch` — PASS
- AC7 — covered by `test_layout_has_a_footer` (now checks the footer's text) — PASS
- AC8 — covered by `test_layout_links_the_tailwind_stylesheet_without_a_build`, green on a fresh `git archive` checkout with no built CSS and no binary — PASS
- AC9 — covered by `core.tests.test_apps.InstalledAppsTests.test_core_app_is_installed`, `test_tailwind_cli_app_is_installed`, `test_home_is_served_by_core_through_core_urls` and `test_root_urlconf_includes_core_urls_at_the_root` — PASS

Suite: 33 tests green. `ruff check` and `ruff format --check` are clean, and `manage.py check` reports no issues.

The code reviewer mutation-tested a scratch copy, and each mutation turned exactly the matching test red:
- the include replaced by a direct `path()`
- the include moved to a non-root prefix
- "Goals" made a link
- the pitch hard-coded in `base.html`, or moved outside `<main>`
- the footer removed
- the messages loop removed
- the app name missing from the `<title>` or the header
- `{% tailwind_css %}` removed

Three harmless changes stayed green, which is correct: the app name wrapped across two lines, a `<map><area href></map>` before the nav, and `include()` given the module object.

## Findings
### Round 2 (commit 5576b47)
Code review (0 high, 0 medium):
8. [low] src/core/tests/test_home.py:129-135 — AC4 checks that the whole placeholder string is absent from the page's link text. A partial link such as `<span><a href="/login">Log</a> in</span>` would stay green. The case is contrived, because the real nav uses plain `<span>`s. — Optional hardening: assert that the link text inside `<nav>` is empty. This can be picked up by the auth tickets, which turn these placeholders into real links anyway.
9. [low] src/core/tests/test_home.py:40-41 — The `collapse()` docstring says "text can't match across elements". Joining with a space only stops pieces from gluing together. — Reword it to "so text from adjacent elements isn't glued together".
10. [low] README.md:18 — "run the build after every checkout" is imprecise, because `git checkout` doesn't delete ignored files. — Reword it to "after cloning, and whenever templates change unless `tailwind runserver` is running".

Security review (0 high, 0 medium, 0 new low): findings 6 and 7 still stand and remain deferred.

### Round 1 (commit 4c87311): verdict FAIL, resolved
1. [medium] The AC9 include was not proven. Resolved by plan step 13 (`test_root_urlconf_includes_core_urls_at_the_root`).
2. [low] The void-element list was incomplete. Resolved by plan step 14.
3. [low] AC7 checked `seen_tags` instead of the footer's text, and the deviation was not recorded. Resolved by plan step 14.
4. [low] Whitespace was collapsed only for the `<main>` check. Resolved by plan step 14, which adds a single `collapse()` helper.
5. [low] Text pieces were glued together without a separator. Resolved by plan step 14 (see finding 9 for the docstring wording).
6. [low] src/config/settings.py:128 — The Tailwind binary is downloaded over HTTPS (certificate verified), but nothing checks its integrity (no SHA-256 or signature). Deferred to the `docker` and `ci-tests` tickets: verify a pinned SHA-256, or disable the automatic download and supply a verified binary.
7. [low] requirements.txt:3 — The dependencies are ranged, and the transitive ones (`click`, `django-click`, `semver`) are not pinned. There is no lock file or hash checking. Deferred to the `ci-tests` and `docker` tickets: a hashed lock file installed with `--require-hashes`.

Outside this diff: production hardening settings (`SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, secure cookies) belong to the deployment ticket.

## Reviewed
commit 5576b47, 2026-10-02 (round 1: commit 4c87311, FAIL)
