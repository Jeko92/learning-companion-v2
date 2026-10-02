# Review: auth-signup
## Verdict: FAIL

Round 1 (commit 3d97cc4). AC7 is only partly proven. The invalid-sign-up test checks the error on the form object in the context, but not that the re-rendered page shows it. A template that renders the fields without their errors keeps the whole suite green (finding 1, confirmed by mutation). Under the verdict rules, an uncovered acceptance criterion means FAIL, even though the suite is green and no finding is high.

## Acceptance criteria
- AC1 — covered by `accounts.tests.test_apps.InstalledAppsTests.test_accounts_app_is_installed` and `accounts.tests.test_signup.SignUpPageTests.test_signup_page_is_served_through_the_accounts_include` — PASS
- AC2 — covered by `accounts.tests.test_models.UserModelTests.test_project_uses_the_custom_user_model`, `test_custom_user_model_adds_no_fields`, `UserAdminTests.test_user_model_is_registered_with_user_admin` and `MigrationsTests.test_no_model_change_is_missing_a_migration` — PASS
- AC3 — covered by `test_signup_page_is_served_through_the_accounts_include` and `test_signup_page_renders_the_signup_form` — PASS
- AC4 — covered by `SignUpSubmitTests.test_valid_signup_creates_one_user_with_a_hashed_password` — PASS
- AC5 — covered by `test_valid_signup_logs_the_user_in_and_redirects` — PASS
- AC6 — covered by `test_home_welcomes_the_new_user_after_signup` — PASS
- AC7 — `SignUpInvalidTests.test_invalid_signup_rerenders_the_form_with_the_field_error` proves the following for all five cases: status 200, the template, the error on the right field (form object), no user created, no login, and no echoed passwords. It does **not** prove that the re-rendered page shows the error (finding 1) — FAIL
- AC8 — covered by `SignUpLoggedInTests.test_logged_in_get_redirects_without_the_form` and `test_logged_in_post_redirects_without_creating_a_user` — PASS
- AC9 — covered by `accounts.tests.test_nav.NavTests.test_anonymous_nav_has_placeholders_and_a_signup_link` and `test_logged_in_nav_has_no_login_placeholder_and_no_signup_link` — PASS
- AC10 — covered by `test_logged_in_nav_shows_the_username` and `test_anonymous_nav_shows_no_username` (see finding 2) — PASS

Suite: 51 tests green. `ruff check` and `ruff format --check` are clean, `manage.py check` reports no issues, and `makemigrations --check --dry-run` reports "No changes detected". No app code imports `django.contrib.auth.models.User`.

Mutations run in a scratch copy, each of which turned its test red:
- `dispatch` limited to GET (AC8)
- no `messages.success` (AC6)
- no `login()` (AC5)
- no `sensitive_post_parameters` (step 13)
- the Sign up `href` changed (AC9)

Two mutations stayed green: the template without errors (finding 1) and the username rendered for anonymous visitors (finding 2). `PageParser.links` and `href_text` were correct on nested elements, nested links, implicitly closed links, links outside sections and `<link href>`.

## Findings
Code review (0 high):
1. [medium] src/accounts/tests/test_signup.py:135-148 — AC7 says the form is re-rendered with each error on its field, but the test only inspects `response.context["form"]`. A `signup.html` that renders `{{ form.username }}{{ form.password1 }}{{ form.password2 }}` without errors keeps the suite green, and the user would see no error. — In each subtest, also assert that the error message is visible in the page's `<main>` text. Plan step 17.
2. [low] src/accounts/tests/test_nav.py:47-52 — `test_anonymous_nav_shows_no_username` can't fail for a realistic regression: `AnonymousUser.get_username()` is `""`, so an unconditional `{{ user.get_username }}` passes. — Pin the anonymous nav text exactly (`"Goals Log in Sign up"`), which covers AC9 and AC10 for anonymous visitors. Plan step 18.
3. [low] CLAUDE.md:9 and the `src/accounts/` Layout line — Log-in and log-out are described in the present tense, but they don't exist until #4. — Reword as future work. Plan step 19.
4. [low] work/auth-signup/plan.md (step 5) — The step text says the suite stays at 33 tests, but its Done note correctly says 38. 33 was the count before this ticket. — Correct the step text. Plan step 19.

Security review (0 high, 0 medium):
5. [low] src/config/settings.py — This is the first branch with authenticated sessions, but there is no transport hardening yet: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` and `SECURE_HSTS_SECONDS` are unset. That predates this branch and only matters once deployed. — Out of scope here: a deployment-hardening ticket should read these from env (on when `DEBUG=False`) and gate on `manage.py check --deploy`. Not a plan step.
6. [low] src/config/urls.py — The admin is at the default `/admin/` with no throttling, and sign-up is open. Only `is_staff` users can reach it, and sign-up can't grant that. — Out of scope (the ticket excludes rate limiting): handle it in the same hardening ticket. Not a plan step.

The security review found no issue with:
- CSRF (`{% csrf_token %}` and the middleware)
- XSS (autoescaped username and message; `UnicodeUsernameValidator`)
- open redirect (only `LOGIN_REDIRECT_URL`, no `next`)
- mass assignment (`Meta.fields = ("username",)`, pinned by the AC3 test)
- session fixation (`login()` cycles the key)
- password storage and validators, and `sensitive_post_parameters`
- authenticated users creating accounts (redirected before the form)
- account enumeration (inherent to username sign-up; acceptable)

## Reviewed
commit 3d97cc4, 2026-10-02
