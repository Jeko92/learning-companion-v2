# DevOps: Dockerfile that serves the app
Issue: #20 · Branch: feature/docker

## Story
As someone running Learning Companion, I want to build one container image and start it with `docker run`, so that the app serves its pages, styles and data in production mode (gunicorn, `DEBUG` off) without a local Python setup, and its SQLite data survives container restarts.

## Acceptance criteria

### Settings
- [ ] AC1 `DATABASES` is read from a new optional `DATABASE_URL` variable through django-environ. The default is the SQLite file used today (`src/db.sqlite3`), so local development and the existing database don't change. A blank value also means the default. The process environment wins over `.env`. A value django-environ can't parse is an `ImproperlyConfigured` that names `DATABASE_URL`. Tested in `config/tests/test_env.py` and `test_settings.py`.
- [ ] AC2 A new optional `CSRF_TRUSTED_ORIGINS` variable is a comma-separated list, trimmed, with empty entries dropped and empty by default. Every entry must start with `http://` or `https://`; otherwise it's an `ImproperlyConfigured` that names the variable (never the value). It is wired to `settings.CSRF_TRUSTED_ORIGINS`.
- [ ] AC3 `.env.example` documents `DATABASE_URL` and `CSRF_TRUSTED_ORIGINS`, each with a comment above it, and `config/tests/test_env_example.py` lists them.
- [ ] AC4 Static files are served by WhiteNoise:
  - `STATIC_ROOT` is set, and `collectstatic` writes there; the directory is git-ignored.
  - `whitenoise.middleware.WhiteNoiseMiddleware` comes right after `SecurityMiddleware`.
  - The `staticfiles` storage is `whitenoise.storage.CompressedStaticFilesStorage`, with no hashed names, so `{% static %}` URLs stay as they are (the pinned `/static/css/tailwind.css` link test stays green).
  - The default storage is unchanged.
- [ ] AC5 `requirements.txt` adds `whitenoise` and `gunicorn` with version ranges, like the existing pins.

### Image
- [ ] AC6 A multi-stage `Dockerfile` on official `python:3.14-slim` images:
  - **Builder stage:** downloads the pinned Tailwind binary and builds the CSS (`tailwind build`, with the vendored daisyUI files), then runs `collectstatic`.
  - **Final stage:** gets the app and the collected static files, but no Tailwind binary, no `.env` and no database. It runs as a non-root user and exposes port 8000.
  - It declares a volume for the data directory and sets `DATABASE_URL` to a SQLite file in it.
  - It has no secrets: `SECRET_KEY` and `OPENAI_API_KEY` are supplied at `docker run` (`-e` or `--env-file`).

  A Django test reads the `Dockerfile` and checks these facts.
- [ ] AC7 On start, the container applies migrations (`migrate --noinput`) and then runs gunicorn on `config.wsgi` at `0.0.0.0:8000` as the main process, so `docker stop` stops it cleanly. Without `SECRET_KEY` or `OPENAI_API_KEY`, the container exits with a non-zero code and the `ImproperlyConfigured` message names the missing variable.
- [ ] AC8 A `HEALTHCHECK` requests the public `/favicon.ico` inside the container, using Python and no extra package. `docker ps`/`docker inspect` report the container healthy once gunicorn answers.
- [ ] AC9 `.dockerignore` keeps the following out of the build context:
  - `.env` and `.git`;
  - `.venv` and caches;
  - local databases (`*.sqlite3*`);
  - the built CSS and `src/.django_tailwind_cli/`;
  - collected static files;
  - `work/` and `.claude/`.

  A test checks these entries.

### Smoke check
- [ ] AC10 A committed `scripts/docker-smoke.sh` builds the image, runs it with dummy keys and a fresh named volume, waits until it is healthy, and then checks:
  - `GET /` is 200 and contains "Learning Companion".
  - `GET /static/css/tailwind.css` is 200 with a CSS content type and contains a daisyUI class. With `Accept-Encoding: gzip`, it is served gzip-encoded.
  - `GET /favicon.ico` is 200 with an icon type.
  - Sign-up works through the real form (CSRF token and a database write).
  - The data survives a new container on the same volume: log-in works there.
  - The process doesn't run as root.
  - The image has no `.env` and no Tailwind binary.
  - A run without `SECRET_KEY` exits non-zero and names the variable.

  It removes everything it created (containers, volume, image tag), exits 0 only when every check passed, and prints each check's result. It runs in final-review and is meant for CI later (#21). It is not part of the hooks' test suite.

### Unchanged and documented
- [ ] AC11 Local development is unchanged:
  - `runserver` with `DEBUG=True` serves styles as before;
  - the default database is the same file;
  - the full suite is green and lint is clean, with no Docker needed to run them;
  - every existing `assertNumQueries` pin and page test is unchanged.
- [ ] AC12 `README.md` gains a "Run with Docker" section: build, run with `--env-file` or `-e`, the port, the volume, and how to run the smoke check. `CLAUDE.md` (Stack, Commands, Layout) describes:
  - the image and its two stages;
  - WhiteNoise and `STATIC_ROOT`;
  - `DATABASE_URL` and `CSRF_TRUSTED_ORIGINS`;
  - the entrypoint and the smoke script.

## Out of scope
- Postgres, docker-compose, deployment, publishing the image to a registry
- Security hardening (secure cookies, HSTS, SSL redirect, proxy SSL header, login throttling, a clean `check --deploy`): all of it stays in #36 deploy-hardening, at the user's choice
- CI (#21 `ci-tests`), which can reuse the smoke script
- Hashed or manifest static file names (`CompressedManifestStaticFilesStorage`)
- Changing the app's pages or behaviour

## Notes
- Decisions made with the user in refinement (2026-10-04):
  - WhiteNoise with `CompressedStaticFilesStorage`, chosen over hashed manifest storage and over Django's `static()`.
  - `DATABASE_URL`, chosen over a SQLite-only path variable and over mounting over `src/`.
  - Verification: Django unit tests for the settings and the Docker files, plus a scripted build-and-run smoke check in final-review.
  - Extras in scope: multi-stage and non-root, `CSRF_TRUSTED_ORIGINS`, `HEALTHCHECK`. The user first selected security hardening, then chose to leave all of it in #36.
- Context found:
  - `STATIC_ROOT` isn't set today, and nothing serves `/static/` with `DEBUG` off.
  - `DATABASES` hardcodes `BASE_DIR / "db.sqlite3"`.
  - There is no Docker or CI file and no `.dockerignore`, so `COPY . .` would bring in `.env`, `.venv` and `src/db.sqlite3`.
- django-tailwind-cli 4.8 downloads `tailwindcss-linux-<x64|arm64>` (glibc) from GitHub for the pinned `TAILWIND_CLI_VERSION`, so the builder stage needs network access and a Debian-based (slim, not Alpine) image. The binary is about 80 MB, which is why it stays in the builder stage.
- `SECRET_KEY` and `OPENAI_API_KEY` stay required at startup (`config/env.py`); a dummy OpenAI key is enough to serve pages. `DEBUG` defaults to `False`, and the default `ALLOWED_HOSTS` (`localhost,127.0.0.1`) covers `docker run -p 8000:8000` reached through localhost and the in-container healthcheck.
- The favicon view reads `STATICFILES_DIRS[0]` (`src/assets`), so the final stage must keep `src/assets` as well as `STATIC_ROOT`.
- New settings follow the existing env pattern: an `EnvSettings` field in `config/env.py`, tests in `test_env.py` (`environ()` helper) and `test_settings.py` (`PATCHED_ENVIRON`), and the variable list in `test_env_example.py`.
- Handout: `instructions/challenge.md` → "Containerize and add CI": "Write a `Dockerfile` for the app using the framework's common base image and startup command, and confirm `docker build` + `docker run` serves the app."
- Docker 29.8 is available locally for the smoke check.
- **Approval:** the user approved the acceptance criteria (AC1–AC12) on 2026-10-04.
