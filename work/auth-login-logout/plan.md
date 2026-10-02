# Plan: auth-login-logout

## Research summary
- **Project (from #3):**
  - The `accounts` app has the namespace `accounts` and is mounted at `/accounts/`. `accounts/urls.py` has only `signup/`.
  - `SignUpView(CreateView)` does three things on success: `login()`, `messages.success("Welcome, …!")`, and a redirect to `resolve_url(settings.LOGIN_REDIRECT_URL)`.
  - `settings.py` has an "# Authentication" section with `AUTH_USER_MODEL = "accounts.User"` and `LOGIN_REDIRECT_URL = "/"`.
  - `LOGIN_URL` (default `/accounts/login/`) and `LOGOUT_REDIRECT_URL` (default `None`) are not set.
  - Defaults apply for `MESSAGE_STORAGE` (`FallbackStorage`), `SESSION_ENGINE` (db) and `CSRF_USE_SESSIONS` (`False`).
  - `base.html` renders messages on every page.
  - The nav is `<span>Goals</span>` plus one of two branches: `{% if user.is_authenticated %}<span>{{ user.get_username }}</span>`, or else `<span>Log in</span><a href=signup>Sign up</a>`.
- **Existing tests this ticket breaks on purpose:**
  - `core/tests/test_home.py::test_nav_shows_placeholders_that_are_not_links`: its "Log in" subtest fails once "Log in" becomes a link.
  - `accounts/tests/test_nav.py`:
    - The anonymous `links("nav") == [signup]` and "Log in not in href_text" break when "Log in" becomes a link. The exact text `"Goals Log in Sign up"` still holds.
    - The logged-in exact text `"Goals alice"` becomes `"Goals alice Log out"` once the logout button exists. `links("nav") == []` still holds, because a form and a button carry no `href`.
- **`PageParser` (`core/tests/html.py`):**
  - It offers `text(section)`, `href_text()`, `links(section)` and `elements`, which lists tags and attributes but no section.
  - `<input>` is a void element, and `handle_starttag` returns early for void tags. So anything that tracks inputs must record them before that `return`.
- **Django 6.1.1 (from the source, confirmed by running it):**
  - **`LoginView`:**
    - Its `dispatch` carries `login_not_required`, `sensitive_post_parameters()`, `csrf_protect` and `never_cache`.
    - Defaults: `template_name = "registration/login.html"`, `redirect_authenticated_user = False`.
    - `get_redirect_url` reads `next` from POST, then from GET. It returns the value only if `url_has_allowed_host_and_scheme(url, {request.get_host()}, require_https=request.is_secure())` holds, and `""` otherwise.
    - `get_success_url` is `get_redirect_url() or resolve_url(settings.LOGIN_REDIRECT_URL)`.
    - The context `next` is the **validated** value, `""` when the URL is unsafe.
    - `form_valid` calls `auth_login`, then redirects. Overriding it and calling `super()` first leaves room to add a message.
    - With `redirect_authenticated_user`, an authenticated user is redirected to the success URL, and Django raises `ValueError` if that would loop back to the login page itself.
  - **`AuthenticationForm`:**
    - Its fields are `username` (autofocus, `autocomplete="username"`) and `password` (`autocomplete="current-password"`).
    - Its `invalid_login` message is "Please enter a correct username and password. Note that both fields may be case-sensitive."
    - With the default `ModelBackend`, an inactive user fails `authenticate()`, so they get `invalid_login`. The separate "This account is inactive." only appears with `AllowAllUsersModelBackend`.
  - **`LogoutView`:**
    - It allows `["post", "options"]`, so `GET` returns 405. It carries `csrf_protect` and `never_cache`.
    - `post()` calls `auth_logout` (which sends `user_logged_out`, then `session.flush()`, which deletes the DB row), then redirects to `get_redirect_url() or LOGOUT_REDIRECT_URL`.
    - It honours a **validated** `next` the same way `LoginView` does.
    - A message added before or after `logout()` survives the redirect. Messages are queued on `request._messages` and written in `MessageMiddleware.process_response`. `FallbackStorage` writes them to a cookie first, which doesn't depend on the session.
  - **`url_has_allowed_host_and_scheme`**, run with `allowed_hosts={"testserver"}`:

    | Input | Result |
    |---|---|
    | `/some/page/?a=1` | True |
    | `https://evil.example/` | False |
    | `//evil.example/` | False |
    | `/\evil.example/` | False |
    | `\\evil.example` | False |
    | `javascript:alert(1)` | False |
    | `https://testserver.evil.example/` | False |

    It also checks the backslash-normalised form of each URL.
  - **Sessions:**
    - `login()` calls `cycle_key()` (a new key, with the old row deleted) when the session had no `_auth_user_id`. It also calls `rotate_token()`, so the CSRF secret changes on login.
    - `logout()` flushes the session.
    - Putting the old session key back in the cookie gives an anonymous request.
  - **Test client:**
    - `Client(enforce_csrf_checks=True)` makes a POST without a token return 403.
    - Either the masked `csrfmiddlewaretoken` from a rendered form or the `csrftoken` cookie secret is accepted.
    - After login the secret rotates, so a test must re-read the token from a fresh page.
    - Read the session key as `client.cookies[settings.SESSION_COOKIE_NAME].value`. `client.session` creates a session as a side effect when there is none.
  - **Autoescaping:** `value="{{ next }}"` with `"><script>alert(1)</script>` renders as `&quot;&gt;&lt;script&gt;…`.

## Design decisions
- **Views in `accounts/views.py`:**
  - `LogInView(auth_views.LoginView)` sets `template_name = "accounts/login.html"` and `redirect_authenticated_user = True`. Its `form_valid` calls `super()`, then `messages.success(self.request, f"Welcome back, {user.get_username()}!")`.
  - `LogOutView(auth_views.LogoutView)` overrides `post()`: it calls `super().post()`, then `messages.info(request, "You have been logged out.")`.
  - These subclasses keep all of Django's decorators and its `next` validation. The project adds only a template, one setting, and a message.
- **URLs:** `path("login/", LogInView.as_view(), name="login")` and `path("logout/", LogOutView.as_view(), name="logout")`. These are not `include("django.contrib.auth.urls")`, so no password routes appear (AC1).
- **Settings, in the Authentication section:** `LOGIN_URL = "accounts:login"` (a URL name, which `resolve_url` turns into `/accounts/login/`) and `LOGOUT_REDIRECT_URL = "/"`.
- **Template `accounts/login.html`:**
  - It extends `base.html`.
  - It contains `<form method="post" action="{% url 'accounts:login' %}">` with `{% csrf_token %}`, `{{ form }}`, `<input type="hidden" name="next" value="{{ next }}">` and a submit button.
  - It uses Tailwind classes like `signup.html`.
- **Nav in `base.html`:**
  - Logged in: `<span>Goals</span><span>{{ user.get_username }}</span><form method="post" action="{% url 'accounts:logout' %}">{% csrf_token %}<button type="submit">Log out</button></form>`.
  - Anonymous: `<span>Goals</span><a href="{% url 'accounts:login' %}">Log in</a><a href="{% url 'accounts:signup' %}">Sign up</a>`.
- **`PageParser.forms(section)`** returns `[(form_attrs, [input_attrs, ...])]` for each `<form>` inside the section, with the inputs tied to their form. It is implemented like `open_links`: a stack of `(depth, attrs, inputs)`, inputs recorded before the void-element `return`, and pruning on end tags. Tests then assert on structure (form in nav, `next` input in main, CSRF input value) and not on substrings.
- **AC15 needs two payloads, or it is vacuous.** `LoginView` drops an unsafe `next` before rendering, so the AC's literal payload `"><script>alert(1)</script>` always renders as an empty value, even with `{{ next|safe }}`. The test also uses a payload that passes URL validation but contains markup: `/x/?q="><script>alert(1)</script>`. Only that one reaches the template and proves the escaping.
- **Guard tests are expected.** AC5, AC7, AC11–AC15 deliberately pin protections that Django already provides, so they pass on arrival. Each one gets a mutation check that breaks the protection in a realistic way and must turn the test red; the mutation is then reverted. The other ACs are real red–green cycles. To keep them red, step 1 starts with a minimal `TemplateView`, and the switch to `LoginView` happens in step 3. This is the same approach as #3.
- **Changes to earlier ACs (#2 AC4, #3 AC9).** The new requirement makes "Log in" a real link and adds "Log out". Steps 13 and 14 rewrite the affected assertions in the same commit as the template change. The suite can't be green with only one of the two changed, and the commit message and step note record this as a deliberate requirement change, not a weakened test. "Goals" stays a pinned non-link placeholder.
- **Test files:** `src/accounts/tests/test_login.py`, `test_logout.py` and the existing `test_nav.py` (all `TestCase`), plus `test_apps.py` for the settings checks. They reuse the per-module constants `USERNAME`/`PASSWORD`, as in #3. A login helper posts real credentials, not `force_login`, wherever the AC is about the login flow itself.

## Steps
Approved by the user on 2026-10-02. The approval includes:
- the strengthened AC15 test with two payloads (step 9)
- the seven guard steps (5, 6, 8, 9, 12, 15, 16), each with its mutation check, including the noted limit that step 12's login half has no project-level mutation
- the deliberate rewrites of the #2 and #3 nav tests (steps 13 and 14)
- option 3a: Django's native `next` handling on logout, validated by `url_has_allowed_host_and_scheme`, with no override. The ticket's out-of-scope note is corrected to match.

Each step is one red–green–refactor cycle and one commit, `feat(auth-login-logout): …`. Guard steps say so and name their mutation.

- [x] 1. The login page is served: `GET /accounts/login/` returns 200, `reverse("accounts:login") == "/accounts/login/"`, `resolve_url(settings.LOGIN_URL) == "/accounts/login/"`, and `accounts/login.html` and `base.html` are used. Test: `test_login.py`, expected red `404 != 200` (the status is the first assertion). Impl: `path("login/", …)`; `LogInView` as a minimal `TemplateView(template_name="accounts/login.html")`; `login.html` extends `base.html` with an empty content block; `LOGIN_URL = "accounts:login"`. Covers: AC1 (login, `LOGIN_URL`), AC2 (status, templates).
- [x] 2. The page renders the login form: `page.forms("main")` has exactly one form with `method="post"` and `action=reverse("accounts:login")`, whose inputs include `csrfmiddlewaretoken`, `username` and `password`. Test: `test_login.py`, expected red `[] != [...]`. Impl: `PageParser.forms(section)` in `core/tests/html.py`; `LogInView.get_context_data` adds `form=AuthenticationForm(self.request)` (still a `TemplateView`); the form markup in `login.html` (no `next` input yet). Covers: AC2.
- [x] 3. Valid credentials log the user in and redirect to `LOGIN_REDIRECT_URL`: after posting `alice`/`PASSWORD`, `client.session["_auth_user_id"] == str(user.pk)`, and `assertRedirects(…, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)`. Test: `test_login.py`, expected red: no `_auth_user_id` (a `TemplateView` answers `POST` with 405). Impl: `LogInView` becomes `auth_views.LoginView` with `template_name`, and `get_context_data` is dropped. Covers: AC3.
- [x] 4. After login, the landing page shows "Welcome back, alice!" (`POST` with `follow=True`, then `assertContains`). Test: `test_login.py`, expected red: the message is not found. Impl: a `form_valid` override with `messages.success`. Covers: AC4.
- [x] 5. A failed login shows one generic, visible error, and the page doesn't reveal which usernames exist. The test has two subtests, a wrong password for `alice` and an unknown username `nobody`. Each asserts:
  - status 200, and `login.html` used
  - the `invalid_login` text is in `page.text("main")`
  - `_auth_user_id` is not in the session
  - the submitted password is not in the response

  Across the two subtests, the `<main>` text is identical once the echoed username value is removed. Test: `test_login.py`. Impl: none. Covers: AC5.
  - This is a guard. Mutation: render `{{ form.username }}{{ form.password }}` without errors. Both subtests must go red. Revert afterwards.
  - Done 2026-10-02: green on arrival. The mutation turned both subtests red: the message was not found in `'Log in Log in'`. The final "identical text" comparison also errored as a knock-on, because the failed subtests recorded no text. The template was restored. The username echo lives in an attribute, not in text, so the two `<main>` texts compare equal directly.
- [x] 6. A deactivated account can't log in, and the page doesn't reveal it. A user `alice` with `is_active=False` posts the correct password. The page shows the same `invalid_login` text, not "This account is inactive.", and no one is logged in. Test: `test_login.py`. Impl: none. Covers: AC14.
  - This is a guard. Mutation: `@override_settings(AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.AllowAllUsersModelBackend"])` on the test, run in a scratch edit. It must go red, because the "inactive" message appears instead. Revert afterwards.
  - Done 2026-10-02: green on arrival. With `AllowAllUsersModelBackend` the test went red, because the page showed "This account is inactive." instead of the generic error. The test was then restored.
- [x] 7. A safe `next` is carried and honoured:
  - `GET /accounts/login/?next=/some/page/?a=1` renders a hidden input `next` with that value inside the login form (`forms("main")`)
  - a valid `POST` with `next=/some/page/?a=1` redirects there

  Test: `test_login.py`, expected red: no `next` input in the form. Impl: `<input type="hidden" name="next" value="{{ next }}">` in `login.html`. Covers: AC6.
- [ ] 8. An unsafe `next` is never followed. One `subTest` per payload: `https://evil.example/`, `//evil.example/`, `/\evil.example/`, `\\evil.example`, `javascript:alert(1)` and `https://testserver.evil.example/`. Each payload is sent both as POST `next` and as `GET ?next=` followed by a POST. Every case logs the user in, redirects to `settings.LOGIN_REDIRECT_URL`, and has a `Location` header that starts with `/` and not with `//` or `/\`. Test: `test_login.py`. Impl: none. Covers: AC7.
  - This is a guard. Mutation: override `LogInView.get_redirect_url` to return the raw POST or GET value, unvalidated. Every subtest must go red. Revert afterwards.
- [ ] 9. `next` can't inject markup. There are two payloads:
  - the AC's literal `"><script>alert(1)</script>`
  - the safe-path `/x/?q="><script>alert(1)</script>`, which passes validation and reaches the template

  For both, `GET /accounts/login/?next=<payload>` returns a page that doesn't contain the raw `<script>alert(1)</script>`. For the safe-path payload, the parsed `next` input value equals the payload (the parser unescapes it), which proves it was escaped. Test: `test_login.py`. Impl: none. Covers: AC15.
  - This is a guard. Mutation: `value="{{ next|safe }}"`. The safe-path subtest must go red. The literal payload stays green under this mutation, because it is dropped by URL validation, which is why both payloads are needed. Revert afterwards.
- [ ] 10. A logged-in user is redirected away from the login page. After `force_login`, both `GET` and `POST` to `/accounts/login/` redirect to `settings.LOGIN_REDIRECT_URL`, and `login.html` is not used. Test: `test_login.py`, expected red `200 != 302` on the `GET`. Impl: `redirect_authenticated_user = True`. Covers: AC8.
- [ ] 11. Logout works only by `POST`:
  - `reverse("accounts:logout") == "/accounts/logout/"`, and `settings.LOGOUT_REDIRECT_URL == "/"`
  - for a logged-in user, a `POST` makes the user anonymous (no `_auth_user_id`) and redirects to `LOGOUT_REDIRECT_URL`, and with `follow=True` the page shows "You have been logged out."
  - a `GET` returns 405 and the user stays logged in

  Test: `test_logout.py`, expected red `404 != 302` on the `POST` (the literal path is asserted first). Impl: `path("logout/", LogOutView.as_view(), name="logout")`; `LogOutView(LogoutView)` whose `post()` adds the message; `LOGOUT_REDIRECT_URL = "/"`. Covers: AC1 (logout, `LOGOUT_REDIRECT_URL`), AC9.
- [ ] 12. The session is replaced at login and invalidated at logout:
  - **Login:** take the session key before login, after an anonymous GET that creates a session. A real credential POST must produce a different key, and the old key must be gone from `Session.objects`.
  - **Logout:** a logged-in key K, followed by a POST to logout, then putting K back in the cookie and `GET /`, gives an anonymous response (the nav shows "Log in").

  Test: `test_logout.py` (both halves, one test per half). Impl: none. Covers: AC13.
  - This is a guard. Mutation: `LogOutView.post` only deletes `_auth_user_id` from the session instead of calling `super().post()`. The logout half must go red. The login half pins `login()`'s built-in `cycle_key`, and has no realistic project-level mutation, which is noted. Revert afterwards.
- [ ] 13. "Log in" in the nav becomes a real link for anonymous visitors. Assertions:
  - `links("nav") == [(reverse("accounts:login"), "Log in"), (reverse("accounts:signup"), "Sign up")]`
  - `text("nav") == "Goals Log in Sign up"`
  - "Goals" is not link text

  Test: `test_nav.py` (anonymous test rewritten) and `core/tests/test_home.py` (the placeholder test now checks only "Goals"). The expected red is the new `links` list. Impl: `<a href="{% url 'accounts:login' %}">Log in</a>` in `base.html`. Covers: AC10 (anonymous).
  - This is a deliberate change of #2 AC4 and #3 AC9, made in the same commit, and recorded in the step note and the commit body.
- [ ] 14. The logged-in nav has a "Log out" button in a POST form:
  - `text("nav") == "Goals alice Log out"`
  - `links("nav") == []`
  - `forms("nav")` is exactly one form with `method="post"` and `action=reverse("accounts:logout")`, whose inputs include `csrfmiddlewaretoken`

  Test: `test_nav.py` (logged-in test rewritten). Expected red: `forms("nav") == []`, and the text lacks "Log out". Impl: the logout form in the authenticated branch of `base.html`. Covers: AC10 (logged in).
  - This is a deliberate change of #3's logged-in exact text, recorded the same way.
- [ ] 15. CSRF is enforced on login and logout. With `Client(enforce_csrf_checks=True)`:
  - a login `POST` without a token returns 403, and no one is logged in
  - for a logged-in user (`force_login`), a logout `POST` without a token returns 403, and the user stays logged in
  - a logout `POST` with the `csrfmiddlewaretoken` value read from `forms("nav")` on a fresh `GET /` returns 302, and the user is anonymous

  Test: `test_logout.py`. Impl: none. Covers: AC12.
  - This is a guard. Mutation: remove `{% csrf_token %}` from the nav's logout form. The third case must go red. Revert afterwards.
- [ ] 16. Full round trip in one client:
  1. sign up `alice` through `/accounts/signup/` (logged in)
  2. `POST` logout, and check that the user is anonymous
  3. `POST` login with the same password, and check that the user is logged in and the nav shows "alice"

  Test: `test_logout.py`. Impl: none. Covers: AC11.
  - This is a guard. Mutation: `LogOutView.post` returns a redirect without calling `super().post()`. The test must go red. Revert afterwards.
- [ ] 17. Docs. No test. Commit `docs(auth-login-logout): document log-in and log-out`.
  - In `CLAUDE.md`, the Stack auth bullet should cover:
    - log-in at `/accounts/login/` and log-out at `/accounts/logout/`, through `LoginView` and `LogoutView` subclasses
    - `LOGIN_URL = "accounts:login"`, `LOGIN_REDIRECT_URL = "/"` and `LOGOUT_REDIRECT_URL = "/"`
    - `next` is honoured only for same-site URLs (Django's `url_has_allowed_host_and_scheme`)
    - logout is POST-only
  - In `CLAUDE.md`, update the Layout line for `src/accounts/`.
  - In `README.md`, update the sign-up sentence and the Layout line to include log-in and log-out.
  - Manual check against `runserver` with curl and a cookie jar:
    - log in with `next=/accounts/signup/`, then check that a malicious `next` lands on `/`
    - the nav shows the username and "Log out", then a POST to logout shows the message
    - `GET /accounts/logout/` returns 405
    - delete the throwaway user afterwards

## Coverage
| AC | Steps |
|---|---|
| AC1 login and logout URLs, `LOGIN_URL`, `LOGOUT_REDIRECT_URL`, no password routes | 1, 11 |
| AC2 login page, template, POST form, fields, CSRF | 1, 2 |
| AC3 valid login and redirect | 3 |
| AC4 "Welcome back, …!" | 4 |
| AC5 generic error, unknown vs wrong identical, no echo | 5 |
| AC6 safe `next` carried and honoured | 7 |
| AC7 unsafe `next` never followed (6 payloads × GET/POST) | 8 |
| AC8 logged-in users redirected away from login | 10 |
| AC9 POST-only logout, message, 405 on GET | 11 |
| AC10 nav anonymous / logged-in | 13, 14 |
| AC11 round trip | 16 |
| AC12 CSRF enforced, nav token works | 15 |
| AC13 session rotation and invalidation | 12 |
| AC14 inactive users rejected generically | 6 |
| AC15 `next` escaped (literal and safe-path payloads) | 9 |

AC1's "no password routes" is checked in step 1 as well: `reverse("password_reset")` and `reverse("accounts:password_reset")` both raise `NoReverseMatch` (`assertRaises`). Step 17 covers the docs and the manual check.
