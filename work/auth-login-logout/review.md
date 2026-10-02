# Review: auth-login-logout

## Verdict: PASS

This is the second final review. The first one (commit 9c8a588) failed because two acceptance criteria had tests that could not fail; its findings are listed under "Earlier review" below. Plan steps 18–24 addressed those findings and added AC16.

Results for this round:
- Neither the code reviewer nor the security reviewer found a high- or medium-severity issue.
- Every finding from the first review (1–11) is resolved. The code reviewer checked each one by breaking the guarded behaviour in a scratch copy and watching the test fail.
- Every acceptance criterion, AC1 to AC16, has a test that goes red when its behaviour is removed.
- The suite passes (76 tests, exit 0), and `ruff check` and `ruff format --check` are clean.

## Acceptance criteria
- AC1: PASS
  - `test_login.LoginPageTests.test_login_page_is_served_at_the_login_url` (login path, `LOGIN_URL`)
  - `test_no_password_reset_or_change_routes_exist`
  - `test_logout.LogoutTests.test_post_logs_out_and_redirects_with_a_message` (logout path, `LOGOUT_REDIRECT_URL`)
- AC2: PASS. `LoginPageTests.test_login_page_is_served_at_the_login_url` and `test_login_page_renders_the_login_form`.
- AC3: PASS. `LoginSubmitTests.test_valid_login_logs_the_user_in_and_redirects`.
- AC4: PASS. `LoginSubmitTests.test_landing_page_welcomes_the_user_back`.
- AC5: PASS. `LoginFailureTests.test_failed_login_shows_one_generic_error`.
- AC6: PASS. `LoginNextTests.test_safe_next_is_carried_in_the_form_and_followed`.
- AC7: PASS
  - `LoginNextTests.test_unsafe_next_is_never_followed`: POST `next`, and GET `next` read by the view
  - `test_unsafe_next_is_dropped_from_the_form_a_browser_submits`: the browser flow
- AC8: PASS. `LoginLoggedInTests.test_logged_in_get_redirects_without_the_form`, `test_logged_in_post_redirects_without_logging_in_again` and `test_logged_in_get_never_follows_an_unsafe_next`.
- AC9: PASS. `LogoutTests.test_post_logs_out_and_redirects_with_a_message`, `test_landing_page_says_the_user_logged_out`, `test_get_is_not_allowed_and_keeps_the_user_logged_in` and `test_unsafe_next_is_never_followed`.
- AC10: PASS
  - `test_nav.NavTests.test_anonymous_nav_has_goals_and_login_and_signup_links`
  - `test_logged_in_nav_has_username_and_logout_form_and_no_auth_links`
  - `core.tests.test_home.HomePageTests.test_nav_shows_goals_as_a_placeholder_that_is_not_a_link`
- AC11: PASS. `RoundTripTests.test_sign_up_log_out_and_log_back_in`.
- AC12: PASS. `CsrfTests.test_login_without_a_csrf_token_is_rejected`, `test_logout_without_a_csrf_token_is_rejected` and `test_logout_with_the_token_from_the_nav_form_succeeds`.
- AC13: PASS. `SessionLifecycleTests.test_login_replaces_the_session_key` and `test_logout_invalidates_the_old_session`.
- AC14: PASS. `LoginFailureTests.test_inactive_user_gets_the_generic_error`.
- AC15: PASS. `LoginNextTests.test_next_cannot_inject_markup_into_the_login_page`.
- AC16: PASS. `LogoutTests.test_anonymous_logout_redirects_without_the_message` and `test_next_pointing_at_logout_still_redirects`.

## Findings (this round; none blocking)
1. **[low] (code and security) `src/accounts/views.py:58-64`: the logout self-`next` check compares full strings.**
   - **Problem:** near-variants still redirect to the logout URL, and the browser's GET of it then gets a 405. Examples:
     - `next=/accounts/logout/?a=1`
     - `#top`
     - no trailing slash
     - a POST to `/accounts/logout/?x=1`

     The admin `logged_out.html` is never rendered and the target is always same-site, so this is not a security issue. Each case needs a deliberately crafted, CSRF-valid POST, and the nav form sends no `next`.
   - **Decision:** the user accepted it for this ticket (2026-10-02).
   - **Later option:** compare `urlsplit(url).path` with `request.path`, or resolve the path to `accounts:logout`. Add a `?a=1` subtest.
2. **[low] (security) `src/accounts/views.py:37`: `redirect_authenticated_user = True` allows cross-site detection of whether a visitor is logged in.**
   - **Decision:** accepted as a risk by the user (2026-10-02) and recorded in `ticket.md` Notes. This was finding 13 in the earlier review.
3. **[low] (code) `work/auth-login-logout/plan.md`: steps 23 and 24 lack "Done" notes.**
   - **Detail:** `activity.log` shows red then green for both. Step 23's red was the message unexpectedly found. Step 24's red was `200 != 302`.
4. **[low] (code) `src/accounts/tests/test_logout.py:7`: `UNSAFE_NEXTS` is imported from `test_login`.**
   - **Problem:** this couples the two test modules. Nothing is discovered twice.
   - **Later option:** a shared payloads helper.
5. **[low] (code) `work/auth-login-logout/ticket.md`: the status line was stale.** Updated with this review.
6. **[info] (security) `src/accounts/views.py:62-63`: the fallback assumes `LOGOUT_REDIRECT_URL` never resolves to the logout URL itself.**
   - **Detail:** it is `"/"`, pinned by a test.
7. **[info] (security) `src/accounts/tests/test_logout.py`: no test shows that a safe same-site `next` on logout is still followed.**
   - **Detail:** that is Django's native behaviour, kept on purpose.

### Deferred (out of scope per ticket.md; for a deployment-hardening ticket)
- [info] There is no rate limiting or lockout for failed logins.
- [info] There are no secure-cookie or HSTS settings (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`).

## Earlier review (commit 9c8a588, verdict FAIL)
Findings 1–11 became plan steps 18–22 and are resolved:
- **AC8:** the logged-in POST test could not fail.
- **AC7:** the browser flow for an unsafe `next` was untested.
- **Unsafe `next`** was untested on logout and for a logged-in user.
- **Test precision fixes:**
  - form attributes were compared as an exact dict
  - a test name was stale
  - a failed subtest led to an `IndexError`
  - the session test's premise was unchecked
  - the CSRF tests failed on a missing cookie, not a missing token
  - the `PageParser` docstrings were incomplete
  - the plan text was out of line with the code

Finding 12 (the logout edge cases) became AC16 and steps 23–24. Finding 13 is accepted as a risk; see finding 2 above.

## Reviewed
commit fb5faa2, 2026-10-02
