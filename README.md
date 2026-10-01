# Learning Companion

Django 6.1 project on Python 3.14.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
./.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# paste the printed key into .env as SECRET_KEY=...
./.venv/bin/python src/manage.py migrate
./.venv/bin/python src/manage.py runserver
```

Settings come from the environment via `django-environ`, read in `src/config/env.py`:

| Variable | Default when unset | Notes |
|---|---|---|
| `SECRET_KEY` | none, so startup fails | Required and must not be empty |
| `DEBUG` | `False` | `.env.example` sets `True` for local development |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated. If it's set but empty, every host is rejected when `DEBUG` is off |

Values are read from the process environment first. `.env` at the repo root only fills in variables that aren't already set. `.env` is git-ignored, and `.env.example` documents every variable. Write one `NAME=value` per line with no spaces around `=`. `DEBUG=True` is for local development only. The test suite needs `SECRET_KEY` too, so set up `.env` before running the tests.

## Tests and lint

```bash
./.venv/bin/python src/manage.py test src
./.venv/bin/ruff check .
./.venv/bin/ruff format .
```

## Layout

- `src/manage.py`, `src/config/`: Django project (settings, URLs, ASGI/WSGI)
- `src/<app>/`: Django apps, each with its own tests
- `work/`: workflow artifacts per ticket (`ticket.md`, `plan.md`, `review.md`)
- `.claude/`: workflow rules, skills, and hooks

## Workflow

Feature work goes through the ticket pipeline described in
`.claude/rules/workflow.md` (refine, plan, TDD implement, review). Tickets are
issues on the GitHub project board; `work/backlog.md` is a local mirror of it.
Run `factory-manager` (or `/loop /factory-manager`) to move the pipeline
forward one step at a time.

Branching follows gitflow (`.claude/rules/git.md`): `feature/<ticket-id>` and
`fix/<ticket-id>` branches are cut from `develop` and squash-merged back into
it. After every ticket, `develop` is promoted to `main`: `main` is merged into
`develop` with a merge commit (resolving any conflicts there), then a release
PR from `develop` is merged into `main` with a merge commit. The next ticket
starts only once `main` has the previous one. If a release can't finish, the
factory only accepts a `type:fix` ticket until that fix is released (see
`.claude/rules/git.md`). Commits follow
Conventional Commits with the ticket id as scope, e.g. `feat(<ticket-id>): ...`
(see `.conventionalcommit.json`).
