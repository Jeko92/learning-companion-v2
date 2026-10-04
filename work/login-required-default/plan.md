# Plan: login-required-default

## Research summary
- **Middleware (Django 6.1.1, `contrib/auth/middleware.py`)**: `LoginRequiredMiddleware.process_view` lets a request through when the resolved callback has `login_required = False` or the user is authenticated; otherwise it redirects to `getattr(view_func, "login_url", None) or settings.LOGIN_URL` with `?next=<full path>`. It needs `request.user`, so it goes after `AuthenticationMiddleware`. Unresolved paths raise `Resolver404` before `process_view`, so they stay a plain 404 (docker-smoke's `/no-such-page/` check is safe).
- **`login_not_required`** only sets `view_func.login_required = False`. It works on a function view and through `@method_decorator(login_not_required, name="dispatch")` (`as_view()` copies `dispatch.__dict__` onto the view function). On a CBV class it does nothing, because class attributes aren't copied.
- **Today's exemptions**: `LoginView.dispatch` is already decorated, and `LogInView` doesn't override `dispatch`, so `/accounts/login/` is exempt. `AdminSite.login` is exempt. `LogoutView` isn't. `SignUpView` overrides `dispatch` and is decorated only with `sensitive_post_parameters`, so it isn't exempt. `core.views.home` and `core.views.favicon` aren't exempt either.
- **Admin**: `AdminSite.get_urls()` gives its own views `login_url = reverse_lazy("admin:login")`, so anonymous `/admin/` still goes to `/admin/login/?next=/admin/`. `ModelAdmin` views have no `login_url`, so e.g. `/admin/goals/goal/` goes to `/accounts/login/?next=/admin/goals/goal/`. Admin's catch-all means every `/admin/...` path resolves.
- **Mixins**: `LoginRequiredMixin` stays, and is redundant but harmless: the middleware redirects anonymous visitors first, to the same `LOGIN_URL?next=` the mixins and every existing `login_redirect(path)` test helper build.
- **Pins that must keep passing**: `MIDDLEWARE[:2]` (WhiteNoise second, `config/tests/test_settings.py:205`) and `MIDDLEWARE[-1]` (Axes last, `accounts/tests/test_lockout.py:54`). Anonymous tests that need the public views to stay public: home (`core/tests/test_home.py`), favicon (`core/tests/test_favicon.py:72`, `core/tests/test_https.py:23`), sign-up (`accounts/tests/test_signup.py`), log-in (`test_login.py`, `test_https.py`), anonymous log-out (`test_logout.py:38`), lockout incl. `/admin/login/` (`test_lockout.py:223`), and the public pages in `core/tests/pages.py`.
- **Test conventions**:
  - Django `TestCase`/`SimpleTestCase`, classes `<Feature><Aspect>Tests`, sentence-style method names, no method docstrings, `#` comments for the why.
  - Arrange/act/assert separated by blank lines, `subTest` in loops, `force_login` (never `Client.login`, because axes is a second backend), `assertRedirects(..., fetch_redirect_response=False)`.
  - Exact-set pins with a "must be added here deliberately" comment.
  - There's no test-only URLconf yet. A test module can define `urlpatterns` and use `@override_settings(ROOT_URLCONF=__name__)`. It must also include `accounts.urls` under `accounts/`, or `resolve_url("accounts:login")` fails.
  - No route walker recurses today (`session_routes()` only reads one include); recursion over `URLResolver`/`URLPattern` is new. Run one module with `./.venv/bin/python src/manage.py test <app>.tests.test_<x> --verbosity 2`.

## Design decisions
- **Mark the public views, then add the middleware.** Steps 1–4 exempt home, favicon, sign-up and log-out while the middleware is still off, so the suite stays green when step 5 turns it on.
- **Decorators**: home and favicon (function views) get `@login_not_required`. `SignUpView` gets `login_not_required` added to its existing `method_decorator([...], name="dispatch")` list, and `LogOutView` gets `@method_decorator(login_not_required, name="dispatch")`. Class-level decoration would silently do nothing (see research).
- **Middleware position**: directly after `AuthenticationMiddleware` (before Messages, XFrame and Axes), so WhiteNoise stays second and Axes stays last. Pinned as "index of LoginRequired == index of Authentication + 1".
- **The "fails closed" proof uses a test-only URLconf** (`ROOT_URLCONF` override in the test module) with an unprotected function view. That is the only way to show a view without its own check is still protected.
- **Walker home**: a new `core/tests/test_login_required.py`, next to the site-wide tests and `pages.py`. It recurses over `get_resolver()`, names each route `namespace:name` and reads `callback.login_required` (the middleware's own test).
  - The set of exempt routes is pinned exactly to `{"home", "favicon", "accounts:signup", "accounts:login", "accounts:logout", "admin:login"}`. A new public route fails until it is added on purpose; a new private route is covered automatically.
  - The anonymous-GET check covers every non-admin route outside the allow-list, with `int` converters filled with `1` (the middleware answers before any lookup, so the pk needn't exist). Admin's regex routes are pinned separately in step 8.
- **Keep every `LoginRequiredMixin`** and change no existing test.

## Steps
- [x] 1. Home is marked public (`resolve("/").func` has `login_required` False) — test: `src/core/tests/test_home.py` — impl: `src/core/views.py` (`@login_not_required` on `home`) — covers: AC3
- [x] 2. The favicon is marked public (`resolve("/favicon.ico").func` has `login_required` False); also add an anonymous HEAD → 200 characterization next to the existing anonymous GET test — test: `src/core/tests/test_favicon.py` — impl: `src/core/views.py` (`@login_not_required` on `favicon`) — covers: AC4
> Steps 3–8 run as **one** red–green–refactor cycle with one commit (the user's request, 2026-10-04, to cut repeated full-suite runs): write all their tests, run only the touched test modules to see red, implement, run the full suite once, tick 3–8 together. Separate "confirm it bites" mutations are dropped: the combined red run already shows the walker failing on the not-yet-exempt sign-up/log-out and the admin/unprotected-view tests failing without the middleware.

- [x] 3. Sign-up is marked public (`resolve(SIGNUP_PATH).func` has `login_required` False) — test: `src/accounts/tests/test_signup.py` — impl: `src/accounts/views.py` (`login_not_required` in `SignUpView`'s `method_decorator` list) — covers: AC5
- [x] 4. Log-out is marked public (`resolve(LOGOUT_PATH).func` has `login_required` False) — test: `src/accounts/tests/test_logout.py` — impl: `src/accounts/views.py` (`@method_decorator(login_not_required, name="dispatch")` on `LogOutView`) — covers: AC7
- [x] 5. A view with no protection of its own redirects an anonymous GET to `/accounts/login/?next=/unprotected/` and returns 200 for a logged-in user. The test module has its own `urlpatterns` (a plain function view plus `accounts/` → `accounts.urls`) and `@override_settings(ROOT_URLCONF=__name__)`. The pin that `LoginRequiredMiddleware` sits right after `AuthenticationMiddleware` is added in the same step, in a new `LoginRequiredSettingsTests` in `test_settings.py`; it is green on arrival because the middleware is added for the red test. — test: `src/core/tests/test_login_required.py`, `src/config/tests/test_settings.py` — impl: `src/config/settings.py` (`MIDDLEWARE`) — covers: AC1, AC2, AC11
- [x] 6. Public pages still serve anonymous visitors under the middleware. Each path in the allow-list is checked through the real URLconf: home GET 200, favicon GET/HEAD 200, sign-up GET 200, log-in GET 200, anonymous log-out POST → `/`. The existing behaviour tests (sign-up submit, log-in submit, logged-in redirects, lockout 429 incl. `/admin/login/`) re-run green unchanged. A guard test, green on arrival. Before committing, confirm it bites: temporarily drop the decorator from `home`, see red, restore. — test: `src/core/tests/test_login_required.py` — impl: none — covers: AC3–AC8
- [x] 7. Fail-closed route walker. Recursive walk of the root URLconf:
  - (a) the set of routes whose callback has `login_required` False equals the allow-list exactly, with log-in and admin log-in exempt through Django itself (the pin for AC6);
  - (b) every non-admin route outside the allow-list redirects an anonymous GET to `/accounts/login/?next=<path>` (`int` converters filled with `1`; a converter the walker can't fill fails the test, so a new kind gets handled on purpose).
  A guard test, green on arrival; confirm it bites the same way as in step 6. — test: `src/core/tests/test_login_required.py` — impl: none — covers: AC10, AC6, AC11
- [x] 8. Admin under the middleware: anonymous `/admin/` → `/admin/login/?next=/admin/`, anonymous `/admin/goals/goal/` → `/accounts/login/?next=/admin/goals/goal/`, anonymous `/admin/login/` → 200. A characterization test, green on arrival. — test: `src/core/tests/test_login_required.py` — impl: none — covers: AC9
- [x] 9. Docs. Markdown only, no test:
  - `CLAUDE.md`'s Auth section (middleware, public views, how to exempt a class-based view through `dispatch`, the walker's allow-list rule, the admin redirects);
  - its favicon note ("must mark it" → "marked");
  - Dashboard/Layout mentions where needed;
  - `README.md`'s auth paragraph.
  — impl: `CLAUDE.md`, `README.md` — covers: AC12

**Coverage**:

| AC | Steps |
|---|---|
| AC1 | 5 |
| AC2 | 5 |
| AC3 | 1, 6 |
| AC4 | 2, 6 |
| AC5 | 3, 6 |
| AC6 | 6, 7 |
| AC7 | 4, 6 |
| AC8 | 6 (existing lockout tests) |
| AC9 | 8 |
| AC10 | 7 |
| AC11 | 5, 7 (all existing anonymous-redirect tests unchanged) |
| AC12 | 9 |
