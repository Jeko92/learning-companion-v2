# Learning Companion

Django 6.1 project on Python 3.14.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/python src/manage.py migrate
./.venv/bin/python src/manage.py runserver
```

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
it, `main` only receives release PRs from `develop`. Commits follow
Conventional Commits with the ticket id as scope, e.g. `feat(<ticket-id>): ...`
(see `.conventionalcommit.json`).
