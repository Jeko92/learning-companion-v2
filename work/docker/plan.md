# Plan: docker

## Research summary

**Settings and env** (`src/config/`):
- `env.py` has `@dataclass(frozen=True) EnvSettings` (`secret_key`, `debug`, `allowed_hosts`, `openai_api_key`, `openai_model`) and `resolve_settings(environ, env_file)`.
  - It subclasses `environ.Env` with `ENVIRON = dict(environ)`, so `read_env` fills a copy and the process environment wins over `.env`.
  - `required_raw()` raises `ImproperlyConfigured(f"The {name} environment variable must be set and not empty")`, which names the variable and never the value.
  - `ALLOWED_HOSTS` is parsed with `env.list(...)`, trimmed, with empty entries dropped. `OPENAI_MODEL` blank means the default.
- `settings.py` wires `_env = resolve_settings(os.environ, BASE_DIR.parent / ".env")` into `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `OPENAI_*`.
  - `DATABASES` hardcodes `BASE_DIR / "db.sqlite3"` (`BASE_DIR` is `src/`).
  - `MIDDLEWARE` is the stock list.
  - `STATIC_URL = "static/"`, `STATICFILES_DIRS = [BASE_DIR / "assets"]`, with no `STATIC_ROOT` and no `STORAGES`.
  - `.gitignore` already ignores `staticfiles/`, `db.sqlite3` and `.env`.

**Tests:**
- `config/tests/test_env.py`: `ResolveSettingsTests(SimpleTestCase)`, 21 tests, with an `environ(**values)` helper (adds a dummy `OPENAI_API_KEY`), `MISSING_ENV_FILE`, `self.resolve()` and `self.write_env_file()`.
  - Names are behaviour sentences, with dicts of cases in `subTest`.
  - Errors use `assertRaisesMessage`, or an exact `assertEqual(str(raised.exception), …)` that guarantees the value isn't echoed.
- `config/tests/test_settings.py`: `SettingsWiringTests` patches `os.environ` with `PATCHED_ENVIRON`, where every variable is set and non-default so a developer's `.env` can't leak in. It reloads `config.settings` and reloads it again in cleanup. `reload_with(**overrides)` covers per-case changes.
- `config/tests/test_env_example.py`: a `VARIABLES` list that must exactly match `.env.example`'s names, each with a `#` comment line directly above it.
- Repo-root files are read through `settings.BASE_DIR.parent / "<file>"`. `ai/tests/test_apps.py` pins `openai>=x,<y` in `requirements.txt` with a regex, which is the template for the new pins.
- No test asserts `MIDDLEWARE`, `STORAGES`, `STATIC_ROOT` or `DATABASES`. `core/tests/test_home.py:124` pins `<link rel="stylesheet" href="/static/css/tailwind.css">`, and `test_favicon.py` pins the `/static/favicon.*` hrefs, so any manifest (hashed) storage would break them. The favicon view reads `STATICFILES_DIRS[0]` (`src/assets`).

**Libraries** (verified in a throwaway venv on Python 3.14.8 and Django 6.1.1):
- **django-environ 0.14 `Env.db_url_config()`:**
  - `sqlite:////abs/path` gives that absolute `NAME`.
  - Garbage returns `{}` with a `UserWarning`, never an exception.
  - Unknown schemes (`foo://…`, `http://…`) come back as `ENGINE "foo"`/`"http"` and only fail at the first connection, with messages that don't name `DATABASE_URL`.
  - `env.db_url()` with `DATABASE_URL=` (blank) returns `{}`, not the default.

  So the code validates the result itself (the engine must be one of `Env.DB_SCHEMES.values()`) and treats blank as unset. Paths are `unquote_plus`-decoded, so no default URL is built from `BASE_DIR`; the default stays a plain dict.
- **whitenoise 6.12.0** (Python 3.10–3.14; classifiers stop at Django 6.0, but it works on 6.1.1):
  - `CompressedStaticFilesStorage` writes `.gz` files at `collectstatic` (`.br` only with `brotli`), and the middleware serves `Content-Encoding: gzip` when the request's `Accept-Encoding` allows it.
  - When `STATIC_ROOT` is set but the directory doesn't exist, the middleware issues `UserWarning: No directory at: …` (once per process) and doesn't error. Locally the suite runs without `collectstatic`, so it would hit this warning.
  - `CompressedManifestStaticFilesStorage` raises `Missing staticfiles manifest entry` without `collectstatic`.
- **gunicorn 26.2.0** (runs on 3.14.8):
  - The default bind is `127.0.0.1:8000`. Workers come from `WEB_CONCURRENCY` (default 1). The access log is off by default.
  - It creates a control socket under `$HOME` (noise for a user without a home directory), so `--no-control-socket` is needed. `--worker-tmp-dir /dev/shm` is recommended in Docker.
  - The sync worker's default `--timeout 30` equals the OpenAI client's 30 s per-phase timeout, so a slow summary could get the worker killed.
- **`python:3.14-slim`** is Debian 13 trixie with Python 3.14.8. It has no curl or wget, so the healthcheck uses Python's `urllib`.
- **django-tailwind-cli 4.8.1:** `manage.py tailwind build` and `collectstatic` both import the full settings, so `SECRET_KEY` and `OPENAI_API_KEY` must be set (dummies) during the build; there's no database access. It downloads `tailwindcss-linux-<x64|arm64>-4.3.3` (glibc, about 80 MB) from GitHub into `src/.django_tailwind_cli/` unless an executable is already there. The local macOS binary must stay out of the build context.
- **Hosts:** `ALLOWED_HOSTS` ignores the port. With the default `localhost,127.0.0.1`, both `127.0.0.1:8000` and `localhost:8000` are accepted, so the healthcheck uses `127.0.0.1` (gunicorn on `0.0.0.0` is IPv4-only).

**Local environment:** Docker 29.8 is available. `.venv` doesn't have whitenoise or gunicorn yet, so `pip install -r requirements-dev.txt` runs in step 1.

## Design decisions
1. **`DATABASE_URL`** is validated in `env.py`, and its default stays in `settings.py`.
   - `EnvSettings.database` is the parsed config dict, or `None` when the variable is unset or blank.
   - `settings.py` uses it, or falls back to today's exact dict (`BASE_DIR / "db.sqlite3"`), so local development is byte-for-byte unchanged.
   - A value whose parsed `ENGINE` isn't one of `Env.DB_SCHEMES.values()` (including `{}` for garbage) raises the fixed `ImproperlyConfigured("The DATABASE_URL environment variable is not a valid database URL")`. That message never echoes the value, because a URL can carry a password.
   - django-environ's own `UserWarning` is suppressed (`warnings.catch_warnings`), since the error replaces it.
2. **`CSRF_TRUSTED_ORIGINS`** uses the `ALLOWED_HOSTS` parsing: a trimmed comma list with empty entries dropped, `[]` by default. Any entry that doesn't start with `http://` or `https://` raises the fixed `ImproperlyConfigured("The CSRF_TRUSTED_ORIGINS environment variable must list origins that start with http:// or https://")`.
3. **WhiteNoise:**
   - `STATIC_ROOT = BASE_DIR / "staticfiles"`, which is already git-ignored.
   - `WhiteNoiseMiddleware` goes right after `SecurityMiddleware`.
   - `STORAGES = {"default": FileSystemStorage, "staticfiles": whitenoise CompressedStaticFilesStorage}`, with no hashed names (the ticket's choice, and the pinned hrefs stay).
   - The middleware's "No directory at" warning: `settings.py` filters exactly that warning (message regex, `UserWarning`, module `whitenoise`) with a comment explaining why. Local runs and the test suite never run `collectstatic`, and the container build does (the smoke check proves the CSS is served). Without the filter, every test run and every `runserver` start would print it.
4. **One image layout:** the app is in `/app` (`/app/src` is `BASE_DIR`), the virtualenv in `/opt/venv` and the data in `/app/data` (a `VOLUME`). `DATABASE_URL=sqlite:////app/data/db.sqlite3` is set in the image, and `STATIC_ROOT` is `/app/src/staticfiles`.
5. **Stages:**
   - **`build`:** installs requirements into `/opt/venv`, copies `src/`, then runs `tailwind build` and `collectstatic --noinput`, with build-only dummy `SECRET_KEY` and `OPENAI_API_KEY` set inline on that `RUN` (never `ENV` or `ARG`, so they don't persist into any image layer's config).
   - **Final:** a fresh `python:3.14-slim` with a non-root `app` user (fixed uid 10001). It copies `/opt/venv`, `src/` from the context (without the binary, the CSS and the database, through `.dockerignore`) and the collected `staticfiles/` from `build`. `/app/data` is created and owned by `app`, so a fresh named volume inherits that ownership.
6. **Startup:**
   - `docker/entrypoint.sh` (`set -eu`) runs `python src/manage.py migrate --noinput`, then `exec "$@"`. A missing key fails `migrate` with the `ImproperlyConfigured` that names it, so the container exits non-zero.
   - `CMD` is `gunicorn --chdir src config.wsgi:application --bind 0.0.0.0:8000 --access-logfile - --worker-tmp-dir /dev/shm --no-control-socket --timeout 90`. The 90 s timeout is above the AI calls' 30 s per-phase timeout.
   - Workers follow `WEB_CONCURRENCY` (gunicorn's own variable).
   - Exec-form `ENTRYPOINT` and `CMD` make gunicorn PID 1, so `docker stop` (SIGTERM) shuts it down gracefully.
7. **`HEALTHCHECK`:** `python -c` with `urllib.request.urlopen("http://127.0.0.1:8000/favicon.ico", timeout=5)`, plus a short interval and a start period.
8. **The smoke script is the acceptance harness for the image:**
   - `scripts/docker-smoke.sh` (bash, `set -euo pipefail`) uses unique names (image tag, containers and volume suffixed with `$$`), a `trap` cleanup, and a random host port (`-p 127.0.0.1::8000`, read back with `docker port`).
   - It prints `PASS`/`FAIL` per check and exits non-zero on the first failure, after cleanup.
   - In the suite, a test only checks that it exists, is executable and passes `bash -n`. Running it needs Docker and takes minutes, so it isn't a unit test. It is run in the steps that build the image and in final-review.
9. **Deployment-file tests** live in a new `src/config/tests/test_docker.py` (`SimpleTestCase`, `ROOT = settings.BASE_DIR.parent`), next to `test_env_example.py`, which does the same kind of repo-root checks. The `Dockerfile` checks parse the stages (split on `FROM`) and assert per-stage facts, not exact lines.

## Steps
- [x] 1. `whitenoise` and `gunicorn` are range-pinned requirements (`whitenoise>=6.12,<7`, `gunicorn>=26.2,<27`), and both import. Install them into the local `.venv` (`./.venv/bin/pip install -r requirements-dev.txt`) before going green. — test: `src/config/tests/test_docker.py` (`RequirementsTests`: one regex-pinned line each, as `ai/tests/test_apps.py` does for openai) — impl: `requirements.txt` — covers: AC5
- [x] 2. `resolve_settings` reads an optional `DATABASE_URL` into `EnvSettings.database`.
  - Unset or blank gives `None`. `sqlite:////abs/x.sqlite3` gives the sqlite engine with that `NAME`, and a postgres URL gives the postgres engine.
  - The environment wins over `.env`.
  - Garbage (`not-a-url`) and an unknown scheme (`foo://x/y`) each raise the exact fixed message, which doesn't contain the value, and no django-environ warning escapes (`assertNoLogs`/`warnings` check).

  — test: `src/config/tests/test_env.py` — impl: `src/config/env.py` — covers: AC1
- [x] 3. `settings.DATABASES["default"]` comes from `DATABASE_URL` when set. When it's blank, it is exactly today's dict (`ENGINE` sqlite3, `NAME == BASE_DIR / "db.sqlite3"`). `PATCHED_ENVIRON` gains a non-default `DATABASE_URL` (a sqlite URL under the temp dir), so a developer's `.env` can't leak in. — test: `src/config/tests/test_settings.py` — impl: `src/config/settings.py` — covers: AC1, AC11
- [x] 4. `resolve_settings` reads an optional `CSRF_TRUSTED_ORIGINS` into `EnvSettings.csrf_trusted_origins`. It is trimmed with empty entries dropped and `[]` by default, and the environment wins over `.env`. An entry without `http://` or `https://` (`example.com`, `ftp://x`) raises the exact fixed message, which doesn't contain the value. — test: `src/config/tests/test_env.py` — impl: `src/config/env.py` — covers: AC2
- [x] 5. `settings.CSRF_TRUSTED_ORIGINS` is wired from the environment (`PATCHED_ENVIRON` gains a non-default list), and blank gives `[]`. — test: `src/config/tests/test_settings.py` — impl: `src/config/settings.py` — covers: AC2
- [x] 6. `.env.example` documents `DATABASE_URL` (commented-out example `sqlite:////app/data/db.sqlite3`, blank meaning `src/db.sqlite3`) and `CSRF_TRUSTED_ORIGINS` (blank), each with a comment above it, and `VARIABLES` lists both. — test: `src/config/tests/test_env_example.py` — impl: `.env.example` — covers: AC3
- [x] 7. WhiteNoise configuration:
  - `STATIC_ROOT` is `BASE_DIR / "staticfiles"` and is git-ignored (`git check-ignore`, or the `.gitignore` entry).
  - `MIDDLEWARE[1]` is `whitenoise.middleware.WhiteNoiseMiddleware`, right after `SecurityMiddleware`.
  - `STORAGES["staticfiles"]["BACKEND"]` is `whitenoise.storage.CompressedStaticFilesStorage`, and `STORAGES["default"]` is Django's `FileSystemStorage`.

  — test: `src/config/tests/test_settings.py` (`StaticFilesSettingsTests`) — impl: `src/config/settings.py` — covers: AC4
- [ ] 8. Collected static files are served compressed with `DEBUG` off. With `override_settings(STATIC_ROOT=<temp dir>)` and `call_command("collectstatic", interactive=False, verbosity=0)` in the test:
  - `GET /static/favicon.svg` with `Accept-Encoding: gzip` returns 200 with `Content-Encoding: gzip`;
  - without that header it returns the plain file;
  - the page's `{% static %}` hrefs are unchanged.

  Also, loading the middleware with a missing `STATIC_ROOT` emits no "No directory at" warning (the settings filter, decision 3).

  — test: `src/config/tests/test_static_files.py` — impl: `src/config/settings.py` (warning filter; the rest from step 7) — covers: AC4, AC11
- [ ] 9. `.dockerignore` lists:
  - `.env` and `.git`;
  - `.venv`, `__pycache__` and `.ruff_cache`;
  - `*.sqlite3*`;
  - `src/assets/css/tailwind.css` and `src/.django_tailwind_cli`;
  - `src/staticfiles`;
  - `work` and `.claude`.

  — test: `src/config/tests/test_docker.py` (`DockerignoreTests`) — impl: `.dockerignore` — covers: AC9
- [ ] 10. The smoke script exists, is executable and passes `bash -n`. It performs the checks AC10 lists, in the order decision 8 describes. It fails at this point if actually run, because there's no `Dockerfile` yet; that is expected, and step 11 makes it pass. — test: `src/config/tests/test_docker.py` (`SmokeScriptTests`) — impl: `scripts/docker-smoke.sh` — covers: AC10
- [ ] 11. The `Dockerfile` and its entrypoint (decisions 4–7). The test parses the stages:
  - Both stages are `FROM python:3.14-slim`, and the first is `AS build`.
  - The build stage installs `requirements.txt` and runs `tailwind build` and `collectstatic --noinput`, with the dummy keys only inline on that `RUN`.
  - The final stage:
    - has a non-root `USER`, `EXPOSE 8000`, `VOLUME` `/app/data` and `ENV DATABASE_URL=sqlite:////app/data/db.sqlite3`;
    - copies `/opt/venv` and the `staticfiles` from `build`;
    - has a `HEALTHCHECK` that requests `127.0.0.1:8000/favicon.ico` through Python;
    - uses exec-form `ENTRYPOINT` (the entrypoint script) and `CMD` (gunicorn on `config.wsgi:application`, `0.0.0.0:8000`);
    - has no `SECRET_KEY` or `OPENAI_API_KEY` in any `ENV` or `ARG`.
  - `docker/entrypoint.sh` is executable, uses `set -eu`, runs `migrate --noinput` and ends with `exec "$@"`.

  Green also requires `docker build` to succeed and `scripts/docker-smoke.sh` to pass end to end; record its output in the commit message body.

  — test: `src/config/tests/test_docker.py` (`DockerfileTests`, `EntrypointTests`) — impl: `Dockerfile`, `docker/entrypoint.sh` — covers: AC6, AC7, AC8, AC10
- [ ] 12. Documentation:
  - **`README.md`:** a "Run with Docker" section (build; run with `--env-file .env` or `-e SECRET_KEY=… -e OPENAI_API_KEY=…`; `-p 8000:8000`; `-v learning-companion-data:/app/data`; `WEB_CONCURRENCY`; `CSRF_TRUSTED_ORIGINS` for a non-localhost origin; `scripts/docker-smoke.sh`), and the new variables in the settings section.
  - **`CLAUDE.md`:**
    - Stack: the image and its two stages, WhiteNoise and `STATIC_ROOT` plus the warning filter, `DATABASE_URL`, `CSRF_TRUSTED_ORIGINS`, the entrypoint and the smoke script.
    - Commands: `docker build`, `docker run`, the smoke script.
    - Layout: `Dockerfile`, `.dockerignore`, `docker/`, `scripts/`.

  No `src/` change. — test: none (docs) — impl: `README.md`, `CLAUDE.md` — covers: AC12

## Coverage
| AC | Steps |
|---|---|
| AC1 `DATABASE_URL` | 2, 3 |
| AC2 `CSRF_TRUSTED_ORIGINS` | 4, 5 |
| AC3 `.env.example` | 6 |
| AC4 WhiteNoise / `STATIC_ROOT` | 7, 8 |
| AC5 requirements | 1 |
| AC6 multi-stage image | 11 (file test + build + smoke) |
| AC7 entrypoint, migrations, gunicorn, missing key | 11 (file test + smoke) |
| AC8 `HEALTHCHECK` | 11 (file test + smoke waits for healthy) |
| AC9 `.dockerignore` | 9 |
| AC10 smoke script | 10 (script), 11 (passes end to end); final-review reruns it |
| AC11 local dev unchanged | 3 (default DB dict), 8 (no warning noise, hrefs), the suite green after every step |
| AC12 docs | 12 |
