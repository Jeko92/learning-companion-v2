# Setup: settings from environment (.env)
Issue: #1 · Branch: feature/setup-env-settings

## Story
As a developer deploying or running the Learning Companion, I want secrets and environment-specific settings to come from the environment or a `.env` file, so that no secret is committed and each environment can be configured without code changes.

## Acceptance criteria
- [x] AC1 `SECRET_KEY` is read from the `SECRET_KEY` variable, and the generated `django-insecure-...` key no longer appears anywhere in `src/config/settings.py`.
- [x] AC2 If `SECRET_KEY` is unset or empty, loading the settings raises `ImproperlyConfigured`, and the message names `SECRET_KEY`.
- [x] AC3 `DEBUG` is read from the `DEBUG` variable as a boolean (`True`/`False`, `1`/`0`, `yes`/`no` are understood). `DEBUG=False` gives `False`.
- [x] AC4 If `DEBUG` is unset, `DEBUG` is `False`.
- [x] AC5 `ALLOWED_HOSTS` is read from the `ALLOWED_HOSTS` variable as a comma-separated list, with whitespace around entries trimmed. `"example.com, www.example.com"` gives `["example.com", "www.example.com"]`.
- [x] AC6 If `ALLOWED_HOSTS` is unset, it is `["localhost", "127.0.0.1"]`.
- [x] AC7 Variables defined in a `.env` file at the repo root are loaded into the settings.
- [x] AC8 If a variable is set in both the process environment and `.env`, the process environment value wins.
- [x] AC9 A missing `.env` file is not an error. The settings load from the process environment alone, as long as `SECRET_KEY` is set there.
- [x] AC10 A committed `.env.example` lists every variable the settings read (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`), each with an explanatory comment, and sets `DEBUG=True` as the local-dev value.

## Out of scope
- Database configuration (SQLite stays as generated).
- The OpenAI API key (ticket `ai-client`).
- CI/Docker wiring of these variables (tickets `ci-tests`, `docker`). Those tickets must provide `SECRET_KEY`.

## Notes
Answers from refinement (2026-10-01):
- `DEBUG` defaults to `False` when unset. Local dev turns it on through `.env`.
- A missing `SECRET_KEY` fails fast, with no dev fallback. Every checkout needs a `.env` (copied from `.env.example`) before `runserver` or the test suite will start.
- `ALLOWED_HOSTS` is comma-separated and defaults to `localhost,127.0.0.1`.
- The process environment takes precedence over `.env` (`.env` only fills in variables that aren't already set). This was first answered as ".env wins" and changed to this at approval on 2026-10-01, so CI, Docker and one-off shell overrides work. Tests still must not depend on the developer's real `.env`: settings resolution has to be testable against a controlled environment and a controlled `.env` file.
- The library is `django-environ` (from the issue). It goes in `requirements.txt`.
- `.env` is already git-ignored. Keep it that way.
- Required deliverable that a test can't verify: update the setup steps in `README.md` and `CLAUDE.md` (copy `.env.example` to `.env` and fill in `SECRET_KEY`, plus a command to generate one).
- This ticket was previously closed on the board without its work landing. It was reopened on 2026-10-01 and is being redone from scratch.
