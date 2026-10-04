# Review: deploy-hardening

## Verdict: PASS

**Re-review (2026-10-04, e0f353b..3444e66, plan steps 20-24):** all four findings of the first review are resolved, checked by both reviewers with targeted mutations (each fix reverted → its test fails):
- 1, medium, `--parallel` workers: `PlainHttpParallelTestSuite.process_setup`.
- 2, low, runner teardown guard.
- 3, low, casefolded `AXES_USERNAME_CALLABLE`.
- 4, info, `\Z` in the favicon exemption.

AC16 now holds:
- 646 tests OK with `DEBUG` from `.env`.
- 646 tests OK with `DEBUG=False --parallel 4`.

Checks are clean: `ruff check`, `ruff format --check`, `makemigrations --check`. No high or medium findings remain.

One new info finding, not fixed here (a follow-up, reported to the user):
- [info] `src/accounts/lockout.py` — **The username reset command needs a lower-case name.** Attempts are now stored under the casefolded username, but `axes_reset_username <name>` matches the name exactly. `axes_reset_username Alice` therefore clears nothing; the operator has to pass `alice`, or use `axes_reset`. This only affects operators and can't be exploited. — Recommendation: the README should say to pass the name in lower case.

Steps 21-24 were made in one batch at the user's request, with a single suite run at the end, not a red run per step. The re-review's mutations confirm each new test fails without its fix.

## First review (2026-10-04): FAIL

AC16 promises a test suite that passes whatever `DEBUG` is. It does not hold for `manage.py test --parallel`. The code reviewer reproduced it: `DEBUG=False … test accounts.tests.test_login accounts.tests.test_nav --parallel 2` errors in the workers, while the same command with `DEBUG=True` passes. CI and the hooks don't run `--parallel`, so they are green. But `--parallel` is a standard runner option, and the criterion is "whatever DEBUG is", so I am not passing it with this caveat. The other findings are low/info and go back with it.

## Acceptance criteria

- AC1 — django-axes pinned, installed and wired — `accounts/tests/test_lockout.py` `LockoutWiringTests` — PASS
- AC2 — after 5 failures even the right password is refused (429, no session) — `LockoutTests.test_after_five_failures_even_the_right_password_is_refused` — PASS
- AC3 — lockout per username + IP — `LockoutTests.test_a_locked_out_username_can_still_log_in_from_another_ip`, `test_another_username_can_still_log_in_from_a_locked_out_ip`, `test_the_lockout_is_per_username_and_ip_address` — PASS
- AC4 — 429 page extending `base.html` (title, one `<h1>`, message) and covered by the site-wide page checks — `LockoutPageTests.test_the_lockout_page_says_when_to_try_again`, plus the "locked out" page in `core/tests/pages.py` (`test_layout`, `test_favicon`, `test_nav` walks) — PASS
- AC5 — a missing username is counted the same way, and the page names no account — `LockoutTests.test_after_five_failures…` (subTest "nobody"), `LockoutPageTests.test_the_lockout_page_names_no_account` — PASS
- AC6 — lifts 15 minutes after the last failure — `CoolOffTests.test_still_locked_out_14_minutes_after_the_last_failure`, `test_the_right_password_logs_in_15_minutes_after_the_last_failure` — PASS
- AC7 — a successful log-in resets the count — `ResetOnSuccessTests.test_failures_before_a_successful_log_in_no_longer_count` — PASS
- AC8 — the admin log-in is covered — `LockoutPageTests.test_the_admin_log_in_is_locked_out_the_same_way` — PASS
- AC9 — limit, cool-off, parameters, handler and status pinned — `LockoutTests.test_the_failure_limit_is_five`, `test_the_lockout_is_per_username_and_ip_address`, `CoolOffTests.test_the_cool_off_matches_the_lockout_page`, `ResetOnSuccessTests.test_a_successful_log_in_resets_the_count`, `LockoutWiringTests.test_failures_are_stored_in_the_database_and_refused_with_429` — PASS
- AC10 — HTTPS settings on without `DEBUG` (HSTS 3600), off with it — `config/tests/test_env.py` (ssl redirect, cookies, HSTS) and `test_settings.py` `test_https_settings_are_on_by_default_without_debug` / `…off_by_default_with_debug` — PASS
- AC11 — explicit env values win, blank means default, invalid values raise naming the variable — `test_env.py` `test_an_explicit_ssl_redirect_wins…`, `test_an_unknown_ssl_redirect_value_raises`, `test_secure_cookies_follow_the_same_rules…`, `test_explicit_hsts_seconds_win…`, `test_hsts_seconds_that_are_not_a_whole_number…` — PASS
- AC12 — proxy header opt-in — `test_env.py` `test_the_proxy_ssl_header_is_opt_in_whatever_debug_is`, `test_an_unknown_proxy_ssl_header_value_raises`, `test_settings.py` `test_https_settings_come_from_the_environment` — PASS
- AC13 — 301 to https, favicon exempt — `core/tests/test_https.py` `SslRedirectTests` — PASS (see finding 4 on the exemption pattern)
- AC14 — HSTS over HTTPS only, without subdomains/preload — `test_https.py` `HstsTests`, `HstsScopeSettingsTests` — PASS
- AC15 — documented in `.env.example`, the README and `PATCHED_ENVIRON` — `test_env_example.py` `test_the_https_variables_are_commented_out_examples`, `test_defines_every_variable`, `test_each_variable_has_a_comment_above_it`, `test_settings.py` `PATCHED_ENVIRON` + `test_https_settings_come_from_the_environment` — PASS
- AC16 — suite passes whatever `DEBUG` is — `config/tests/test_runner.py`, and the full suite green with `DEBUG` from `.env` and with `DEBUG=False` — **FAIL** for `--parallel` runs (finding 1)
- AC17 — console email only with `DEBUG` — `test_settings.py` `test_mail_goes_to_the_console_only_with_debug` — PASS
- AC18 — `check --deploy --fail-level WARNING` clean — `config/tests/test_deploy_check.py` — PASS
- AC19 — CI step — `config/tests/test_ci.py` `QualityJobTests.test_each_gate_command_is_its_own_unconditional_named_step_in_order`, `test_the_deployment_check_key_is_long_enough_for_check_deploy` — PASS
- AC20 — smoke script with HTTP overrides and a default-settings container — `config/tests/test_docker.py` `SmokeScriptTests` (two new tests). `scripts/docker-smoke.sh` ran end to end in step 18: 22 checks PASS — PASS
- AC21 — README and `CLAUDE.md` — checked by reading the diff. The documented `check --deploy` and `axes_reset_username` commands were run — PASS

Suite: 642 tests OK (59.6 s). `ruff check` clean, `ruff format --check` clean, `makemigrations --check` "No changes detected".

## Findings

- [medium] `src/config/runner.py:13` — **Parallel workers miss the override.** `TestRunner` turns the SSL redirect off in `setup_test_environment()`, which runs only in the main process. `--parallel` workers set up through `ParallelTestSuite`'s worker initialiser and re-import settings, so with `DEBUG` off they keep `SECURE_SSL_REDIRECT=True`. Their plain-HTTP requests get 301s, which breaks AC16. — Recommendation: give `TestRunner` a `ParallelTestSuite` subclass (`parallel_test_suite`) whose worker setup (`process_setup`) also turns the redirect off. Test it by calling that setup directly, then confirm with `DEBUG=False manage.py test <a few modules> --parallel 2`.
- [low] `src/config/runner.py:19` — **Teardown can mask a setup error.** `teardown_test_environment()` reads `self._plain_http`, which doesn't exist if `super().setup_test_environment()` raised. The resulting `AttributeError` would hide the original error. — Recommendation: tolerate a missing override in teardown, with a test that tears down without having set up.
- [low] `src/config/settings.py` (`AXES_LOCKOUT_PARAMETERS`) — **Case variants each get their own counter.** The lockout key is the username exactly as typed. On a database whose username lookup ignores case (e.g. MySQL's default collation, reachable through `DATABASE_URL`), "Alice", "ALICE" and so on log in as the same user, and each gets its own 5-try counter. That multiplies the limit. SQLite, as shipped, is case-sensitive, so it can't be exploited there today. — Recommendation: set `AXES_USERNAME_CALLABLE` to a function that casefolds the username, with a test that 5 failures spread over case variants lock out the user.
- [info] `src/config/settings.py` (`SECURE_REDIRECT_EXEMPT`) — **The exemption pattern also matches before a trailing newline.** In `r"^favicon\.ico$"`, `$` matches before a trailing newline, so `/favicon.ico%0A` also skips the redirect. No route matches it, so it is only a 404 over HTTP, with no exposure. — Recommendation: use `r"^favicon\.ico\Z"`, and add `/favicon.ico%0A` to `test_only_the_favicon_itself_is_exempt`.

Checked with no finding:
- The lockout page and response reveal no account.
- `override_settings(AXES_FAILURE_LIMIT=1)` in `pages.py` really reaches axes (read at call time).
- `test_deploy_check`'s environment overrides a developer's `.env`.
- Blank and whitespace handling in `optional_bool` and `optional_non_negative_int`.
- The proxy header is opt-in and documented.
- The runner only affects `manage.py test`.
- Error messages name the variable, never the value.
- The CI file, README and `.env.example` hold dummy keys only.

## Reviewed
first review: commit 61c7ce6, 2026-10-04 (base d52d39d)
re-review: commit 3444e66, 2026-10-04 (base e0f353b)
