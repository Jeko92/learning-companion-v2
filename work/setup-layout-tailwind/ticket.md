# Setup: base layout with Tailwind and a home page
Issue: #2 · Branch: feature/setup-layout-tailwind

## Story
As a learner using the Learning Companion, I want a consistent, styled page layout and a home page at `/`, so that every feature built later has a shared frame and the app has a landing page.

## Acceptance criteria
- [x] AC1 `GET /` returns 200 and renders `home.html`, which extends `base.html`. Both show up in `assertTemplateUsed`.
- [x] AC2 `base.html` and `home.html` are loaded from the project-level `src/templates/` directory, not from an app's `templates/` folder.
- [x] AC3 The layout's header shows the app name "Learning Companion", and the page `<title>` contains "Learning Companion".
- [x] AC4 The layout's nav shows "Goals" and "Log in" as placeholders that aren't links: neither is inside an element with an `href`.
- [x] AC5 The layout renders Django messages. A message added for the request appears on the rendered page.
- [x] AC6 The layout has a content block that the home page fills, and the home page shows the one-line pitch "Track your learning goals and sessions, and get AI-powered summaries and next steps."
- [x] AC7 The layout has a `<footer>`.
- [x] AC8 The layout links the Tailwind stylesheet. The rendered page contains the `<link rel="stylesheet">` that `django-tailwind-cli` produces for its CSS file, and the test passes without the CSS having been built.
- [x] AC9 `django_tailwind_cli` and a new `core` app are in `INSTALLED_APPS`, and the home view lives in `core`, routed through `core/urls.py` included at `/`.

## Out of scope
- Real auth links and auth-aware nav (tickets `auth-signup`, `auth-login-logout`).
- Visual polish beyond a simple, readable Tailwind layout. No dark mode, no responsive menu.
- Building the CSS in Docker or CI (tickets `docker`, `ci-tests`). They must run the Tailwind build step.

## Notes
Answers from refinement (2026-10-01; first given earlier the same day while #1 was being redone, then confirmed):
- Project-wide templates live in `src/templates/` (added to `TEMPLATES['DIRS']`), not in the `core` app.
- The built Tailwind CSS is **not committed**. Its output path must be git-ignored, and everyone who checks out the repo runs the build step before running the project.
- The home page shows the app name, a one-line pitch, and nav placeholders (Goals, Log in) that don't link anywhere yet.
- The home view goes in a new `core` app (the issue's scope). Only the templates are project-level.
- Tests check that the layout links the stylesheet, not that a built CSS file exists, so the suite needs no Tailwind binary.
- Documented dev workflow: `./.venv/bin/python src/manage.py tailwind build` as the required build step after checkout, and `./.venv/bin/python src/manage.py tailwind runserver` (watcher plus dev server) for everyday development.
- Required deliverables that tests can't verify:
  - add `django-tailwind-cli` to `requirements.txt`
  - git-ignore the built CSS output
  - update `README.md` and `CLAUDE.md` (setup, the build step, the dev command, and the `core` app and `src/templates/` in the Layout section)
- Constraint: the suite needs `SECRET_KEY` (from ticket #1). Tests run with the local `.env`.

Status: the user approved these acceptance criteria on 2026-10-01. The ticket was then paused (card back to Todo, phase reset to idle) so a workflow ticket, "release develop to main after every ticket", could run first. When #2 resumes, bring this branch up to date with `develop` and continue at `plan-ticket`. Don't refine again.
