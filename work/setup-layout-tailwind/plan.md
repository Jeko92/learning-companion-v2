# Plan: setup-layout-tailwind

## Research summary
- **Project:** `config` is the only package under `src/`. `BASE_DIR = Path(__file__).resolve().parent.parent` is `src/`, which is the import root (ruff `src = ["src"]`), so the new app is `core`, not `src.core`.
  - `INSTALLED_APPS` holds only the 6 contrib apps.
  - `TEMPLATES` has `"DIRS": []` and `"APP_DIRS": True`, plus the `request`, `auth` and `messages` context processors.
  - `MessageMiddleware`, `SessionMiddleware` and `AuthenticationMiddleware` are already in `MIDDLEWARE`.
  - Static: only `STATIC_URL = "static/"`, with no `STATICFILES_DIRS`, no `STATIC_ROOT`, and the default `StaticFilesStorage`.
  - `config/urls.py` has only `admin/` and no `include` import.
- **Tests:** `src/config/tests/` (with `__init__.py`) holds `test_env.py`, `test_env_example.py` and `test_settings.py`.
  - Every class is a `SimpleTestCase`, with arrange/act/assert separated by blank lines.
  - Tests are named as behaviour sentences, helpers are methods on the class, and booleans are checked with `assertIs`.
  - Discovery needs an `__init__.py` in every `tests/` dir. Labels are relative to `src/`, e.g. `./.venv/bin/python src/manage.py test core.tests.test_home --verbosity 2`.
  - The runner forces `DEBUG=False`. The suite needs `SECRET_KEY` from the local `.env`, which exists.
- **Ruff:** defaults (88 columns, E4/E7/E9/F), `target-version = "py314"`, migrations excluded.
- **Requirements:** pinned to a minor version, `Django>=6.1,<6.2` and `django-environ>=0.14,<0.15`. `django-tailwind-cli` is not installed yet.
- **django-tailwind-cli 4.8.1** (latest, 2026-09-18):
  - **Compatibility:** declares Django 6.1 and Python 3.14 support. Its dependencies are `click`, `django-click` and `semver`.
  - **App:** `INSTALLED_APPS += ["django_tailwind_cli"]`.
  - **`STATICFILES_DIRS` must be non-empty.** Otherwise both the build and the template tag raise `ConfigurationError` (a `ValueError` subclass).
  - **Built CSS:** `TAILWIND_CLI_DIST_CSS` defaults to `css/tailwind.css` relative to `STATICFILES_DIRS[0]`.
  - **Tailwind version:** `TAILWIND_CLI_VERSION` defaults to `"latest"`, which means a GitHub lookup on every build. The latest Tailwind release is v4.3.3.
  - **Source CSS and binary:** with `TAILWIND_CLI_SRC_CSS` unset, the package manages `BASE_DIR/.django_tailwind_cli/source.css` (`@import "tailwindcss";`). The binary is downloaded into the same directory, and that directory ignores itself through its own `.gitignore`.
  - **Template tag:** `{% load tailwind_cli %}{% tailwind_css %}` renders `<link rel="stylesheet" href="/static/css/tailwind.css">`. With `DEBUG=False` a `rel="preload"` link comes before it.
    - Since 4.8.1 the tag needs no binary and no built file. It only resolves settings, and `{% static %}` with the default storage just joins `STATIC_URL`.
  - **Commands:** `tailwind build` always rebuilds and minifies. `tailwind runserver` runs `tailwind watch` and `runserver` together.
    - Both run the CLI with `cwd=BASE_DIR`, and Tailwind v4's automatic detection scans everything under `src/` except git-ignored paths.
- **Docs:**
  - `CLAUDE.md` has one bash block of commands (with `runserver` among them) and a Layout list.
  - `README.md` has `## Setup` (venv, pip, `.env`, key, migrate, runserver), `## Tests and lint` and `## Layout`.
  - Neither file mentions templates or the Tailwind commands yet. `CLAUDE.md`'s Stack line already names `django-tailwind-cli`.

## Design decisions
- **`core` app, project-level templates:**
  - `src/core/` holds `apps.py` (`CoreConfig`, `name = "core"`), `views.py` (function view `home`) and `urls.py` (`path("", views.home, name="home")`).
  - `config/urls.py` includes `core.urls` at `""`.
  - `TEMPLATES["DIRS"] = [BASE_DIR / "templates"]`, so the templates are `src/templates/base.html` and `src/templates/home.html`.
  - The `core` app has no models, so it gets no `migrations/` package.
- **Tailwind wiring:**
  - `STATICFILES_DIRS = [BASE_DIR / "assets"]`, the convention from the docs.
  - The built CSS is `src/assets/css/tailwind.css` and is git-ignored.
  - `src/assets/.gitkeep` keeps the directory present on a fresh checkout. Otherwise the staticfiles check `W004` would warn about a missing directory.
  - The source CSS stays the package-managed default. The project needs no custom CSS yet, and the default keeps the source CSS out of `STATICFILES_DIRS`, which avoids the package's `W001` warning.
- **`TAILWIND_CLI_VERSION = "4.3.3"`:** the build is reproducible and doesn't look up GitHub on every run. Raising the version is a deliberate one-line change.
- **Dependency:** `django-tailwind-cli>=4.8,<4.9` in `requirements.txt`, matching the minor-version pinning style. 4.8 is the first line with the binary-free template tag and with the Django 6.x support that came from dropping django-typer.
- **View tests use `django.test.TestCase`, not `SimpleTestCase`.** The request goes through the session, auth and messages middleware and context processors. A `TestCase` keeps any incidental session or DB access from erroring, and SQLite keeps it cheap. Settings-level checks (`apps.is_installed`) stay `SimpleTestCase`.
- **HTML structure checks with a stdlib `html.parser.HTMLParser` subclass** in the test module. It collects the text inside `<title>`, `<header>`, `<nav>`, `<main>` and `<footer>`, and the text that sits inside any element with an `href`. This makes AC3, AC4 and AC7 checks about structure, not just substrings, without adding a dependency.
- **Messages test (AC5):** build the request with `RequestFactory`. Run `SessionMiddleware` on it, attach `default_storage(request)` as `request._messages`, add `messages.info(request, "Profile saved.")`, call `core.views.home` directly and `assertContains` the message. This avoids a fake view or URL that exists only to add a message.
- **Styling:** simple, readable Tailwind utility classes in `base.html` and `home.html`: a header bar, a nav, a centred content column and a muted footer. Tests don't check classes, so styling is not a step of its own.

## Steps
Approved by the user on 2026-10-02, including step 4 as a guard test that passes on arrival.

Test files: `src/core/tests/test_apps.py` (`SimpleTestCase`) for installed apps, and `src/core/tests/test_home.py` (`TestCase`) for the view and layout. Each step is one red–green–refactor cycle and one commit, `feat(setup-layout-tailwind): <what the step delivers>`.

- [x] 1. The `core` app is installed: `apps.is_installed("core")` is `True`. Test: `src/core/tests/test_apps.py` (plus `src/core/tests/__init__.py`), expected to be red with `False is not True`. Impl: `src/core/__init__.py`, `src/core/apps.py`, `INSTALLED_APPS` in `src/config/settings.py`. Covers: AC9.
- [x] 2. `GET /` returns 200 and is served by `core.views.home` through `core.urls`: `resolve("/").func` is `core.views.home`, `resolve("/").url_name == "home"`, and `resolve("/", urlconf="core.urls").func` is `core.views.home`. Test: `src/core/tests/test_home.py`, red on the 404 status assertion. Impl: `src/core/views.py` (minimal response), `src/core/urls.py`, `include("core.urls")` in `src/config/urls.py`. Covers: AC9, AC1 (status).
- [x] 3. `GET /` renders `home.html`, which extends `base.html`: `assertTemplateUsed` for both. Test: `test_home.py`. Impl: `src/templates/base.html` (with a `content` block), `src/templates/home.html` (`{% extends "base.html" %}`), `TEMPLATES["DIRS"] = [BASE_DIR / "templates"]`, and `home` switched to `render(request, "home.html")`. Covers: AC1.
- [x] 4. Both templates are loaded from the project-level `src/templates/`: for `base.html` and `home.html` in `response.templates`, `Path(t.origin.name)` equals `settings.BASE_DIR / "templates" / <name>`. Test: `test_home.py`. Impl: none. Covers: AC2.
  - A guard test that passes on arrival, because step 3 already puts the templates there. It pins AC2 against templates moving into `core/templates/`. Confirm the guard works by temporarily moving `home.html` into `src/core/templates/` (`APP_DIRS` would then find it there): the test must go red. Then move it back.
  - Done 2026-10-02: green on arrival; with `home.html` moved into `src/core/templates/` the test went red (`.../src/core/templates/home.html != .../src/templates/home.html`), then the file was moved back.
- [ ] 5. The header shows the app name, and so does the page title: the `<header>` text contains "Learning Companion", and so does the `<title>` text. Test: `test_home.py`, with the `HTMLParser` helper added here. Impl: `base.html`. Covers: AC3.
- [ ] 6. The nav shows "Goals" and "Log in" as non-link placeholders: both appear in the `<nav>` text, and neither appears in the text inside an element with an `href`. Test: `test_home.py`. Impl: `base.html`. Covers: AC4.
- [ ] 7. The layout renders Django messages: a request carrying `messages.info(request, "Profile saved.")` renders a page that contains "Profile saved.". Test: `test_home.py`, using `RequestFactory`, `SessionMiddleware` and `default_storage` as in the design decisions. Impl: a messages loop in `base.html`. Covers: AC5.
- [ ] 8. The home page fills the layout's content block with the pitch: the `<main>` text of `GET /` contains "Track your learning goals and sessions, and get AI-powered summaries and next steps.", and `render_to_string("base.html")` does not contain it. Test: `test_home.py`. Impl: `<main>{% block content %}{% endblock %}</main>` in `base.html`, and the pitch inside `{% block content %}` in `home.html`. Covers: AC6.
- [ ] 9. The layout has a footer: a `<footer>` element is present in `GET /`. Test: `test_home.py`. Impl: `base.html`. Covers: AC7.
- [ ] 10. `django_tailwind_cli` is installed: `apps.is_installed("django_tailwind_cli")` is `True`. Test: `test_apps.py`. Impl:
  - add `django-tailwind-cli>=4.8,<4.9` to `requirements.txt`, then `./.venv/bin/pip install -r requirements-dev.txt`, before running the test (the red is the assertion, not an import error)
  - in `settings.py`: `INSTALLED_APPS += "django_tailwind_cli"`, `STATICFILES_DIRS = [BASE_DIR / "assets"]` and `TAILWIND_CLI_VERSION = "4.3.3"`
  - `src/assets/.gitkeep`
  - `src/assets/css/tailwind.css` in `.gitignore`

  Covers: AC9, AC8 (setup).
- [ ] 11. The page links the Tailwind stylesheet without a built CSS file: `GET /` contains `<link rel="stylesheet" href="/static/css/tailwind.css">`. Test: `test_home.py`. It passes on a fresh checkout with no `tailwind build`, because nothing checks that the file exists. Impl: `{% load tailwind_cli %}` and `{% tailwind_css %}` in the `<head>` of `base.html`, plus the Tailwind utility classes for the simple layout. Covers: AC8.
- [ ] 12. Docs. No test. Commit `docs(setup-layout-tailwind): document the Tailwind build and the core app layout`.
  - In `CLAUDE.md`, add to Commands, next to `runserver`:
    - `./.venv/bin/python src/manage.py tailwind build`, the required build step after checkout (downloads the pinned binary into `src/.django_tailwind_cli/`)
    - `./.venv/bin/python src/manage.py tailwind runserver`, the watcher plus the dev server for everyday development
  - In `CLAUDE.md`, add to Layout: `src/core/` (home page, site-wide views), `src/templates/` (project-wide templates: `base.html` layout, pages), and `src/assets/` (static source dir; the built `css/tailwind.css` is git-ignored).
  - In `CLAUDE.md`, add to Stack: `TAILWIND_CLI_VERSION` is pinned in `settings.py`.
  - In `README.md`, add the `tailwind build` step to Setup before `runserver`, mention `tailwind runserver`, and add the same Layout entries.
  - Manual check before committing:
    - `tailwind build` writes `src/assets/css/tailwind.css`
    - `git status` doesn't list that file
    - with `tailwind runserver`, `/` serves the styled page

## Coverage
| AC | Steps |
|---|---|
| AC1 `GET /` 200, `home.html` extends `base.html` | 2, 3 |
| AC2 templates from `src/templates/` | 4 |
| AC3 app name in header and `<title>` | 5 |
| AC4 nav placeholders, not links | 6 |
| AC5 messages rendered | 7 |
| AC6 content block filled with the pitch | 8 |
| AC7 `<footer>` | 9 |
| AC8 stylesheet linked, no build needed for tests | 10, 11 |
| AC9 `django_tailwind_cli` and `core` installed, home view in `core` via `core/urls.py` at `/` | 1, 2, 10 |

The deliverables that tests can't verify (requirements, `.gitignore`, `README.md`, `CLAUDE.md`) are covered by steps 10 and 12.
