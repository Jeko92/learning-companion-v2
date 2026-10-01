# Learning Companion

A learning companion for tracking goals and learning sessions, attaching resources, and getting AI-powered summaries and next steps. Built with Django through an AI-factory pipeline (Recap Project 6, handouts in `instructions/`).

## Stack

- Python 3.14, Django 6.1, SQLite (dev, tests and container)
- Server-rendered Django templates, Tailwind via `django-tailwind-cli` (standalone binary, no Node)
- Django's built-in test runner (`django.test`), ruff for lint and formatting
- OpenAI Chat Completions for the AI features; API key from `.env`, never hardcoded

Decisions above that aren't implemented yet are delivered by the tickets on the board; keep this file in step as they land.

## Commands

Run from the repo root.

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt   # setup
./.venv/bin/python src/manage.py runserver                                   # dev server
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
- `work/<ticket-id>/`: workflow artifacts per ticket (`ticket.md`, `plan.md`, `review.md`, `activity.log`)
- `work/backlog.md`: git-ignored local mirror of the GitHub project board
- `.claude/`: workflow rules, skills, hooks, the board sync script
- `instructions/`: the project handouts (requirements per feature)

## Workflow

Every change goes through the pipeline in `.claude/rules/workflow.md`: `refine-ticket` → `plan-ticket` → `tdd-implement` → `final-review`, driven one step per call by `factory-manager` (e.g. `/loop /factory-manager`). TDD rules: `.claude/rules/tdd.md`. Gitflow and commit conventions: `.claude/rules/git.md`.

- Tickets are GitHub issues on the project board (repo and board number in `.claude/hooks/config.sh`).
- Ticket branches `feature/<id>` / `fix/<id>` are cut from `develop` and squash-merged back into it; the branches are kept.
- `main` only changes through the `release` skill (PR from `develop`, merge commit).
- Source under `src/` is write-protected outside the `implementing` phase; hooks also gate commits, pushes and merges.
