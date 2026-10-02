# Learning Companion

A learning companion for tracking goals and learning sessions, attaching resources, and getting AI-powered summaries and next steps. Built with Django through an AI-factory pipeline (Recap Project 6, handouts in `instructions/`).

## Stack

- Python 3.14, Django 6.1, SQLite (dev, tests and container)
- Server-rendered Django templates, Tailwind via `django-tailwind-cli` (standalone binary, no Node). The Tailwind version is pinned in `settings.py` (`TAILWIND_CLI_VERSION`), and the built CSS is git-ignored, so run `tailwind build` after checkout. Tests don't need the build.
- Auth: Django's built-in auth with the custom user model `accounts.User` (`AUTH_USER_MODEL = "accounts.User"`, an `AbstractUser` with no extra fields). Always refer to it through `get_user_model()` or `settings.AUTH_USER_MODEL`, never `django.contrib.auth.models.User`. Profile data goes on `profiles.Profile`, not on `User`. Every user saved through `save()` gets exactly one profile (`user.profile`: `name`, `cohort`, `focus_areas`). A `post_save` signal in `profiles/signals.py` creates it, and the data migration `profiles/0002` backfilled users who already existed. `bulk_create` and raw fixture loads skip the signal, so views must use `Profile.objects.get_or_create(user=request.user)`, not a bare `user.profile`. The User admin (`accounts/admin.py`) shows it as an inline on the change page only, never on the add page. Users view and edit their own profile at login-required pages: `/profile/` (`profiles:mine`) redirects to `/profile/<pk>/` (`profiles:detail`), and `/profile/<pk>/edit/` (`profiles:edit`) takes focus areas as comma-separated text. Any view that takes a pk must scope its queryset to `request.user`, as `profiles.views.OwnProfileMixin` does for profiles, so another user's pk is a 404, exactly like a missing one. A profile takes at most 20 focus areas (1,000 characters of input), checked before any tag lookup. Sign-up (`/accounts/signup/`), log-in (`/accounts/login/`) and log-out (`/accounts/logout/`, POST only) are `accounts` views, the last two thin subclasses of Django's `LoginView` and `LogoutView`. `LOGIN_URL = "accounts:login"`, `LOGIN_REDIRECT_URL = "/"` and `LOGOUT_REDIRECT_URL = "/"`. A `next` parameter is followed only for same-site URLs (Django's `url_has_allowed_host_and_scheme`); keep it that way for any new redirect.
- Tags: one shared `tags.Tag` vocabulary, used for a profile's `focus_areas` and later for session tags. Names are normalised (NFKC, trimmed, inner whitespace collapsed), must not contain control or invisible characters (Unicode Cc/Cf) or commas (the separator for typed focus areas), and are unique regardless of case, through a database constraint on `Lower("name")`; on SQLite the case folding is ASCII-only. `Tag.objects.clean_name()` validates a name without touching the database (forms use it to reject bad entries before anything is saved). `save()` normalises the name; the 50-character limit and the character checks apply only through `full_clean()`/`clean_name()`; `update()` and `bulk_create()` bypass all of it. Rows written before the normalisation existed (or through those bypasses) aren't renormalised: there is no data migration, as there is no production data yet. So always turn typed input into tags with `Tag.objects.get_or_create_by_name()`, never `Tag.objects.create()`. It is the only creation path for typed names: it validates before its lookup (an over-long name is a `ValidationError`, never a database error), and it is safe when two requests create the same name at once.
- Goals: `goals.Goal` is owned by one user (`owner`, `user.goals`, deleted with the user). Its fields are `title` (required, up to 200 characters, stored trimmed), optional `description`, `status` and `created_at`/`updated_at`. `Goal.Status` is a `TextChoices` with `planned`, `in-progress` and `done` (the hyphen matches the planned `?status=` filter); a database `CheckConstraint` enforces them, so `update()`/`bulk_create()` can't store anything else. Goals are ordered newest first (`-created_at`, then `-id`). Goal views should scope every lookup through a `Goal.objects.owned_by(user)` helper, which #8 introduces, so another user's goal is a 404.
- Django's built-in test runner (`django.test`), ruff for lint and formatting. Ruff's defaults include RUF012, so class-level options (`Meta.ordering`, `Meta.constraints`, admin `inlines`) are tuples. A test of a data migration must be a `TransactionTestCase` (see `profiles/tests/test_migrations.py`).
- Settings from the environment via `django-environ` (`src/config/env.py`). `SECRET_KEY` is required, `DEBUG` defaults to `False` and `ALLOWED_HOSTS` to `localhost,127.0.0.1`. The process environment beats `.env`, and `.env.example` documents every variable.
- OpenAI Chat Completions for the AI features; API key from `.env`, never hardcoded

Decisions above that aren't implemented yet are delivered by the tickets on the board; keep this file in step as they land.

## Commands

Run from the repo root.

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt   # setup
cp .env.example .env   # then set SECRET_KEY; required by runserver and the test suite
./.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"   # generate a SECRET_KEY
./.venv/bin/python src/manage.py tailwind build                              # build the CSS (required after checkout; downloads the pinned binary into src/.django_tailwind_cli/)
./.venv/bin/python src/manage.py tailwind runserver                          # dev server plus Tailwind watcher (everyday development)
./.venv/bin/python src/manage.py runserver                                   # dev server only
./.venv/bin/python src/manage.py test src                                    # full suite (what the hooks run)
./.venv/bin/python src/manage.py test <app>.tests.test_<x> --verbosity 2     # one test module
./.venv/bin/ruff check .                                                     # lint (what the hooks run)
./.venv/bin/ruff format .                                                    # format
./.venv/bin/python src/manage.py makemigrations && ./.venv/bin/python src/manage.py migrate
python3 .claude/scripts/board.py sync                                        # mirror the GitHub board into work/backlog.md
```

## Layout

- `src/manage.py`, `src/config/`: Django project (settings, root URLs, ASGI/WSGI)
- `src/<app>/`: one Django app per domain area, tests in `src/<app>/tests/` (`test_*.py`)
- `src/core/`: the home page and other site-wide views. `src/core/tests/html.py` holds `PageParser`, the HTML helper shared by the apps' page tests.
- `src/accounts/`: the custom user model, and sign-up, log-in and log-out under `/accounts/` (URL namespace `accounts`)
- `src/tags/`: the shared `Tag` model, plus its admin with a name search, which backs tag autocomplete
- `src/profiles/`: `Profile` (one per user), the signal that creates it, the backfill migration, the admin inline, and the profile pages under `/profile/` (views, URLs, `ProfileForm`)
- `src/goals/`: the `Goal` model (status choices, ownership, admin); the goal pages come with the later goal tickets
- `src/templates/`: project-wide templates (`base.html` layout, pages that extend it, `accounts/` and `profiles/` pages)
- `src/assets/`: static source directory (`STATICFILES_DIRS`); the built `css/tailwind.css` is git-ignored
- `work/<ticket-id>/`: workflow artifacts per ticket (`ticket.md`, `plan.md`, `review.md`, `activity.log`)
- `work/backlog.md`: git-ignored local mirror of the GitHub project board
- `.claude/`: workflow rules, skills, hooks, the board sync script
- `instructions/`: the project handouts (requirements per feature)

## Workflow

Every change goes through the pipeline in `.claude/rules/workflow.md`: `refine-ticket` → `plan-ticket` → `tdd-implement` → `final-review` → `release`, driven one step per call by `factory-manager` (e.g. `/loop /factory-manager`). TDD rules: `.claude/rules/tdd.md`. Gitflow and commit conventions: `.claude/rules/git.md`.

- Tickets are GitHub issues on the project board (repo and board number in `.claude/hooks/config.sh`).
- Ticket branches `feature/<id>` / `fix/<id>` are cut from `develop` and squash-merged back into it; the branches are kept.
- After every ticket, `factory-manager` runs the `release` skill: `main` is merged into `develop` with a merge commit (conflicts are resolved there), then a PR from `develop` is merged into `main` with a merge commit. `main` only changes this way.
- The next ticket starts only once `main` has the previous one; a hook blocks new ticket branches while `develop` is ahead of `main`.
- A release that can't finish (red suite, failed checks, a conflict, unreviewed commits on `develop`) sets `release_status: blocked` in `.claude/state/workflow.json` and returns to `idle`; then only a `type:fix` ticket can start, and its release clears the flag. A human can also fix an outside cause and run `/release`.
- `REQUIRE_CHECKS` in `.claude/hooks/config.sh` is `"false"` until CI exists: release PRs without checks merge on the local suite + lint, which the hook re-runs before `gh pr merge`. Flip it to `"true"` with the `ci-tests` ticket.
- A paused ticket (approval recorded in its `ticket.md`) resumes on its existing branch: `refine-ticket` merges the latest `develop` into it and continues at `plan-ticket`.
- Source under `src/` is write-protected outside the `implementing` phase; hooks also gate commits, pushes and merges.
