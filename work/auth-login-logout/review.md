# Review: auth-login-logout

## Verdict: FAIL

The two reviewers (code and security) found no high-severity issues. The suite is green (71 tests, exit 0), and `ruff check` and `ruff format --check` are clean. The review still fails because two acceptance criteria are only partly proven: their tests pass even when the behaviour they guard is removed (findings 1 and 2).

## Acceptance criteria
- AC1: covered. `test_login.LoginPageTests.test_login_page_is_served_at_the_login_url` checks the login path and `LOGIN_URL`. `test_no_password_reset_or_change_routes_exist` checks that no password routes exist. `test_logout.LogoutTests.test_post_logs_out_and_redirects_with_a_message` checks the logout path and `LOGOUT_REDIRECT_URL`. PASS
- AC2: covered by `LoginPageTests.test_login_page_is_served_at_the_login_url` and `test_login_page_renders_the_login_form`. PASS
- AC3: covered by `LoginSubmitTests.test_valid_login_logs_the_user_in_and_redirects`. PASS
- AC4: covered by `LoginSubmitTests.test_landing_page_welcomes_the_user_back`. PASS
- AC5: covered by `LoginFailureTests.test_failed_login_shows_one_generic_error`. PASS
- AC6: covered by `LoginNextTests.test_safe_next_is_carried_in_the_form_and_followed`. PASS
- AC7: **partly covered** by `LoginNextTests.test_unsafe_next_is_never_followed`. The "POST `next`" half PASSES. The "passed in the query string (`GET ?next=`) and then posted" half is not exercised as written; see finding 2.
- AC8: **partly covered.** The GET half (`LoginLoggedInTests.test_logged_in_get_redirects_without_the_form`) PASSES. `test_logged_in_post_redirects` stays green with `redirect_authenticated_user` removed; see finding 1.
- AC9: covered by `LogoutTests.test_post_logs_out_and_redirects_with_a_message`, `test_landing_page_says_the_user_logged_out` and `test_get_is_not_allowed_and_keeps_the_user_logged_in`. PASS
- AC10: covered by `test_nav.NavTests.test_anonymous_nav_has_goals_and_login_and_signup_links` and `test_logged_in_nav_has_no_login_placeholder_and_no_signup_link`, plus `core.tests.test_home.HomePageTests.test_nav_shows_goals_as_a_placeholder_that_is_not_a_link`. PASS
- AC11: covered by `RoundTripTests.test_sign_up_log_out_and_log_back_in`. PASS
- AC12: covered by `CsrfTests.test_login_without_a_csrf_token_is_rejected`, `test_logout_without_a_csrf_token_is_rejected` and `test_logout_with_the_token_from_the_nav_form_succeeds`. PASS (but see finding 9 on how precise the tests are)
- AC13: covered by `SessionLifecycleTests.test_login_replaces_the_session_key` and `test_logout_invalidates_the_old_session`. PASS
- AC14: covered by `LoginFailureTests.test_inactive_user_gets_the_generic_error`. PASS
- AC15: covered by `LoginNextTests.test_next_cannot_inject_markup_into_the_login_page`. PASS

## Findings
1. **[medium] (code) `src/accounts/tests/test_login.py:218`: `test_logged_in_post_redirects` can't fail on the regression it guards.**
   - **Problem:** It posts *valid* credentials, and a normal re-login redirects to `/` the same way. With `redirect_authenticated_user = False` the test still gets `302 /`, so AC8's POST half is unproven.
   - **Fix:** post empty data, then assert the redirect, `assertTemplateNotUsed("accounts/login.html")` and that no "Welcome back" message was queued. Mutation check: `redirect_authenticated_user = False` must turn the test red.
2. **[medium] (code) `src/accounts/tests/test_login.py:116-123`, `plan.md` step 8 note: AC7's "GET `?next=` then posted" variant posts directly to `/accounts/login/?next=…`.**
   - **Problem:** The step note's justification is wrong. The form's `action` carries no query string, so a browser posts `next` only through the hidden field. The real flow is never tested: render the form, check that the hidden `next` is `""` for an unsafe payload, then post it.
   - **Fix:** keep the direct-query case, which pins that `LoginView` reads GET `next`. Add the real flow too: GET with each payload, assert the form's `next` input value is `""`, then post that value and assert a redirect to `LOGIN_REDIRECT_URL`. Correct the step 8 note.
3. **[low] (security and code) `src/accounts/tests/test_logout.py`: no test pins that an unsafe posted `next` on logout is ignored.**
   - **Problem:** The ticket keeps Django's native `next` handling on logout, but no test pins it.
   - **Fix:** loop over the AC7 payloads, POST each to logout, and assert the user is logged out and the redirect goes to `LOGOUT_REDIRECT_URL`.
4. **[low] (security) `src/accounts/tests/test_login.py:205-225`: no test covers an unsafe `next` for an already logged-in user.**
   - **Problem:** That case uses the `dispatch` → `get_success_url()` path, a separate code path from `form_valid`.
   - **Fix:** for a logged-in user, GET `?next=https://evil.example/` and `?next=//evil.example/`, and assert a redirect to `LOGIN_REDIRECT_URL`.
5. **[low] (code) `src/accounts/tests/test_login.py:37-39`, `src/accounts/tests/test_nav.py:49-52`: form attributes are compared as an exact dict.**
   - **Problem:** Adding a `class` or `id` breaks the test.
   - **Fix:** compare only `method` and `action`, and assert exactly one form.
6. **[low] (code) `src/accounts/tests/test_nav.py:39`: the name `test_logged_in_nav_has_no_login_placeholder_and_no_signup_link` is stale after step 14.**
   - **Fix:** rename it, e.g. `test_logged_in_nav_has_username_and_logout_form_and_no_auth_links`.
7. **[low] (code) `src/accounts/tests/test_login.py:185`: a failed subtest makes the final comparison raise `IndexError`.**
   - **Fix:** assert `len(main_texts) == 2` before comparing.
8. **[low] (code) `src/accounts/tests/test_logout.py:49-61`: `test_login_replaces_the_session_key` never asserts that the login worked.**
   - **Problem:** It only passes because a failed login leaves the cookie unchanged.
   - **Fix:** assert `_auth_user_id` is in the session after the POST.
9. **[info] (security) `src/accounts/tests/test_logout.py:83-99`: the two "no token" CSRF tests never GET a page first.**
   - **Problem:** They pass on Django's "CSRF cookie not set" rejection rather than on a missing token.
   - **Fix:** GET first so the cookie is set, then POST without a token.
10. **[low] (code) `src/core/tests/html.py:36-38, 66-91`: `PageParser` docstrings are incomplete.**
    - **Problem:** The class docstring doesn't mention forms. `forms()` collects only `<input>` and doesn't collapse nested forms the way a browser does. Nothing in this ticket hits these gaps.
    - **Fix:** document both limits.
11. **[low] (code) `plan.md` design section: the settings checks are said to go in `test_apps.py`, but they live in `test_login.py` and `test_logout.py`.**
    - **Fix:** align the plan text.

### Needs a decision from the user (behaviour beyond the ACs)
Decision on finding 12 (2026-10-02): the user chose to fix both edge cases. They are now AC16 and plan steps 23–24. Finding 13 is still open.

12. **[low] (code and security) `src/accounts/views.py:49-53`: two logout edge cases.**
    - An anonymous POST to logout also shows "You have been logged out.".
    - A POST with `next=/accounts/logout/` makes Django render the admin-styled `registration/logged_out.html` instead of redirecting.
    - Both need a deliberate CSRF-valid POST, so neither is a security issue.
    - **Options:** add the message only when the user was authenticated, and/or set `next_page` so logout always redirects. Or accept both as they are.
13. **[low] (security) `src/accounts/views.py:37`: `redirect_authenticated_user = True` allows cross-site detection of whether a visitor is logged in.**
    - This is a known Django caveat. The setting was an approved design choice (AC8, consistent with sign-up).
    - **Options:** record it as an accepted risk in `ticket.md`, or drop the flag.

### Deferred (out of scope per ticket.md; for a deployment-hardening ticket)
- [info] There is no rate limiting or lockout for failed logins.
- [info] There are no secure-cookie or HSTS settings (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`).

## Reviewed
commit 9c8a588, 2026-10-02
