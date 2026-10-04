# Plan: deploy-hardening

## Research summary

### Settings layer
- **`src/config/env.py`**
  - `resolve_settings(environ, env_file)` builds the frozen `EnvSettings` dataclass. It uses a local `django_environ.Env` subclass, and `read_env` only fills keys that are missing, so the process environment wins.
  - The only boolean is `DEBUG`, read through `env.bool`. That treats blank and any unknown string as `False`.
  - "Blank means the default" is done by hand (`Env.ENVIRON.get(name, "").strip() or default`, as for `OPENAI_MODEL` and `DATABASE_URL`).
  - There is no integer helper. `env.int` gives a raw `ValueError` on `""` and accepts negative numbers.
  - Error messages read `"The {NAME} environment variable <rule>"`: they name the variable, never the value.
- **`config/tests/test_env.py`** (`ResolveSettingsTests`)
  - Calls `self.resolve(environ(SECRET_KEY="x", …))` with a missing env file.
  - Checks exact messages with `assertRaises` + `str(raised.exception)`, and runs tables through `subTest`.
- **`config/tests/test_settings.py`** (`SettingsWiringTests`)
  - Reloads `config.settings` under `mock.patch.dict(os.environ, PATCHED_ENVIRON)` (DEBUG `"True"`, non-default values).
  - `reload_with(**overrides)` reloads with extra variables, and assertions read the reloaded module.
- **`config/tests/test_env_example.py`**
  - `VARIABLES` minus `COMMENTED_EXAMPLES` must equal the live assignments exactly.
  - Every variable, live or `# NAME=`, needs a `#` comment line directly above it.
- **`settings.py`**
  - `MAILERS = {"default": {"BACKEND": console}}` at L192-199.
  - There is no `SECURE_*`, `SILENCED_SYSTEM_CHECKS` or `AUTHENTICATION_BACKENDS`.
  - The middleware starts with `SecurityMiddleware`, then WhiteNoise, so static files also go through the SSL redirect.
- **Django 6.1 checks**
  - W008, W012 and W016 need `is True`. W004 needs a truthy HSTS value.
  - W005 and W021 only fire when HSTS > 0 and includeSubDomains/preload is not `True`.
  - `mail.E001` reads `MAILERS["default"]["BACKEND"]` and errors on console, dummy, filebased or locmem.
- **`SecurityMiddleware`**
  - Matches `SECURE_REDIRECT_EXEMPT` with `re.search` against `request.path.lstrip("/")`, so the pattern is `r"^favicon\.ico$"`.
  - The redirect is a 301 to `https://<host><full path>`.
  - It reads the settings when the handler is built, so `override_settings` works with the test client.

### Test-time `DEBUG`
- Locally, `.env` has `DEBUG=True`. CI sets only `SECRET_KEY` and `OPENAI_API_KEY`, so settings load with `DEBUG=False`.
- About 200 plain-HTTP `self.client` calls would get 301s once the SSL redirect follows `not DEBUG`.
- There is no test settings module and no shared base class.
- Django's runner sets `settings.DEBUG = False` at runtime, but values derived from `DEBUG` are computed at import.

### django-axes 8.3.1
- **Wiring**
  - App `"axes"`, middleware `"axes.middleware.AxesMiddleware"` (last).
  - Backends `["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]`.
  - It ships migrations 0001–0010 (`AccessAttempt`, …). Checks W002 and W003 fire if the middleware or backend is missing.
- **Defaults to override**
  - `AXES_FAILURE_LIMIT` is 3.
  - `AXES_LOCKOUT_PARAMETERS` is `["ip_address"]`; username + IP is `[["username", "ip_address"]]`.
  - `AXES_COOLOFF_TIME` is `None`, which means a permanent lock. An int means hours, so use `timedelta(minutes=15)`.
  - `AXES_RESET_ON_SUCCESS` is `False`.
  - Defaults we keep: `AXES_HANDLER` is the database handler (shared by every worker), and `AXES_HTTP_RESPONSE_CODE` is 429.
- **Lockout behaviour**
  - It locks **at** the Nth failure: with limit 5, the 5th failed POST already returns 429.
  - Once locked, `AxesStandaloneBackend.authenticate` raises `PermissionDenied`, so even the right password gets 429.
  - By default, attempts made during the lockout are recorded and restart the cool-off, which is measured from the last failure.
  - The response comes from `AXES_LOCKOUT_TEMPLATE` through `render(request, …, status=429)`, so context processors run and `base.html` works. The context holds `failure_limit`, `username`, `cooloff_time` and `cooloff_timedelta`.
  - The middleware swaps the view's response after the view runs. A GET of the log-in page is never blocked.
- **Admin**: Django's admin log-in calls `authenticate(request, …)`, so it is covered with the same template.
- **Client IP**: django-ipware isn't installed, so axes uses `REMOTE_ADDR`. The test client defaults it to `127.0.0.1`, and `client.post(..., REMOTE_ADDR="10.0.0.2")` overrides it.
- **Time in tests**: patching is awkward (`axes.handlers.proxy.now` plus `auto_now_add`). Shifting `AccessAttempt.attempt_time` back with `update(F(...) - timedelta)` is simpler.
- **Risks found**
  - `SignUpView` calls `login(request, user)` without a backend. With two backends configured, Django raises `ValueError`, which breaks every sign-up POST, so the call has to pass `backend=`.
  - `Client.login()` calls `authenticate()` without a request, which axes rejects. No test in `src/` uses it; all use `force_login`, which picks `ModelBackend`.
  - Existing tests post at most 2 failed log-ins each, below the limit.
- **Compatibility**: the classifiers stop at Django 6.0, but the code uses only stable APIs and no version checks. The suite has to confirm it works.

### Site-wide pages
- `core/tests/pages.py` has the frozen `Page(name, path, logged_in)`.
- `AllPagesMixin.get()` GETs the page and asserts 200. The page walks are `test_layout`, `test_favicon`, `test_forms` (filtered by `FORM_PAGES`) and `test_nav`.
- A 429 page needs the dataclass extended, with an expected status and a way to produce the response (5 failed POSTs).

### CI and Docker
- **`config/tests/test_ci.py`**
  - Flattens each step's `with:` and `env:` children into its dict, and pins the `quality` steps exactly through `GATE`.
  - Pins the job env exactly, and requires `secrets.` to be absent from the whole file.
  - The job's `ci-dummy-secret-key` is too short for W009, so the deploy step needs a step-level key.
- **`config/tests/test_docker.py`**
  - Pins requirements by regex (`RequirementsTests`, `("whitenoise", "gunicorn")`, plus an import check).
  - Checks only the smoke script's presence, shebang, `bash -n` and two strings.
- **`scripts/docker-smoke.sh`**
  - `start name opts…` runs a container and waits for it to be healthy.
  - `cleanup` lists every container name by hand.
  - The page and form checks use plain `http://` with curl (no `-L`) and a cookie jar.
- **The Dockerfile `HEALTHCHECK`** uses `urllib` against `http://127.0.0.1:8000/favicon.ico`, which follows redirects.

## Design decisions

### Environment
- **Strict booleans for the new variables.** A new `optional_bool(env, name, default)` accepts `true/false/1/0/yes/no/on/off`, case-insensitive. Blank means the default, and anything else is `ImproperlyConfigured` naming the variable. A typo like `Ture` must never quietly turn HTTPS off, as `env.bool` would. `DEBUG` keeps `env.bool` (unchanged).
- **A strict integer.** `optional_non_negative_int(env, name, default)` follows the same blank rule and errors on non-integers and negative numbers.
- **The shape of the new `EnvSettings` fields.** `ssl_redirect`, `session_cookie_secure`, `csrf_cookie_secure`, `hsts_seconds` and `proxy_ssl_header` are resolved in `env.py`, with `DEFAULT_HSTS_SECONDS = 3600`. `settings.py` only assigns them, plus `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if … else None`. That keeps the rules unit-testable without reloading settings.
- **Every new variable is a commented-out example in `.env.example`** (`COMMENTED_EXAMPLES`). The file is for local `DEBUG=True` use, and blank lines would also leak through `--env-file`.

### Tests and checks
- **A project test runner keeps the suite on plain HTTP.** `TEST_RUNNER = "config.runner.TestRunner"`, a `DiscoverRunner` subclass, turns `SECURE_SSL_REDIRECT` off through `override_settings` for the whole run, so the suite behaves the same whatever `DEBUG` is (AC16). This is the only setting that changes responses to plain-HTTP test-client requests: Secure cookies are still sent by the test client, and HSTS is only sent on HTTPS. Tests of the redirect turn it back on with `override_settings`.
- **`check --deploy` is tested in a subprocess.** It runs `manage.py check --deploy --fail-level WARNING` with an explicit environment: `DEBUG=False`, a long dummy key, and every new `SECURE_*` variable blank, which means the default and overrides a developer's `.env`. This exercises the real import-time settings, not overrides.
- **Silenced checks.** `SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]`, with a comment (out of scope, by the user's decision).

### Email
- `MAILERS["default"]["BACKEND"]` is the console backend when `DEBUG`, otherwise `django.core.mail.backends.smtp.EmailBackend`, written out explicitly.

### django-axes settings
- `AXES_FAILURE_LIMIT = 5`
- `AXES_COOLOFF_TIME = timedelta(minutes=15)`
- `AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]`
- `AXES_RESET_ON_SUCCESS = True`
- `AXES_LOCKOUT_TEMPLATE = "accounts/locked_out.html"`
- The handler and the response code keep the axes defaults (database, 429), and a test pins both.

### Lockout timing
- Axes refuses the 5th failed attempt itself with the 429 page; the 6th, even with the right password, is refused too. That meets AC2, which only requires the 6th to be refused.
- Attempts made during a lockout restart the 15 minutes (axes default), which matches AC6's "since the last failure".

### Other
- **The lockout page text is literal** ("Try again in 15 minutes."). The test that pins it sits next to the test pinning `AXES_COOLOFF_TIME`, so changing one without the other is red.
- **Sign-up logs in with an explicit `backend="django.contrib.auth.backends.ModelBackend"`.** This is needed once two backends are configured.
- **`Page` gains `status: int = 200` and an optional `prepare` callable** (run before the GET or POST that renders it). The "locked out" page sends 5 failed log-ins and expects 429.
- **The smoke script's HTTP containers get a shared `HTTP=(-e SECURE_SSL_REDIRECT=False -e SESSION_COOKIE_SECURE=False -e CSRF_COOKIE_SECURE=False)` array.** A new `$ID-https-defaults` container, also added to `cleanup`, runs with the default settings. It checks:
  - it becomes healthy, and the favicon is served over HTTP,
  - `/` gives `301 https://…`,
  - there is no `Strict-Transport-Security` header over HTTP.

## Steps

### Environment
- [x] 1. `SECURE_SSL_REDIRECT` resolves from the environment.
  - Behaviour: it defaults to `not DEBUG`, an explicit `true`/`false` wins in both directions, and blank means the default. An unknown value (`maybe`) is `ImproperlyConfigured("The SECURE_SSL_REDIRECT environment variable must be true or false")`.
  - Test: `src/config/tests/test_env.py`
  - Impl: `src/config/env.py` (`optional_bool`, `EnvSettings.ssl_redirect`)
  - Covers: AC10, AC11
- [x] 2. `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` resolve with the same rules, in one table-driven test.
  - Test: `src/config/tests/test_env.py`
  - Impl: `src/config/env.py`
  - Covers: AC10, AC11
- [x] 3. `SECURE_HSTS_SECONDS` resolves from the environment.
  - Behaviour: 3600 when `DEBUG` is off and 0 when on. An explicit integer wins (including `0` with DEBUG off), and blank means the default. `abc`, `1.5` and `-1` are `ImproperlyConfigured` naming the variable ("must be a whole number of seconds, 0 or more").
  - Test: `src/config/tests/test_env.py`
  - Impl: `src/config/env.py` (`optional_non_negative_int`, `DEFAULT_HSTS_SECONDS`)
  - Covers: AC10, AC11
- [x] 4. `SECURE_PROXY_SSL_HEADER` is an opt-in boolean.
  - Behaviour: `False` when unset or blank in both DEBUG modes, `True` when set true, and an invalid value is an error.
  - Test: `src/config/tests/test_env.py`
  - Impl: `src/config/env.py` (`EnvSettings.proxy_ssl_header`)
  - Covers: AC12

### Test runner and settings wiring
- [x] 5. The suite runs on plain HTTP whatever `DEBUG` is.
  - Behaviour: `settings.TEST_RUNNER` is the project's runner. Its `setup_test_environment()` leaves `SECURE_SSL_REDIRECT` `False` even when it was `True`, and `teardown_test_environment()` restores it. The test calls them with `DiscoverRunner`'s own setup and teardown patched out, since the real environment is already set up.
  - Test: `src/config/tests/test_runner.py`
  - Impl: `src/config/runner.py` (`TestRunner(DiscoverRunner)`), `settings.py` (`TEST_RUNNER = "config.runner.TestRunner"`). It is not `config/test_runner.py`, because that name matches the `test*.py` discovery pattern.
  - Covers: AC16
- [x] 6. `settings.py` assigns the HTTPS settings from `EnvSettings`.
  - Settings: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, and `SECURE_PROXY_SSL_HEADER` (the tuple, or `None`).
  - `PATCHED_ENVIRON` gets non-default values for all five, so the `.env` leak guard covers them.
  - A wiring test asserts the patched values, a `reload_with(DEBUG="False", <the five blank>)` test asserts the secure defaults, and a `DEBUG="True"` test asserts the insecure ones.
  - Test: `src/config/tests/test_settings.py`
  - Impl: `src/config/settings.py`
  - Covers: AC10, AC11, AC12, AC15
- [x] 7. With the SSL redirect on, `/favicon.ico` is exempt.
  - Behaviour: under `override_settings(SECURE_SSL_REDIRECT=True)`, an HTTP GET of `/accounts/login/` gets a 301 to `https://testserver/accounts/login/`, while `/favicon.ico` is a 200 over HTTP.
  - Also in this module, two tests describe what Django already does, so they pass as soon as they're written: HSTS (`override_settings(SECURE_HSTS_SECONDS=3600)`) sends exactly `max-age=3600` over HTTPS and nothing over HTTP, and `SECURE_HSTS_INCLUDE_SUBDOMAINS`/`SECURE_HSTS_PRELOAD` are `False`.
  - Test: `src/core/tests/test_https.py`
  - Impl: `src/config/settings.py` (`SECURE_REDIRECT_EXEMPT = [r"^favicon\.ico$"]`)
  - Covers: AC13, AC14

### Email, deploy check, documentation and CI
- [x] 8. The email backend follows `DEBUG`: reloaded settings have the console backend with `DEBUG="True"` and SMTP with `DEBUG="False"`.
  - Test: `src/config/tests/test_settings.py`
  - Impl: `src/config/settings.py`
  - Covers: AC17
- [x] 9. `check --deploy` is clean.
  - Behaviour: a subprocess `manage.py check --deploy --fail-level WARNING` exits 0 with `DEBUG=False`, a 50+ character dummy key and blank `SECURE_*` variables. Before this step it fails on W005 and W021.
  - Test: `src/config/tests/test_deploy_check.py`
  - Impl: `src/config/settings.py` (`SILENCED_SYSTEM_CHECKS` with a comment)
  - Covers: AC18
- [x] 10. `.env.example` documents the five new variables as commented-out examples, each with a comment line above it. `VARIABLES` and `COMMENTED_EXAMPLES` are extended, and a test pins each example line.
  - Test: `src/config/tests/test_env_example.py`
  - Impl: `.env.example`
  - Covers: AC15
- [ ] 11. CI's `quality` job gets a "Deployment checks" step.
  - The step runs `python src/manage.py check --deploy --fail-level WARNING`, right after "Django system checks".
  - It has its own `env`: `DEBUG: "False"` and a 50+ character dummy `SECRET_KEY`, with no `secrets.`.
  - `GATE` in `test_ci.py` is extended with the step's exact flattened dict.
  - Test: `src/config/tests/test_ci.py`
  - Impl: `.github/workflows/ci.yml`
  - Covers: AC19

### Lockout (django-axes)
- [ ] 12. django-axes is installed and wired.
  - Requirement `django-axes>=8.3,<8.4` (pinned by regex, and `axes` is importable), the app `axes`, `AxesMiddleware` last.
  - `AUTHENTICATION_BACKENDS` lists the axes backend first, then `ModelBackend`.
  - `AXES_HANDLER` and the response code keep their defaults (database, 429) and are pinned.
  - `SignUpView` logs in with the explicit `ModelBackend`. The existing sign-up tests stay green, and `pip install -r requirements-dev.txt` installs the package.
  - Test: `src/accounts/tests/test_lockout.py` (`LockoutWiringTests`)
  - Impl: `requirements.txt`, `settings.py`, `accounts/views.py`
  - Covers: AC1, AC9
- [ ] 13. The 5th failure locks out username + IP.
  - Behaviour: the first 4 wrong-password POSTs for alice get 200 with the generic form error. After the 5th, a 6th POST with the **correct** password gets 429, no `_auth_user_id` in the session, and no session cookie for a logged-in user.
  - A `subTest` repeats it for a username that doesn't exist (AC5).
  - `AXES_FAILURE_LIMIT = 5` is pinned.
  - Test: `src/accounts/tests/test_lockout.py` (`LockoutTests`)
  - Impl: `settings.py`
  - Covers: AC2, AC5, AC9
- [ ] 14. The lockout applies only to the same username + IP.
  - Behaviour: after alice is locked out from `127.0.0.1`, alice logs in from `REMOTE_ADDR="10.0.0.2"`, and bob logs in from `127.0.0.1`.
  - `AXES_LOCKOUT_PARAMETERS` is pinned.
  - Test: `src/accounts/tests/test_lockout.py`
  - Impl: `settings.py`
  - Covers: AC3, AC9
- [ ] 15. The lockout page.
  - Behaviour: the 429 response uses `accounts/locked_out.html`, extending `base.html`.
    - title `Locked out · Learning Companion`, one `<h1>`
    - main text "Too many failed log-in attempts. Try again in 15 minutes."
    - neither the username nor whether the account exists
  - The same page is served for a lockout on `/admin/login/` (5 failed admin log-ins with `next=/admin/`; AC8).
  - `core/tests/pages.py` gets the `status` and `prepare` fields and a "locked out" page, so the layout, title, heading, button and favicon walks cover it.
  - Test: `src/accounts/tests/test_lockout.py`, `src/core/tests/pages.py`
  - Impl: `src/templates/accounts/locked_out.html`, `settings.py` (`AXES_LOCKOUT_TEMPLATE`)
  - Covers: AC4, AC8
- [ ] 16. The lockout lifts 15 minutes after the last failure.
  - Behaviour: after a lockout, with `AccessAttempt.attempt_time` shifted back 14 minutes, the correct password still gets 429. Shifted 15 minutes back from the last failure, it logs in (302 to `/dashboard/`).
  - `AXES_COOLOFF_TIME = timedelta(minutes=15)` is pinned next to the page text.
  - Test: `src/accounts/tests/test_lockout.py`
  - Impl: `settings.py`
  - Covers: AC6, AC9
- [ ] 17. A successful log-in resets the count.
  - Behaviour: 4 failures, then a successful log-in, a log-out and 4 more failures leave alice able to log in (no 429).
  - `AXES_RESET_ON_SUCCESS` is pinned.
  - Test: `src/accounts/tests/test_lockout.py`
  - Impl: `settings.py`
  - Covers: AC7

### Container, smoke script and docs
- [ ] 18. The smoke script covers the HTTPS defaults.
  - Behaviour: `SmokeScriptTests` pins that the script defines the `HTTP` overrides and passes them to the HTTP containers. It also pins the default-settings container (in `cleanup` too), its `301`/`https://` check and its `Strict-Transport-Security` check.
  - Then run `scripts/docker-smoke.sh` end to end. It needs Docker and its output goes in the step's commit message.
  - Test: `src/config/tests/test_docker.py`
  - Impl: `scripts/docker-smoke.sh`
  - Covers: AC20
- [ ] 19. Docs (no test, doc-only commit).
  - **README**
    - the env table rows for the five variables
    - "Run with Docker": local HTTP needs the three `-e …=False`, the HTTPS proxy needs `SECURE_PROXY_SSL_HEADER=True`, and `axes_reset` clears a lockout
    - the client IP behind a proxy is a known limitation
    - the smoke checks list
    - the CI bullet and the local gate block with `check --deploy`
  - **`CLAUDE.md`**
    - the settings, container and CI bullets
    - an Auth note on axes, the backends and sign-up's explicit backend
    - the test runner
  - Impl: `README.md`, `CLAUDE.md`
  - Covers: AC21

## Coverage

| AC | Steps |
|---|---|
| AC1 | 12 |
| AC2 | 13 |
| AC3 | 14 |
| AC4 | 15 |
| AC5 | 13 |
| AC6 | 16 |
| AC7 | 17 |
| AC8 | 15 |
| AC9 | 12, 13, 14, 16, 17 |
| AC10 | 1, 2, 3, 6 |
| AC11 | 1, 2, 3, 6 |
| AC12 | 4, 6 |
| AC13 | 7 |
| AC14 | 7 |
| AC15 | 6, 10, 19 |
| AC16 | 5 |
| AC17 | 8 |
| AC18 | 9 |
| AC19 | 11 |
| AC20 | 18 |
| AC21 | 19 |

**Why this order:** step 5 (the test runner) comes before step 6, because wiring the redirect into the settings would otherwise turn CI red. Step 9 runs before axes is installed, and steps 12–17 keep the check clean, since axes' own checks pass once it is wired.
