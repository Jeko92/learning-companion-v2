# Learning Companion

[![CI](https://github.com/Jeko92/learning-companion-v2/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Jeko92/learning-companion-v2/actions/workflows/ci.yml)

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

The components come from [daisyUI](https://daisyui.com/) 5, used through its standalone setup: `src/tailwind/source.css` (the build's input, `TAILWIND_CLI_SRC_CSS`) loads `daisyui.mjs` and `daisyui-theme.mjs`, which are committed next to it. The stylesheet's header records the daisyUI version and each file's sha256, and a test checks them. To update daisyUI, download both files from `https://github.com/saadeghi/daisyui/releases/download/v<version>/`, then update the version and the two hashes (`shasum -a 256 src/tailwind/*.mjs`). The same stylesheet defines the app's two themes: `companion` (light, the default) and `companion-dark`, which the browser picks when the system is in dark mode. The System / Light / Dark switch in the header overrides that for the current page with CSS alone (daisyUI's `theme-controller`, no JavaScript); it isn't remembered, so each page load starts at System. Their colours stay inside sRGB and every text colour has at least 4.5:1 contrast on its background, checked by `src/core/tests/test_theme.py`. Every class name must appear literally in a template or a `.py` file, because the build only finds classes it can read there.

The favicon is `src/assets/favicon.svg` (an open book on the theme's indigo), with `favicon.ico` (16, 32 and 48 px) and `apple-touch-icon.png` (180 px, square corners) generated from it on macOS and committed. `/favicon.ico` serves the ICO to anyone. To regenerate them after changing the SVG:

```bash
cd src/assets
sed 's/ rx="7"//' favicon.svg > /tmp/touch.svg   # full-bleed square for iOS
sips -s format png -z 180 180 /tmp/touch.svg --out apple-touch-icon.png
for s in 16 32 48; do sips -s format png -z $s $s favicon.svg --out /tmp/icon-$s.png; done
python3 -c 'import struct; S=[16,32,48]; P=[open(f"/tmp/icon-{s}.png","rb").read() for s in S]; h=struct.pack("<HHH",0,1,3); o=6+16*3
for s,p in zip(S,P): h+=struct.pack("<BBBBHHII",s,s,0,0,1,32,len(p),o); o+=len(p)
open("favicon.ico","wb").write(h+b"".join(P))'
```

Users sign up at `/accounts/signup/`, log in at `/accounts/login/` and log out with the nav's Log out button (a POST to `/accounts/logout/`). Signing up or logging in lands on the dashboard at `/dashboard/` (the Dashboard link in the nav), unless a same-site `next` page was asked for. It shows how many of your goals are planned, in progress and done, each count linking to the goal list filtered by that status. Below that, it totals your logged session time per tag (with time from untagged sessions as "Untagged"; a session with several tags counts under each) and per week for the last 8 weeks (weeks start on Monday; empty weeks show 0 min). Logging out lands on the public home page `/`. The project uses a custom user model, `accounts.User`. If your `src/db.sqlite3` was created before that change (before the `auth-signup` ticket), `migrate` fails with `InconsistentMigrationHistory`. Delete `src/db.sqlite3` once and run `migrate` again.

Every user gets a profile (name, cohort, focus areas), created automatically when the user is created through sign-up, `createsuperuser` or the admin. Users loaded from fixtures don't get one automatically. Running `migrate` gives users who existed before that a profile too. Logged-in users see their profile at `/profile/` (the username in the nav links there) and edit it at `/profile/<id>/edit/`, entering focus areas as comma-separated text. Nobody can open another user's profile. Admins can also edit profiles on each user's page in the admin. Logged-in users see their own goals at `/goals/` (the Goals link in the nav), newest first and 20 per page (filter by status with the All / Planned / In progress / Done links), add goals at `/goals/new/`, and open, edit or delete a goal from its page at `/goals/<id>/`. Nobody can open another user's goal. A goal's page shows its 5 most recent learning sessions and the total time spent; sessions are added at `/goals/<id>/sessions/new/` (date, duration in minutes, notes, comma-separated tags), listed at `/goals/<id>/sessions/`, and edited or deleted at `/sessions/<id>/edit/` and `/sessions/<id>/delete/`. Nobody can open another user's sessions. Deleting a goal deletes its sessions too, and the confirmation page says how many. The goal page's Summary section has a Generate summary button: it sends the goal, its 10 most recent sessions, its total time and its 20 newest resources to OpenAI, and keeps the reply on the goal page with the time it was generated until you regenerate it. A goal with no sessions and no resources isn't sent, and if the AI service fails you see its message and the previous summary stays. Below it, the Next steps section has a Suggest next steps button: it sends the same data and shows 2-3 concrete next learning actions as a numbered list, kept with the time they were suggested until you ask again. A brand-new goal with nothing logged still gets steps on how to start, and if the AI fails or its reply isn't a list of 2-3 steps you see a message and the previous steps stay. Both need a real `OPENAI_API_KEY` in `.env`.

Settings come from the environment via `django-environ`, read in `src/config/env.py`:

| Variable | Default when unset | Notes |
|---|---|---|
| `SECRET_KEY` | none, so startup fails | Required and must not be empty |
| `DEBUG` | `False` | `.env.example` sets `True` for local development |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated. If it's set but empty, every host is rejected when `DEBUG` is off |
| `OPENAI_API_KEY` | none, so startup fails | Required and must not be empty. `sk-dummy` (the `.env.example` value) is enough to run the tests and the dev server; the AI features need a real key |
| `OPENAI_MODEL` | `gpt-4.1-mini` | The Chat Completions model for the AI features; empty also means the default |
| `DATABASE_URL` | `src/db.sqlite3` | The database as a URL, e.g. `sqlite:////app/data/db.sqlite3` (four slashes for an absolute path); empty also means the default. A value that isn't a valid database URL stops startup with an error that names the variable |
| `CSRF_TRUSTED_ORIGINS` | empty | Comma-separated origins with their scheme (`https://companion.example`), needed when the site is reached through another origin such as an HTTPS proxy. Each must start with `http://` or `https://` |

Values are read from the process environment first. `.env` at the repo root only fills in variables that aren't already set. `.env` is git-ignored, and `.env.example` documents every variable. Write one `NAME=value` per line with no spaces around `=`. `DEBUG=True` is for local development only. The test suite needs `SECRET_KEY` and `OPENAI_API_KEY` too, so set up `.env` before running the tests. The tests never call the OpenAI API.

## Run with Docker

The `Dockerfile` builds a production image: gunicorn, `DEBUG` off, static files (including the Tailwind CSS) served by WhiteNoise, and the SQLite database on a volume. The build downloads the Linux Tailwind binary from GitHub, so it needs network access. The image's healthcheck uses `--start-interval`, which needs Docker Engine 25 or newer.

```bash
docker build -t learning-companion .
docker run --env-file .env -e DEBUG=False -p 127.0.0.1:8000:8000 -v learning-companion-data:/app/data learning-companion
# or pass the two required keys directly:
docker run -e SECRET_KEY=... -e OPENAI_API_KEY=... -p 127.0.0.1:8000:8000 -v learning-companion-data:/app/data learning-companion
```

Then open http://localhost:8000/.

- **Start-up:** on every start the container applies migrations to `/app/data/db.sqlite3` (the image sets `DATABASE_URL` to it), then starts gunicorn on port 8000. Without `SECRET_KEY` or `OPENAI_API_KEY` it exits with an error that names the missing variable.
- **Data:** it survives new containers as long as they use the same volume.
- **Health:** `docker ps` shows the container as healthy once it answers.
- **`.env` from `.env.example`:** it works with `--env-file`. `DATABASE_URL` is commented out there on purpose, because a blank `DATABASE_URL=` would override the image's own value. The example's `DEBUG=True` would reach the container too, which is why the command adds `-e DEBUG=False`: `-e` beats `--env-file`.
- **Ports:** `-p 127.0.0.1:8000:8000` publishes the port on this machine only. Use `-p 8000:8000` to reach it from other devices.

A few options:

- `-e WEB_CONCURRENCY=3` runs more gunicorn workers (default 1).
- If the site is reached through another host name or an HTTPS proxy, set `-e ALLOWED_HOSTS=companion.example,127.0.0.1` and `-e CSRF_TRUSTED_ORIGINS=https://companion.example`. Keep `127.0.0.1` in `ALLOWED_HOSTS`: the healthcheck requests `http://127.0.0.1:8000/favicon.ico` inside the container, and without it the container stays unhealthy.

`scripts/docker-smoke.sh` builds the image, runs it with dummy keys and checks it end to end:

- the home page, the gzipped stylesheet and the favicon are served;
- sign-up works through the real form;
- an account survives a new container on the same volume, also when that container is started with `--env-file` and a `.env` made from `.env.example`;
- `-e DEBUG=False` beats the example's `DEBUG=True`;
- the app doesn't run as root;
- the image holds no `.env` and no Tailwind binary.

It removes everything it created and needs Docker; the test suite doesn't.

## Tests and lint

```bash
./.venv/bin/python src/manage.py test src
./.venv/bin/ruff check .
./.venv/bin/ruff format .
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull
request, with a read-only token; a newer run of the same branch cancels the
older one. Two jobs run in parallel, and their ids are the status checks:

- `quality` (Python 3.14, pip cache): `ruff check .`, `ruff format --check .`,
  `manage.py check`, `manage.py makemigrations --check --dry-run` and
  `manage.py test src`, each its own step. The two required keys are dummies
  in the workflow (the tests never call the API); no secret is used.
- `docker-smoke`: `scripts/docker-smoke.sh`, which builds the image, runs it
  and checks it end to end.

Branch protection requires both checks on `main` and on `develop`
(`scripts/branch-protection.sh show` prints it, `apply` sets it; needs repo
admin). On `develop`, admins may bypass them, so a release can push its
`main`-into-`develop` merge commit directly. Release PRs into `main` merge
only once both checks have passed.

The same gate locally:

```bash
./.venv/bin/ruff check . && ./.venv/bin/ruff format --check .
./.venv/bin/python src/manage.py check
./.venv/bin/python src/manage.py makemigrations --check --dry-run
./.venv/bin/python src/manage.py test src
scripts/docker-smoke.sh   # needs Docker
```

Follow a run with `gh run list` or `gh pr checks <pr>`.

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
- `src/dashboard/`: the dashboard at `/dashboard/`, where log-in lands: the user's goal count per status, with a total, and session time per tag and per week
- `src/ai/`: the OpenAI Chat Completions service the AI features use (key and model from the environment, 30 seconds per network phase, 2 retries by default and none for the page actions, one user-safe error for any failure, plain-text or JSON-schema replies)
- `src/templates/`: project-wide templates (`base.html` layout, pages that extend it, `accounts/`, `profiles/`, `goals/`, `learning_sessions/`, `resources/` and `dashboard/` pages), `forms/` (how every form outside the admin renders) and `components/` (shared pieces: icons, page header, status badge, tag pills, empty state, pagination, delete confirmation)
- `src/tailwind/`: the Tailwind source stylesheet with the app's themes, and the vendored daisyUI plugin files
- `src/assets/`: static source files (the favicons); the built `css/tailwind.css` is git-ignored
- `work/`: workflow artifacts per ticket (`ticket.md`, `plan.md`, `review.md`)
- `Dockerfile`, `.dockerignore`, `docker/entrypoint.sh`: the production image and its start-up (migrate, then gunicorn)
- `scripts/docker-smoke.sh`: builds and runs the image and checks it serves the app
- `scripts/branch-protection.sh`: the branch protection of `main` and `develop` (`show`, `apply`)
- `.github/workflows/ci.yml`: the CI workflow (jobs `quality` and `docker-smoke`)
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
