# Plan: session-model

## Research summary
Condensed from three read-only research reports (app scaffolding, test setup, data layer), 2026-10-02.

**App scaffolding, following `goals` and `tags`:**
- `apps.py` sets only `name` (no `default_auto_field`); `BigAutoField` comes from Django 6.x's default.
- `__init__.py`, `migrations/__init__.py` and `tests/__init__.py` are empty.
- New apps go at the end of `INSTALLED_APPS` in `src/config/settings.py`, after `"goals"`.
- No URLs are needed for a model-only ticket.
- An app labelled `sessions` would clash with `django.contrib.sessions`. Nothing uses the reverse name `sessions` on `Goal` or `Tag`: Tag has only `profiles`, and Goal has none.

**Model conventions (`src/goals/models.py`):**
- Queryset: a `GoalQuerySet(models.QuerySet)` with `owned_by(user)` and a one-line prose docstring, attached as `objects = GoalQuerySet.as_manager()`.
- Meta options are tuples (ruff RUF012), e.g. `ordering = ("-created_at", "-id")`.
- Each constraint has a comment explaining why it exists. The syntax is `models.CheckConstraint(condition=Q(...), name="<app>_<model>_<what>")` (e.g. `goals_goal_status_valid`).
- Text limits are a model-level `MaxLengthValidator` on a `TextField`, so forms, `full_clean()` and the admin share one limit.
- `Goal.owner` cascades from the user, and `Profile.focus_areas` is `M2M("tags.Tag", blank=True, related_name="profiles")`.
- `GoalAdmin.search_fields = ("title",)` and `TagAdmin.search_fields = ("name",)` both exist, which `autocomplete_fields` requires.
- `TIME_ZONE = "UTC"`, `USE_TZ = True`. No date defaults exist anywhere yet.

**Tests (`src/goals/tests/`, `src/profiles/tests/`):**
- **Layout:** one `TestCase` per concern, users from `get_user_model().objects.create_user("alice")`, no factories, `subTest` for case lists.
- **Field introspection:** via `_meta.get_field(...)`: `related_model`, `remote_field.on_delete`, `remote_field.related_name`, `blank`.
- **Validation:** `with self.assertRaises(ValidationError) as caught: obj.full_clean()`, then `caught.exception.error_dict["<field>"]`. Boundaries pair a failing value with a passing one.
- **Constraints:** `with self.assertRaises(IntegrityError), transaction.atomic(): Model.objects.filter(pk=...).update(...)`. The valid values go through `update()` and `refresh_from_db()`.
- **Time:** patched with `patch("django.utils.timezone.now", return_value=<aware datetime>)`. `timezone.localdate()` calls `timezone.now()`, so the patch controls a `default=timezone.localdate` as long as the model refers to it through the `timezone` module. `from django.utils.timezone import localdate` would also work, since `localdate` looks up `now` at call time, but the module reference keeps that obvious.
- **Ordering:** create the rows, then force timestamps with `update()` to make ties.
- **Admin:** `assertIn(Model, admin.site._registry)`, the `list_display`/`list_filter` contents, and a superuser `force_login` GET of `admin:<app>_<model>_changelist`. Autocomplete is checked from the rendered page (`PageParser` from `core.tests.html`): the `<select>` has class `admin-autocomplete` (see `src/profiles/tests/test_admin.py`).
- **App test:** `test_apps.py` is a `SimpleTestCase` asserting `apps.is_installed("<app>")`.
- **Migrations:** `MigrationsTests` (`makemigrations --check`) lives in `src/accounts/tests/test_models.py`.
- **Commands:** run one module with `./.venv/bin/python src/manage.py test learning_sessions.tests.test_models --verbosity 2`, and the full suite with `./.venv/bin/python src/manage.py test src`. Both need `SECRET_KEY` (from `.env`).

**Precedent (`work/goal-model/plan.md`):**
- Step 1 installs the app, and step 2 creates the model. The first red is the registry check, and a refactor switches to a direct import.
- Migrations are generated per step, then collapsed into one `0001_initial` in a refactor step before the docs.
- A guard step that is green on arrival names a mutation that must go red. Mutations run with `PYTHONDONTWRITEBYTECODE=1`, because a stale `.pyc` once survived a same-size revert.

## Design decisions
- **App `learning_sessions`, `LearningSessionsConfig` with only `name`.** This avoids the `sessions` label clash and matches the one-app-per-domain layout. #12 adds the pages here.
- **No `owner` field.** Ownership is `goal.owner`, and `LearningSessionQuerySet.owned_by(user)` filters `goal__owner=user`. A copied owner could disagree with the goal's.
- **`duration_minutes = PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(1440)])` plus a `CheckConstraint`** named `learning_sessions_learningsession_duration_valid`. The validators give form and `full_clean()` errors on the field. The constraint stops `update()` and `bulk_create()`. `PositiveIntegerField`'s own database check allows 0, so the constraint is what rejects 0.
- **`date = DateField(default=timezone.localdate, validators=[reject_future_dates])`.**
  - `reject_future_dates` is a module-level validator in `learning_sessions/models.py` comparing against `timezone.localdate()`. It is a field validator so the error lands on `date`.
  - There's no database constraint for this, because "today" moves.
- **`notes = TextField(blank=True, validators=[MaxLengthValidator(2000)])`**, the same pattern as `Goal.description`.
- **`tags = ManyToManyField("tags.Tag", blank=True, related_name="sessions")`**, the same pattern as `Profile.focus_areas`. No typed-tag handling here; that arrives with #12's form.
- **`Meta.ordering = ("-date", "-created_at", "-id")`.** The date the session happened comes first. Sessions logged the same day sort by when they were recorded, and the id breaks the remaining ties.
- **Admin** sets `list_display = ("goal", "date", "duration_minutes")`, `list_filter = ("date",)` and `autocomplete_fields = ("goal", "tags")`. No `search_fields` (not asked for).
- **One `0001_initial` migration** for the new app, collapsed before release as in goal-model.
- **Field steps assert the name first.** Each step that adds a field first asserts the field name is in `{f.name for f in LearningSession._meta.get_fields()}`, so the red is an assertion failure, not `FieldDoesNotExist`.

## Steps
Each step is one red–green–refactor cycle and one commit, `feat(session-model): …`, unless stated otherwise. The test files are `src/learning_sessions/tests/test_apps.py`, `test_models.py` and `test_admin.py`.

- [x] 1. **The `learning_sessions` app is installed.**
  - Test: `test_apps.py`, `InstalledAppsTests.test_learning_sessions_app_is_installed` (`SimpleTestCase`, `apps.is_installed("learning_sessions")`). Expected red: `False is not True`.
  - Impl: `src/learning_sessions/__init__.py`, `apps.py` (`LearningSessionsConfig`), `migrations/__init__.py`, `tests/__init__.py`, and the `INSTALLED_APPS` entry after `"goals"`.
  - Covers: AC1.
- [x] 2. **A session belongs to a goal and goes with it.**
  - Test (`test_models.py`):
    - `"learning_sessions.LearningSession"` is in `{m._meta.label for m in apps.get_models()}` (the expected red: an assertion).
    - `goal` is a `ForeignKey` to `Goal`, with `CASCADE` and `related_name == "sessions"`.
    - Behaviour: alice has two sessions on one goal and bob has one. Deleting alice's goal deletes both of hers, and bob's remains. A second test does the same with `alice.delete()`, through her goals.
  - Impl: `src/learning_sessions/models.py` with `LearningSession` and its `goal` FK only, then `makemigrations learning_sessions`.
  - Refactor: switch the registry check to a direct `from learning_sessions.models import LearningSession`.
  - Covers: AC2.
- [x] 3. **`duration_minutes` is validated to 1–1,440.**
  - Test: the field is a `PositiveIntegerField`. With `subTest`, `full_clean()` rejects 0 and 1,441, and a missing value, with an error on `duration_minutes`, and accepts 1 and 1,440. Expected red: the field name is missing.
  - Impl: the field with `MinValueValidator(1)` and `MaxValueValidator(1440)`, plus a migration.
  - Covers: AC4.
  - Done 2026-10-02.
    - **Correction to the plan:** a required field added to an existing table makes `makemigrations` prompt for a default. Since the app has no data, each model-changing step deletes and regenerates `0001_initial` instead of adding a migration, so step 13 only has to confirm a single initial migration.
    - The red for the boundary test was a `TypeError` until the field-name check moved into the class `setUp`; then both tests failed on the assertion.
    - Step 2's fixtures now pass `duration_minutes=30`, because the column is required.
- [x] 4. **The database enforces the duration range.**
  - Test: for 0 and 1,441, `update(duration_minutes=…)` inside `transaction.atomic()` raises `IntegrityError`. For 1 and 1,440, `update()` then `refresh_from_db()` stores the value. Expected red: no `IntegrityError` for 1,441 (and for 0, which `PositiveIntegerField` allows).
  - Impl: `Meta.constraints` with the `CheckConstraint` and a comment saying why, plus a migration.
  - Covers: AC4.
- [x] 5. **`date` defaults to today.**
  - Test: with `django.utils.timezone.now` patched to `datetime(2026, 3, 10, 23, 30, tzinfo=UTC)`, a session saved without a date has `date == date(2026, 3, 10)`. The field is a `DateField`. Expected red: the field name is missing.
  - Impl: `date = DateField(default=timezone.localdate)`, plus a migration.
  - Covers: AC3.
- [x] 6. **A future date is rejected.**
  - Test: with `now` patched as in step 5, `full_clean()` rejects `date(2026, 3, 11)` with an error on `date`, and accepts `date(2026, 3, 10)` and `date(2025, 1, 1)`. Expected red: no `ValidationError` for tomorrow.
  - Impl: the `reject_future_dates` validator on `date`, plus a migration.
  - Covers: AC3.
- [x] 7. **`notes` is optional and capped at 2,000 characters.**
  - Test: the field is a `TextField` with `blank=True`. `full_clean()` accepts an empty value and `"n" * 2000`, and rejects `"n" * 2001` with an error on `notes`. Expected red: the field name is missing.
  - Impl: the field with `MaxLengthValidator(2000)`, plus a migration.
  - Covers: AC5.
- [ ] 8. **Sessions carry shared tags.**
  - Test:
    - Introspection: `tags` is a `ManyToManyField` to `Tag`, with `blank=True` and `related_name == "sessions"`.
    - Behaviour: one session gets two tags. A session of bob's shares one of them, and `tag.sessions` holds both sessions. Deleting a tag removes only the link, and the sessions remain.
    - Expected red: the field name is missing.
  - Impl: the field, plus a migration.
  - Covers: AC6.
- [ ] 9. **Timestamps, and newest first.**
  - Test:
    - `created_at`/`updated_at` are set (`auto_now_add`/`auto_now`, with `now` patched for a create and a later save).
    - Sessions on different dates come out by `-date`, regardless of creation order.
    - Two sessions on the same date come out by `-created_at`, forced with `update()`.
    - Two with the same date and `created_at` come out by `-id`.
    - Expected red: the field names are missing.
  - Impl: both timestamp fields, `Meta.ordering = ("-date", "-created_at", "-id")`, plus a migration.
  - Covers: AC8.
- [ ] 10. **`str(session)`.**
  - Test: `str(LearningSession(goal=<"Learn Django">, date=date(2026, 3, 10), duration_minutes=45)) == "Learn Django · 2026-03-10 · 45 min"`. Expected red: the default `LearningSession object (None)`.
  - Impl: `__str__`.
  - Covers: AC8.
- [ ] 11. **`owned_by(user)` returns only the user's sessions.**
  - Test:
    - Setup: alice has two goals with sessions, and bob has one goal with sessions. A tag `shared` is on sessions of both users, and a tag `alice-only` is only on alice's.
    - `hasattr(LearningSession.objects, "owned_by")` holds (the expected red: an assertion).
    - `set(owned_by(alice))` is exactly her sessions, and `set(owned_by(bob))` exactly his. It is chainable: `owned_by(alice).filter(goal=…)`.
    - `Tag.objects.filter(sessions__in=LearningSession.objects.owned_by(bob)).distinct()` is `{shared}`, never `alice-only`.
  - Impl: `LearningSessionQuerySet.owned_by` and `objects = LearningSessionQuerySet.as_manager()`.
  - Covers: AC7.
- [ ] 12. **`LearningSession` is in the admin.**
  - Test (`test_admin.py`):
    - `assertIn(LearningSession, admin.site._registry)` (the expected red).
    - `list_display` contains `goal`, `date` and `duration_minutes`, and `list_filter` contains `date`.
    - As a superuser, `admin:learning_sessions_learningsession_changelist` returns 200 and contains the session's `str`.
    - On `admin:learning_sessions_learningsession_add`, the `<select name="goal">` and `<select name="tags">` both carry class `admin-autocomplete` (via `PageParser`).
  - Impl: `src/learning_sessions/admin.py`.
  - Covers: AC9.
- [ ] 13. **Refactor: ship the app with one initial migration.** No new test. Commit `refactor(session-model): ship learning_sessions with one initial migration`.
  - Run `migrate learning_sessions zero` if the dev database applied any. Delete the generated migrations, then run `makemigrations learning_sessions`. The single `0001_initial` must hold the `CheckConstraint`.
  - The suite stays green, including `MigrationsTests` (`makemigrations --check`). Then run `migrate`.
  - Covers: AC1.
- [ ] 14. **Docs.** No test. Commit `docs(session-model): document the learning_sessions app`.
  - `CLAUDE.md`:
    - A "Learning sessions" Stack bullet after Goals, covering:
      - the app name and why it isn't `sessions`
      - `goal` (CASCADE, `goal.sessions`)
      - `date` (defaults to today, no future dates, checked only by `full_clean()`)
      - `duration_minutes` (1–1,440, validators and a `CheckConstraint`; the dashboard divides by 60)
      - `notes` (2,000 cap) and `tags` (`tag.sessions`, shared vocabulary; queries start from `owned_by`)
      - no owner field, with `owned_by(user)` filtering `goal__owner`
      - ordering, and the admin
    - The Tags bullet: "later for session tags" becomes "and for session tags".
    - A Layout line for `src/learning_sessions/`.
  - `README.md`: a Layout line for `src/learning_sessions/`, and the tags line mentions session tags.
  - Manual check: `migrate`, then in `manage.py shell` create a session for an existing goal without a date (it gets today), check `str()`, `owned_by()` and that `full_clean()` rejects 0 minutes, then delete it.

## Coverage
| AC | Steps |
|---|---|
| AC1 app installed, migration generated, `makemigrations --check` clean | 1, 13 |
| AC2 `goal` FK, CASCADE, `goal.sessions`; goal and user deletion | 2 |
| AC3 `date` defaults to today, future rejected | 5, 6 |
| AC4 `duration_minutes` 1–1,440 by validators and `CheckConstraint` | 3, 4 |
| AC5 `notes` optional, 2,000 cap | 7 |
| AC6 `tags` M2M to `Tag`, shared, `tag.sessions` | 8 |
| AC7 `owned_by(user)` scopes sessions and the tags reached through them | 11 |
| AC8 ordering, timestamps, `str()` | 9, 10 |
| AC9 admin registration, columns, filter, autocomplete, changelist | 12 |

Status: the user approved this plan on 2026-10-02. The next step is `tdd-implement`.
