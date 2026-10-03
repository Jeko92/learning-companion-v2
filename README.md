# Learning Companion

Django 6.1 project on Python 3.14.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
./.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# paste the printed key into .env as SECRET_KEY=...
# for the AI features, replace OPENAI_API_KEY=sk-dummy in .env with your OpenAI key
./.venv/bin/python src/manage.py migrate
./.venv/bin/python src/manage.py tailwind build
./.venv/bin/python src/manage.py runserver
```

Styling uses Tailwind through `django-tailwind-cli`, a standalone binary with no Node. `tailwind build` downloads the Tailwind version pinned in `settings.py` (`TAILWIND_CLI_VERSION`) into `src/.django_tailwind_cli/` and builds `src/assets/css/tailwind.css`. Both are git-ignored, so run the build after cloning, and again whenever templates change unless `tailwind runserver` is running. For everyday development, `./.venv/bin/python src/manage.py tailwind runserver` runs the dev server and rebuilds the CSS as templates change.

Users sign up at `/accounts/signup/`, log in at `/accounts/login/` and log out with the nav's Log out button (a POST to `/accounts/logout/`). The project uses a custom user model, `accounts.User`. If your `src/db.sqlite3` was created before that change (before the `auth-signup` ticket), `migrate` fails with `InconsistentMigrationHistory`. Delete `src/db.sqlite3` once and run `migrate` again.

Every user gets a profile (name, cohort, focus areas), created automatically when the user is created through sign-up, `createsuperuser` or the admin. Users loaded from fixtures don't get one automatically. Running `migrate` gives users who existed before that a profile too. Logged-in users see their profile at `/profile/` (the username in the nav links there) and edit it at `/profile/<id>/edit/`, entering focus areas as comma-separated text. Nobody can open another user's profile. Admins can also edit profiles on each user's page in the admin. Logged-in users see their own goals at `/goals/` (the Goals link in the nav), newest first and 20 per page (filter by status with the All / Planned / In progress / Done links), add goals at `/goals/new/`, and open, edit or delete a goal from its page at `/goals/<id>/`. Nobody can open another user's goal. A goal's page shows its 5 most recent learning sessions and the total time spent; sessions are added at `/goals/<id>/sessions/new/` (date, duration in minutes, notes, comma-separated tags), listed at `/goals/<id>/sessions/`, and edited or deleted at `/sessions/<id>/edit/` and `/sessions/<id>/delete/`. Nobody can open another user's sessions. Deleting a goal deletes its sessions too, and the confirmation page says how many.

Settings come from the environment via `django-environ`, read in `src/config/env.py`:

| Variable | Default when unset | Notes |
|---|---|---|
| `SECRET_KEY` | none, so startup fails | Required and must not be empty |
| `DEBUG` | `False` | `.env.example` sets `True` for local development |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated. If it's set but empty, every host is rejected when `DEBUG` is off |
| `OPENAI_API_KEY` | none, so startup fails | Required and must not be empty. `sk-dummy` (the `.env.example` value) is enough to run the tests and the dev server; the AI features need a real key |
| `OPENAI_MODEL` | `gpt-4.1-mini` | The Chat Completions model for the AI features; empty also means the default |

Values are read from the process environment first. `.env` at the repo root only fills in variables that aren't already set. `.env` is git-ignored, and `.env.example` documents every variable. Write one `NAME=value` per line with no spaces around `=`. `DEBUG=True` is for local development only. The test suite needs `SECRET_KEY` and `OPENAI_API_KEY` too, so set up `.env` before running the tests. The tests never call the OpenAI API.

## Tests and lint

```bash
./.venv/bin/python src/manage.py test src
./.venv/bin/ruff check .
./.venv/bin/ruff format .
```

## Layout

- `src/manage.py`, `src/config/`: Django project (settings, URLs, ASGI/WSGI)
- `src/<app>/`: Django apps, each with its own tests
- `src/core/`: the home page and other site-wide views
- `src/accounts/`: the custom user model (`accounts.User`), and sign-up, log-in and log-out under `/accounts/`
- `src/tags/`: shared tags (case-insensitive unique names), used for focus areas and session tags, plus the comma-separated tag field both forms use
- `src/profiles/`: each user's profile (name, cohort, focus areas), created automatically for new users, and the profile pages under `/profile/`
- `src/goals/`: learning goals (title, description, status planned / in-progress / done), each owned by one user; listed at `/goals/`, created at `/goals/new/`, and viewed, edited or deleted at `/goals/<id>/`
- `src/learning_sessions/`: learning sessions, each logged against one goal: a date (today or earlier), a duration in minutes (1 to 1,440), notes and tags; listed and created under `/goals/<id>/sessions/`, edited or deleted at `/sessions/<id>/`
- `src/resources/`: reference material for a goal (an article, video, repo or doc): an http(s) URL, a title and a type, each URL at most once per goal
- `src/ai/`: the OpenAI Chat Completions service the AI features use (key and model from the environment, a 30-second timeout and 2 retries, one user-safe error for any failure)
- `src/templates/`: project-wide templates (`base.html` layout, pages that extend it, `accounts/`, `profiles/`, `goals/` and `learning_sessions/` pages)
- `src/assets/`: static source files; the built `css/tailwind.css` is git-ignored
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
