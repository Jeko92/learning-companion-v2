# Plan: goal-list-create

## Research summary
- **Project patterns (#5–#7):**
  - Views are class-based. Login protection is `LoginRequiredMixin`, and ownership is enforced by a mixin overriding `get_queryset()` (`profiles.views.OwnProfileMixin`).
  - URL modules set `app_name` and are mounted from `config/urls.py` (`path("profile/", include("profiles.urls"))`).
  - Templates live in `src/templates/<app>/`, extend `base.html`, and render `{{ form }}` in `<form method="post" action="{% url … %}">` with `{% csrf_token %}`.
  - `base.html` messages show after redirects.
  - `goals.Goal` (#7):
    - `owner` FK (`related_name="goals"`, CASCADE), `title` (200, trimmed), `description` (`TextField`, blank), `status` (`Goal.Status`, default planned, `CheckConstraint`) and timestamps
    - `Meta.ordering = ("-created_at", "-id")`
    - one migration so far, `0001_initial`
- **The nav (`base.html`):** it starts with `<span>Goals</span>` for everyone.
  - `accounts/tests/test_nav.py` pins the anonymous text "Goals Log in Sign up" and the logged-in text "Goals alice Log out", with `links("nav") == [(profiles:mine, "alice")]`.
  - `core/tests/test_home.py` pins "Goals" as a non-link placeholder.
- **Tests:**
  - New views get an assertion-red from a literal path with the status asserted first (`404 != 200`).
  - Guards name a mutation, run with `PYTHONDONTWRITEBYTECODE=1`, then revert.
  - Escaping is checked on raw responses, because `PageParser` unescapes.
  - CSRF tests use `Client(enforce_csrf_checks=True)` with a GET first, so the cookie is set.
- **Django 6.1.1 (verified by probes):**
  - **`ListView(paginate_by=20)`:**
    - The context has `page_obj`, `is_paginated`, `paginator` and `object_list`.
    - `?page=2` works. `?page=99`, `?page=abc` and `?page=0` raise `Http404`; `?page=last` works.
    - `get_queryset()` ordering is respected, and `Meta.ordering` avoids the unordered-pagination warning.
  - **`validators=[MaxLengthValidator(2000)]` on a `TextField`:**
    - The form field gets no `max_length` and the textarea no `maxlength`.
    - The 2,001-character error comes from `ModelForm._post_clean` (`instance.full_clean`) and is attached to `description`: "Ensure this value has at most 2000 characters (it has 2001)."
    - The autodetector makes an `AlterField`.
  - **`CreateView` with `form.instance.owner = request.user`:** setting it in `form_valid` before `super()` saves with that owner. A POSTed `owner` is ignored when `Meta.fields` leaves it out, and model validation excludes non-form fields, so `is_valid()` passes without an owner.
  - **`SuccessMessageMixin`:** with `success_message = "Goal created."`, the message shows after the redirect.
  - **`GoalQuerySet.as_manager()`:** `owned_by(u).filter(...)` chains, `Meta.ordering` still applies, and no migration is needed (`use_in_migrations=False`).
  - **Status select:** an unbound ModelForm renders exactly `<option value="planned" selected>Planned</option>`, In progress and Done, with no blank option, because the field has a default and `blank=False`.

## Design decisions
- **`goals.models.GoalQuerySet(models.QuerySet)`** with `owned_by(user)` returning `self.filter(owner=user)`, used via `objects = GoalQuerySet.as_manager()`. It's the single scoping helper, and #9/#10 build on it.
- **`goals.views.OwnGoalsMixin(LoginRequiredMixin)`:** `model = Goal`, and `get_queryset()` returns `Goal.objects.owned_by(self.request.user)`.
  - `GoalListView(OwnGoalsMixin, ListView)` uses `paginate_by = 20` and `goals/goal_list.html`.
  - `GoalCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView)` uses `form_class = GoalForm`, `goals/goal_form.html`, `success_url = reverse_lazy("goals:list")` and `success_message = "Goal created."`. Its `form_valid` sets `form.instance.owner = self.request.user` before `super()`.
- **`goals.forms.GoalForm(ModelForm)`** with `Meta.fields = ("title", "description", "status")`, an explicit allow-list (never `"__all__"` or `exclude`), so `owner` can't be posted.
- **The description cap** is a model-level `validators=[MaxLengthValidator(2000)]` on `Goal.description`, with migration `goals/0002`. The form, `full_clean()` and the admin then share one limit.
- **URLs:** `src/goals/urls.py` with `app_name = "goals"`: `""` is `list`, and `"new/"` is `create`. They're mounted at `path("goals/", include("goals.urls"))`.
- **Templates:**
  - `goal_list.html`: an "Your goals" heading, a "New goal" link, and a `<ul>` of goals, each with its title and `get_status_display`. It shows "No goals yet." when there are none, and Previous/Next links only when `page_obj.has_previous` or `has_next`.
  - `goal_form.html`: a "New goal" heading and `{{ form }}`.
- **Nav:** for logged-in users, `<a href="{% url 'goals:list' %}">Goals</a>` comes before the username link. Anonymous visitors get no "Goals". The nav and home tests are rewritten deliberately in the same step.

## Steps
The user approved this plan on 2026-10-02.

Each step is one red–green–refactor cycle and one commit, `feat(goal-list-create): …`. Test modules:
- `src/goals/tests/test_models.py` (`owned_by` and the description cap)
- `src/goals/tests/test_views.py` (one class per page)
- `accounts/tests/test_nav.py` and `core/tests/test_home.py` (the nav)

Guard steps (7, 8, 10, 12) name their mutation.

- [x] 1. `Goal.objects.owned_by(user)` returns exactly that user's goals, newest first, and chains. Test: in `test_models.py`, assert `hasattr(Goal.objects, "owned_by")` first. Then alice has 2 goals and bob 1:
  - `list(Goal.objects.owned_by(alice))` is alice's two, newest first
  - `.owned_by(alice).filter(status=Goal.Status.DONE)` chains

  Expected red: `False is not true`. Impl: `GoalQuerySet` and `objects = GoalQuerySet.as_manager()`, with no migration (checked by `MigrationsTests`). Covers: AC3.
- [x] 2. The goals list is served. Logged in as alice, `GET /goals/`:
  - the status is **asserted first** (200)
  - `goals/goal_list.html` and `base.html` are used
  - `reverse("goals:list") == "/goals/"`

  Expected red: `404 != 200`. Impl: `goals/urls.py` (`list`), the `config/urls.py` include, a minimal `GoalListView(ListView)` with `model = Goal`, and the template. Covers: AC1 (list), AC4.
- [x] 3. The list requires login. An anonymous `GET /goals/` redirects to `f"{resolve_url(settings.LOGIN_URL)}?next=/goals/"`. Expected red: `200 != 302`. Impl: `LoginRequiredMixin`. Covers: AC2 (list).
- [x] 4. The list shows only your own goals, newest first, with status labels. Alice has "Learn Django" (in-progress, newer) and "Read docs" (planned, older); bob has "Bob's secret goal".
  - `page.text("main")` contains "Learn Django" before "Read docs", and the label "In progress".
  - Bob's title is absent.
  - A subtest with a user who has no goals: "No goals yet.".

  Expected red: the titles are missing. Impl: `OwnGoalsMixin` (scoped `get_queryset`) and the template loop with `get_status_display` and `{% empty %}`. Covers: AC4.
- [x] 5. The create page renders a goal form, and the list links to it. `GET /goals/new/`:
  - the status is asserted first (200), and `goals/goal_form.html` is used
  - `reverse("goals:create") == "/goals/new/"`
  - `forms("main")` has one `method="post"` form with the create URL as `action`, and a `csrfmiddlewaretoken` and `title` input
  - `page.elements` has a `textarea` named `description` and a `select` named `status`, whose options in order are planned (selected), in-progress and done
  - there is no element named `owner`
  - `/goals/`'s `links("main")` includes `("/goals/new/", "New goal")`

  Expected red: `404 != 200`. Impl: `GoalForm`, `GoalCreateView(LoginRequiredMixin, CreateView)` without `form_valid` yet, the `create` route, `goal_form.html`, and the list's "New goal" link. Covers: AC1 (create), AC4 (link), AC5.
- [x] 6. A valid create saves the goal for you and returns to the list. POST `title="  Learn Django "`, `description="Parts 1-7"`, `status="in-progress"`. Assert:
  - a redirect to `/goals/`
  - one goal, with owner alice, title "Learn Django", status in-progress
  - with `follow=True`, "Goal created." appears and the goal is first in `main`

  Expected red: `IntegrityError` (NOT NULL `owner_id`). That is the missing behaviour itself: the view doesn't set the owner yet. Impl: `form_valid` setting the owner, plus `SuccessMessageMixin`, `success_message` and `success_url`. Covers: AC6.
- [x] 7. A posted owner is ignored. Alice POSTs a valid goal with `owner=<bob.pk>`; the goal is owned by alice, and bob has none. Impl: none. Covers: AC7.
  - Guard. Mutation: `GoalForm.Meta.fields = ("title", "description", "status", "owner")`. It must go red (owned by bob). Revert afterwards.
  - Done 2026-10-02: green on arrival.
  - **Correction to the plan:** the planned mutation (adding `owner` to `Meta.fields`) **survived**. There are two layers of protection, and `form_valid` overwrites any posted owner with `request.user`. The field allow-list on its own is pinned by step 5 (no element named `owner`), which that mutation turns red.
  - The mutation used here breaks both layers in a realistic way: `owner` in the fields, plus `form_valid` setting the owner only `if not form.instance.owner_id`. The guard went red (`bob != alice`) and was then restored.
- [x] 8. Create requires login. An anonymous `GET` and `POST` (with valid data) to `/goals/new/` both redirect to login with `next=/goals/new/`, and `Goal.objects.count()` is unchanged. Impl: none, since step 5 has `LoginRequiredMixin`. Covers: AC2 (create).
  - Guard. Mutation: drop `LoginRequiredMixin` from `GoalCreateView`. It must go red (the GET is 200). Revert afterwards.
  - Done 2026-10-02: green on arrival. Under the mutation, both subtests went red: the GET returned 200, and the anonymous POST failed when assigning the owner. The view was then restored.
- [ ] 9. Invalid input re-renders the form and creates nothing. Subtests, each checking:
  - status 200 and `goal_form.html`
  - `assertFormError(form, field, message)` with the message in `page.text("main")`
  - `Goal.objects.count()` unchanged

  The cases:
  - `title=""` and `"   "` → `title` "This field is required."
  - 201 characters → `title` "Ensure this value has at most 200 characters (it has 201)."
  - a 2,001-character description → `description` "Ensure this value has at most 2000 characters (it has 2001)."
  - `status="bogus"` → `status` "Select a valid choice. bogus is not one of the available choices."

  Expected red: the 2,001-character description is accepted (`302 != 200`). Impl: `validators=[MaxLengthValidator(2000)]` on `Goal.description`; `makemigrations goals` creates `0002`. Covers: AC8.
- [ ] 10. CSRF is enforced on create. With `Client(enforce_csrf_checks=True)` and alice logged in, after a GET of `/goals/new/`:
  - a POST without a token returns 403 and creates nothing
  - a POST with the form's `csrfmiddlewaretoken` (asserting `len(tokens) == 1`) returns 302 and creates the goal

  Impl: none. Covers: AC9.
  - Guard. Mutation: `@method_decorator(csrf_exempt, name="dispatch")` on `GoalCreateView`. The first case must go red. Revert afterwards.
- [ ] 11. The logged-in nav links to the goals list; anonymous visitors see no "Goals". Rewrite `accounts/tests/test_nav.py`:
  - **Anonymous:** `text("nav") == "Log in Sign up"`, with links `[(login, "Log in"), (signup, "Sign up")]`.
  - **Logged in:** `text("nav") == "Goals alice Log out"`, with `links("nav") == [(reverse("goals:list"), "Goals"), (reverse("profiles:mine"), "alice")]`; the logout-form checks are unchanged.

  In `core/tests/test_home.py`, `test_nav_shows_goals_as_a_placeholder_that_is_not_a_link` becomes `test_anonymous_nav_has_no_goals_link`: "Goals" is not in the anonymous nav text. Expected red: the anonymous text is still "Goals Log in Sign up". Impl: `base.html` (move "Goals" into the logged-in branch as a link). Covers: AC10.
  - This deliberately changes #2 AC4, #3 AC9, #4 AC10 and #6 AC11, recorded in the commit body.
- [ ] 12. Goal values are shown escaped. Alice has a goal whose title and description are `<script>alert(1)</script>`. `GET /goals/` must not contain the raw payload (`assertNotContains`) and must contain `&lt;script&gt;alert(1)&lt;/script&gt;`. Impl: none. Covers: AC11.
  - Guard. Mutation: `{{ goal.title|safe }}` in `goal_list.html`. It must go red. Revert afterwards.
- [ ] 13. The list is paginated, 20 per page, counting only your goals.
  - Alice has 21 goals ("g01" oldest to "g21" newest, with `created_at` set via `update` so the order is deterministic); bob has 30.
  - **Page 1:** shows g21 to g02 (20 items), has a "Next" link to `?page=2`, and no "Previous".
  - **Page 2:** shows only g01 and has a "Previous" link.
  - `?page=99` returns 404.
  - None of bob's titles appear.

  Expected red: page 1 shows 21 items. Impl: `paginate_by = 20`, plus the Previous/Next links in `goal_list.html`. Covers: AC12.
- [ ] 14. Docs. No test. Commit `docs(goal-list-create): document the goal list and create pages`.
  - `CLAUDE.md`:
    - The Goals bullet: the pages `/goals/` (`goals:list`, paginated 20 per page) and `/goals/new/` (`goals:create`). `Goal.objects.owned_by(user)` is the one scoping helper (via `OwnGoalsMixin`). `GoalForm` has an explicit field allow-list and the owner is set from `request.user`. The description is capped at 2,000 characters by a model validator.
    - The Layout line for `src/goals/`.
  - `README.md`: a short user-facing line on the goal pages, and the Layout line.
  - Manual check: `migrate` the dev DB (applies `goals.0002`), then run `runserver` with curl and the fictional users:
    - alice sees her 3 goals and not bob's
    - creating a goal as alice shows "Goal created."
    - an anonymous `/goals/` redirects to login
    - delete the manual-check goal afterwards

## Coverage
| AC | Steps |
|---|---|
| AC1 URLs `goals:list` and `goals:create` | 2, 5 |
| AC2 login required (list, create GET and POST) | 3, 8 |
| AC3 `Goal.objects.owned_by(user)` | 1 |
| AC4 list: own goals, newest first, status labels, New goal link, empty state | 2, 4, 5 |
| AC5 create form: fields, status options, no owner | 5 |
| AC6 valid create: owner, trimmed, redirect, message | 6 |
| AC7 posted owner ignored | 7 |
| AC8 invalid input: field errors, nothing created (model-level description cap) | 9 |
| AC9 CSRF on create | 10 |
| AC10 nav link for logged-in users, no Goals for anonymous | 11 |
| AC11 escaping | 12 |
| AC12 pagination, 20 per page, owner-scoped, out-of-range 404 | 13 |
