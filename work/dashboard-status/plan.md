# Plan: dashboard-status

## Research summary
- **Apps.** Each `AppConfig` only sets `name`. Model-free apps already exist: `core` (apps, urls, views, tests) and `ai`. Every app has a `tests/test_apps.py` asserting `apps.is_installed("<app>")`. `INSTALLED_APPS` (`config/settings.py:41-57`) lists the project apps after `django_tailwind_cli`, ending with `ai`. `config/urls.py:21-29` includes `admin/`, `accounts/`, `profile/` and `goals/`, then the `""` includes for learning_sessions, resources and core (core last). Namespaced apps set `app_name` in `urls.py`.
- **Views.** All views are CBVs except `core.views.home`. Login-required views use `LoginRequiredMixin`, and `get_context_data` calls `super()` first. Aggregates are inline in views today (`Sum(...)` with `or 0`). `GoalQuerySet` has only `owned_by(user)`. Restricted methods are a tuple, e.g. `http_method_names = ("post",)`.
- **Goals.** `Goal.Status` is `planned`/"Planned", `in-progress`/"In progress" and `done`/"Done". `Meta.ordering = ("-created_at", "-id")`, so a `values().annotate()` grouping needs `.order_by()` to drop the ordering columns from GROUP BY. The list's filter accepts exactly `Goal.Status.values` and links as `{% url 'goals:list' %}?status={{ value }}`.
- **Templates.** `base.html` hard-codes `<title>Learning Companion</title>` (no title block) and has `{% block content %}`, the messages list, and the nav (`:13-25`). The logged-in nav has the Goals link, the username link to `profiles:mine` and the Log out form. The anonymous nav has Log in and Sign up. Page headings are `<h1 class="text-2xl font-bold">`. Sections use `<section class="mt-10" aria-labelledby="…-heading">` with `<h2 id="…-heading" class="text-lg font-semibold">`. There is no `<table>` anywhere yet. Muted text is `text-sm text-slate-500` and links are `font-medium hover:underline`.
- **Auth redirects.** Every use of `LOGIN_REDIRECT_URL` resolves it through `resolve_url` or `redirect`, so a URL name works: `SignUpView.dispatch` (already authenticated), `SignUpView.get_success_url`, and `LogInView`'s inherited default redirect, which applies when `next` is missing or not same-site, and also when `redirect_authenticated_user` sends an authenticated visitor on. `LogOutView` uses only `LOGOUT_REDIRECT_URL` (stays `"/"`). Settings `:104-109` give each one a comment.
- **Tests.** Built-in runner. Each module has a `PASSWORD` constant, creates users with `create_user("alice", password=PASSWORD)` and logs in with `force_login`. There are no factories. `PageParser` (`core/tests/html.py`) provides `text(section)`, `links(section)` (ordered `(href, text)`), `forms(section)` and `elements`, for the sections title, header, nav, main and footer. Page test modules define `get_page(client, path)` and `login_redirect(path)`. An anonymous request is checked with `assertRedirects(..., login_redirect(path), fetch_redirect_response=False)`. Query counts are checked with `CaptureQueriesContext` (same count for small and large data) plus `assertNumQueries(n)`, with a comment listing each query. A 405 test is a plain `status_code == 405`.
- **Tests that will change.**
  - `accounts/tests/test_nav.py:38-51` pins the exact logged-in nav links (`[Goals, username]`) and text (`"Goals alice Log out"`).
  - `accounts/tests/test_signup.py:74` asserts `LOGIN_REDIRECT_URL == "/"`, and `:82` follows the sign-up redirect and asserts `PATH_INFO == "/"`.
  - `test_login.py:73-78` follows the login and expects "Welcome back, alice!" on the landing page. It keeps passing because the dashboard extends `base.html`, which renders messages.
  - Tests that use `settings.LOGIN_REDIRECT_URL` symbolically keep working.
  - `test_logout.py:25` pins `LOGOUT_REDIRECT_URL == "/"`, which stays.
  - The route-walking tests (`GoalViewsScopingTests` and the sessions/resources ones) only inspect their own URLconfs, so a separate `dashboard` app doesn't touch them.

## Design decisions
- **A new model-free app `dashboard`** (`src/dashboard/`, URL namespace `dashboard`, route `index` at `/dashboard/`, mounted in `config/urls.py` before the `""` includes). #19 dashboard-hours adds its sections here. Keeping the page out of `goals/urls.py` keeps it out of `GoalViewsScopingTests`, which would demand a single-object or multiple-object goal view.
- **Counting lives on the queryset:** `GoalQuerySet.status_counts() -> dict[str, int]`, with every `Goal.Status` value in choice order and 0 for the missing ones. It runs one grouped query: `values("status")` + `annotate(Count("id"))` + `.order_by()`. It is called as `Goal.objects.owned_by(request.user).status_counts()`, so it is unit-testable on its own and scoping stays the single `owned_by` path.
- **View:** `DashboardView(LoginRequiredMixin, TemplateView)`, template `dashboard/dashboard.html`, `http_method_names = ("get", "head")`. Its context is `status_rows`, a list of `(value, label, count)` in `Goal.Status` order, and `total_goals`, the sum of the counts (no second query).
- **Markup:** `<section aria-labelledby="goals-by-status-heading">` with `<h2>` "Goals by status" and a `<table>`.
  - The `<thead>` holds Status and Goals.
  - The `<tbody>` has one row per status, its label linking to `goals:list?status=<value>`.
  - The `<tfoot>` has a Total row linking to `goals:list`.
  - When `total_goals == 0`, a "Create your first goal" link to `goals:create` follows the table.
- **Title:** `base.html` gets `<title>{% block title %}Learning Companion{% endblock %}</title>`. The dashboard sets "Dashboard · Learning Companion". Pages that don't override the block keep today's title.
- **Nav:** "Dashboard" is the first logged-in link, before Goals. It is a link, never a form, because nav tests expect exactly one form there.
- **`LOGIN_REDIRECT_URL = "dashboard:index"`**, a URL name like `LOGIN_URL`. `LOGOUT_REDIRECT_URL` stays `"/"`, and `/` (`core.views.home`) is not changed.

## Steps
- [x] 1. **The `dashboard` app is installed.** — test: `src/dashboard/tests/test_apps.py` — impl: `src/dashboard/__init__.py`, `src/dashboard/apps.py`, `src/dashboard/tests/__init__.py`, `src/config/settings.py` (`INSTALLED_APPS`, after `resources` and before `ai`) — covers: groundwork
- [x] 2. **`status_counts()` counts every status in one grouped query.** It returns `{"planned": n, "in-progress": n, "done": n}` in `Goal.Status` order, with 0 for a status that has no goals, and runs in exactly one query (`assertNumQueries(1)`). Chained after `owned_by(alice)`, it ignores bob's goals. — test: `src/goals/tests/test_models.py` (`GoalStatusCountsTests`) — impl: `src/goals/models.py` (`GoalQuerySet.status_counts`) — covers: AC3, AC4, AC5
- [x] 3. **The route exists and is login-required.** `reverse("dashboard:index") == "/dashboard/"`, and an anonymous GET redirects to `login_redirect("/dashboard/")`. — test: `src/dashboard/tests/test_views.py` (`DashboardAccessTests`) — impl: `src/dashboard/urls.py`, `src/dashboard/views.py` (`DashboardView`), `src/config/urls.py`, `src/templates/dashboard/dashboard.html` (extends `base.html`) — covers: AC1
- [x] 4. **The logged-in page.** It returns 200 with `dashboard/dashboard.html` and `base.html`, the `<title>` "Dashboard · Learning Companion" and the `<h1>` "Dashboard". A logged-in POST returns 405. The 405 test may be green on first run because of `TemplateView`. If so, it stays as a regression pin next to the explicit `http_method_names`, and the commit notes this. — test: `src/dashboard/tests/test_views.py` (`DashboardAccessTests`, `DashboardPageTests`) — impl: `src/templates/base.html` (title block), `src/templates/dashboard/dashboard.html`, `src/dashboard/views.py` — covers: AC2, AC12
- [x] 5. **The Goals by status table.**
  - Fixture: alice has 2 planned goals and 1 done goal, and bob has goals in every status.
  - The section labelled by its "Goals by status" `<h2>` shows the rows Planned 2, In progress 0 and Done 1, in that order, then Total 3.
  - Bob's goals never count. A sibling test gives alice only in-progress goals and checks Planned 0 and Done 0.

  — test: `src/dashboard/tests/test_views.py` (`DashboardStatusCountsTests`) — impl: `src/dashboard/views.py` (`get_context_data`: `status_rows`, `total_goals`), `src/templates/dashboard/dashboard.html` — covers: AC2, AC3, AC5
- [x] 6. **Rows link to the filtered goal list.** The section's links are, in order, `/goals/?status=planned` "Planned", `/goals/?status=in-progress` "In progress", `/goals/?status=done` "Done" and `/goals/` "Total". — test: `src/dashboard/tests/test_views.py` (`DashboardStatusCountsTests`) — impl: `src/templates/dashboard/dashboard.html` — covers: AC6
- [x] 7. **Empty state.**
  - A user with no goals sees all three statuses at 0, a Total of 0, and a "Create your first goal" link to `reverse("goals:create")` in `main`.
  - A user with one goal doesn't see that link.

  — test: `src/dashboard/tests/test_views.py` (`DashboardEmptyStateTests`) — impl: `src/templates/dashboard/dashboard.html` — covers: AC7
- [x] 8. **Fixed query count.**
  - The page runs the same number of queries for 1 goal and for 30 goals spread over the statuses (`CaptureQueriesContext`).
  - It is pinned with `assertNumQueries(3)`, commented as session, user and the grouped status count. If the actual number differs because of middleware or the nav, use the real count and list each query in the comment.
  - This test is expected to be green on first run with step 5's code. It stays as a regression pin, and the commit notes this.

  — test: `src/dashboard/tests/test_views.py` (`DashboardQueryCountTests`) — impl: none expected — covers: AC4
- [x] 9. **Nav link.**
  - The logged-in nav's links are exactly `[("/dashboard/", "Dashboard"), ("/goals/", "Goals"), (profile, username)]`, and its text is `"Dashboard Goals alice Log out"`. The existing expectations in `test_nav.py` are updated to the new nav as part of this step.
  - The anonymous nav still has only Log in and Sign up.

  — test: `src/accounts/tests/test_nav.py` — impl: `src/templates/base.html` — covers: AC8
- [x] 10. **Logged-in users land on the dashboard.**
  - *As implemented:* the existing tests already cover each case: no `next`, same-site `next` (`SAFE_NEXT`), every off-site `next` in `UNSAFE_NEXTS`, the logged-in GET and POST to log-in and sign-up, and the followed sign-up and log-in. So instead of adding duplicates, they now assert a literal `DASHBOARD = "/dashboard/"` in place of `settings.LOGIN_REDIRECT_URL`, which as a URL name is no longer a path to compare against. That was the red: 30 failures, all `'/' != '/dashboard/'`. The followed log-in test also asserts it ends at `/dashboard/`.
  - Red: `test_signup.py:74` now expects `resolve_url(settings.LOGIN_REDIRECT_URL) == "/dashboard/"`, and `:82` expects the followed sign-up redirect to end at `/dashboard/`, still showing "Welcome, alice!".
  - New tests in `test_login.py`: a login without `next` redirects to `/dashboard/`; a same-site `next=/goals/` is still followed; an off-site `next=https://evil.example/` falls back to `/dashboard/`. An already-authenticated GET to `/accounts/login/` and to `/accounts/signup/` each redirect to `/dashboard/`.
  - Green: `LOGIN_REDIRECT_URL = "dashboard:index"`, with its settings comment kept accurate.

  — test: `src/accounts/tests/test_signup.py`, `src/accounts/tests/test_login.py` — impl: `src/config/settings.py` — covers: AC9, AC10
- [x] 11. **Log-out and home are unchanged.**
  - After a POST to `/accounts/logout/` the redirect target is `/`.
  - A logged-in GET to `/` returns 200 with `home.html` and isn't redirected.
  - Anonymous `/` is already covered by `core/tests/test_home.py`.
  - These tests are expected to be green on first run (regression pins for the redirect change); the commit notes this.

  — test: `src/accounts/tests/test_logout.py`, `src/core/tests/test_home.py` — impl: none expected — covers: AC11
- [ ] 12. **Docs.**
  - `CLAUDE.md`:
    - Auth bullet: `LOGIN_REDIRECT_URL = "dashboard:index"`.
    - A new Dashboard stack bullet: route, view, `status_counts()`, table and links, the empty state, the query count, and where #19 adds its sections.
    - Goals bullet: mention `status_counts()`.
    - Layout: `src/dashboard/`, and `dashboard/` under templates.
    - Note the `title` block in `base.html`.
  - `README.md`: the dashboard as the post-login landing page and the nav's Dashboard link; in Layout, `src/dashboard/` (adding the missing `resources/` to the templates bullet).
  - Run the full suite and `ruff check .` / `ruff format --check .`.

  — test: none (docs) — impl: `CLAUDE.md`, `README.md` — covers: docs obligation from ticket notes

## AC coverage
| AC | Steps |
|----|-------|
| AC1 anonymous redirect | 3 |
| AC2 page, title, h1, table, Total | 4, 5 |
| AC3 zero statuses listed | 2, 5 |
| AC4 one grouped query, fixed count | 2, 8 |
| AC5 only own goals | 2, 5 |
| AC6 links to filtered list | 6 |
| AC7 empty state link | 7 |
| AC8 nav link | 9 |
| AC9 login redirect and `next` | 10 |
| AC10 sign-up and authenticated redirects | 10 |
| AC11 log-out and home unchanged | 11 |
| AC12 GET only, POST 405 | 4 |
