# Review: login-required-default
## Verdict: PASS

Review base `7f108fd` (merge-base with `origin/develop`), first review, all 9 plan steps in scope (steps 3–8 done as one cycle at the user's request, recorded in `plan.md`). Full suite: 662 tests OK; `ruff check` and `ruff format --check` clean; `makemigrations --check --dry-run`: no changes.

## Acceptance criteria
- AC1 — covered by `config.tests.test_settings.LoginRequiredSettingsTests.test_login_required_middleware_comes_right_after_authentication`, plus the existing pins `StaticFilesSettingsTests.test_whitenoise_middleware_comes_right_after_the_security_middleware` and `accounts.tests.test_lockout.LockoutWiringTests.test_the_app_and_its_middleware_are_installed` — PASS
- AC2 — covered by `core.tests.test_login_required.UnprotectedViewTests` (`test_anonymous_visitors_are_sent_to_log_in`, `test_logged_in_users_get_the_view`) — PASS
- AC3 — covered by `core.tests.test_home.HomePageTests.test_home_is_public_under_the_login_required_middleware`, `core.tests.test_login_required.PublicPagesTests.test_public_pages_answer_anonymous_get_requests` and the existing anonymous home tests — PASS
- AC4 — covered by `core.tests.test_favicon.FaviconRouteTests` (`test_favicon_ico_is_public_under_the_login_required_middleware`, `test_favicon_ico_answers_an_anonymous_head_request`, `test_favicon_ico_serves_the_committed_icon_to_anyone`, `test_favicon_ico_may_be_cached_for_a_day`) and `PublicPagesTests.test_the_favicon_answers_an_anonymous_head_request` — PASS
- AC5 — covered by `accounts.tests.test_signup.SignUpPageTests.test_signup_is_public_under_the_login_required_middleware`, `PublicPagesTests.test_public_pages_answer_anonymous_get_requests` and the existing `SignUpSubmitTests` / `SignUpLoggedInTests`, all run under the middleware — PASS
- AC6 — covered by `core.tests.test_login_required.LoginRequiredRouteTests.test_only_the_allow_listed_routes_are_public` (`accounts:login` exempt through Django's `LoginView`, no new decorator), `PublicPagesTests` and the existing `accounts.tests.test_login` tests — PASS
- AC7 — covered by `accounts.tests.test_logout.LogoutTests.test_logout_is_public_under_the_login_required_middleware`, the existing `test_anonymous_logout_redirects_without_the_message` and the GET-405 test, and `PublicPagesTests.test_an_anonymous_log_out_lands_on_the_home_page` — PASS
- AC8 — covered by the existing `accounts.tests.test_lockout.LockoutPageTests` (incl. `test_the_admin_log_in_is_locked_out_the_same_way`) and the "locked out" page in `core/tests/pages.py`, green under the middleware — PASS
- AC9 — covered by `core.tests.test_login_required.AdminLoginRequiredTests` (admin index → `/admin/login/?next=/admin/`, model admin page → `/accounts/login/?next=/admin/goals/goal/`, `/admin/login/` 200) — PASS
- AC10 — covered by `core.tests.test_login_required.LoginRequiredRouteTests` (exact exempt set == `PUBLIC_ROUTES`; every other non-admin route redirects an anonymous GET to log-in, with a non-vacuity guard) — PASS
- AC11 — no `LoginRequiredMixin` removed; no existing test changed (the diff only adds tests); every existing anonymous-redirect test passes in the full suite — PASS
- AC12 — `CLAUDE.md` (Auth "Login required by default" bullet, favicon note, Layout) and `README.md` (auth paragraph) updated — PASS

## Findings
None.
- code-reviewer: 0 high / 0 medium / 0 low. Four mutations (middleware removed; decorator removed from home+favicon, from `SignUpView`, from `LogOutView`) each turned the targeted modules red. Walker recursion, namespacing and the scoped `ROOT_URLCONF` override checked; no URL-cache leakage. Accepted limitations, by design: an unknown path converter is a `KeyError` in `sample_path` (a new converter gets a sample on purpose), and a non-admin `re_path` would need walker support.
- security-reviewer: 0 findings. CSRF still precedes the redirect; the exemptions take effect on `dispatch` and don't leak; anonymous log-out is POST-only with CSRF, as before; `next` is only followed through `LogInView`'s same-site check; the admin still checks staff and permissions after the app log-in; unresolved paths stay 404.

## Reviewed
commit eacc47b, 2026-10-04
