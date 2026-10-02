# Review: auth-signup
## Verdict: PASS

Round 3 (commit 4736532). There are no high or medium findings. Every acceptance criterion is proven by a test that can fail, and the suite is green. Round 2's findings 7–11 are resolved, and each was re-checked by mutation. The two new low findings (12, 13) and the deferred security lows (5, 6) don't block.

## Round 3 (commit 4736532)
### Acceptance criteria
- AC1 — `test_accounts_app_is_installed`, `test_signup_page_is_served_through_the_accounts_include` — PASS
- AC2 — `test_project_uses_the_custom_user_model`, `test_custom_user_model_adds_no_fields` (now including many-to-many fields), `test_user_model_is_registered_with_user_admin`, `test_no_model_change_is_missing_a_migration` — PASS (see finding 12)
- AC3 — `test_signup_page_is_served_through_the_accounts_include`, `test_signup_page_renders_the_signup_form` — PASS
- AC4 — `test_valid_signup_creates_one_user_with_a_hashed_password` — PASS
- AC5 — `test_valid_signup_logs_the_user_in_and_redirects` — PASS
- AC6 — `test_home_welcomes_the_new_user_after_signup` — PASS (see finding 13)
- AC7 — `test_invalid_signup_rerenders_the_form_with_the_field_error`, five cases: field error, error visible in `<main>`, no user, no login, no echoed passwords — PASS
- AC8 — `test_logged_in_get_redirects_without_the_form`, `test_logged_in_post_redirects_without_creating_a_user` — PASS
- AC9 — `test_anonymous_nav_has_placeholders_and_a_signup_link` (exact `"Goals Log in Sign up"`), `test_logged_in_nav_has_no_login_placeholder_and_no_signup_link` (exact `"Goals alice"`) — PASS
- AC10 — `test_logged_in_nav_shows_the_username` and the exact logged-in pin. The anonymous half holds by construction — PASS

Suite: 50 tests green. `ruff check` and `ruff format --check` are clean, and `manage.py check` and `makemigrations --check --dry-run` pass.

Mutations re-run by the code reviewer, each red:
- a `friends` many-to-many field (AC2)
- a stray item in the logged-in nav (AC9)
- a redirect target of `/x/` (both AC8 tests)

### Findings
Code review (0 high, 0 medium):
12. [low] src/accounts/tests/test_models.py:22 — The "adds no fields" check doesn't include `_meta.private_fields`. A `GenericRelation` on `User` would pass the suite and `makemigrations --check`, because it has no column. It's low because such a field stores no data on `User`, so AC2's purpose (profile data goes on `Profile`) still holds, and a `GenericRelation` on the user is unlikely. — Follow-up: add `+ model._meta.private_fields` to `field_names()` when the user model is next touched. Not a blocker.
13. [low] review.md, round 2 — The round 2 record listed "a welcome message built from raw POST input" as a caught mutation, but it isn't caught. The test posts `alice`, which is saved unchanged, so building the message from `request.POST["username"]` stays green. The behaviour is correct: the message uses `self.object.get_username()` and is autoescaped. The two values only differ after NFKC normalization. — Corrected in the round 2 record below. Optional follow-up: post a username that normalization changes (e.g. fullwidth `ａlice`) and assert `"Welcome, alice!"`.

Security review (0 high, 0 medium, 0 new low):
- `redirect(settings.LOGIN_REDIRECT_URL)` is confirmed not to be an open redirect, because the value is the constant `"/"` and no request data picks the target.
- If #4 adds `next`, it must validate it with `url_has_allowed_host_and_scheme`.
- Findings 5 and 6 still stand and remain deferred to a deployment-hardening ticket.

## Round 2 (commit 261a8d2): verdict FAIL, findings 7–11 resolved by plan steps 20–22
### Acceptance criteria
- AC1, AC3, AC4, AC5, AC6, AC8 — unchanged since round 1 — PASS
- AC2 — `test_custom_user_model_adds_no_fields` misses many-to-many fields (finding 7) — FAIL
- AC7 — the round 1 gap is closed. Every subtest now also asserts that the error appears in `<main>`. The help texts don't contain any of the five messages, so the check can't pass by accident — PASS
- AC9 — the anonymous nav is pinned exactly (`"Goals Log in Sign up"`) — PASS
- AC10 — PASS. The anonymous half holds by construction, because `AnonymousUser.get_username()` is `""` (see finding 9).

Suite: 50 tests green. `ruff check` and `ruff format --check` are clean, and so are `manage.py check` and `makemigrations --check --dry-run`.

Mutations caught:
- `{% if user %}` in the nav
- `{{ request.user }}` in the anonymous nav
- an extra `email` form field
- a missing `{% csrf_token %}`
- ~~a welcome message built from raw POST input~~ (corrected in round 3: this mutation is **not** caught, see finding 13)

Not caught: findings 7 and 8.

### Findings
Code review (0 high):
7. [medium] src/accounts/tests/test_models.py:18-25 — AC2 "adds no fields" compares only `_meta.fields`, so an added many-to-many field goes unnoticed. — Compare `fields + many_to_many` on both models (`AbstractUser`'s list includes `groups` and `user_permissions`). Plan step 20.
8. [low] src/accounts/tests/test_nav.py:32-46 — The logged-in nav isn't pinned. A stray `<span>Profile</span><span>Sign up</span>` there keeps the suite green. — Assert `page.text("nav") == "Goals alice"`. Plan step 21.
9. [low] src/accounts/tests/test_nav.py:26 and plan step 18's note — The comment "(no username)" and the note's "no test can make it red" / "no visible regression" go too far. Rendering the username unconditionally still outputs an empty `<span>`, and an element-level assertion would catch it, but no username ever reaches anonymous visitors. — Say that AC10's anonymous half holds by construction, and that the exact pin only guards against stray text. Plan step 22.
10. [low] src/config/settings.py:89-94 — `AUTH_USER_MODEL` and `LOGIN_REDIRECT_URL` sit under the "# Password validation" header. — Give them their own "# Authentication" section. Plan step 22.
11. [low] src/accounts/views.py:20 — `redirect(resolve_url(...))` resolves the URL twice, because `redirect()` already calls `resolve_url`. — Use `redirect(settings.LOGIN_REDIRECT_URL)`. Plan step 22.

Security review (0 high, 0 medium, no new findings): findings 5 and 6 still stand and remain deferred.

## Round 1 (commit 3d97cc4): verdict FAIL, findings 1–4 resolved by plan steps 17–19
### Acceptance criteria
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

### Findings
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
commit 4736532, 2026-10-02 (round 1: commit 3d97cc4, FAIL; round 2: commit 261a8d2, FAIL)
