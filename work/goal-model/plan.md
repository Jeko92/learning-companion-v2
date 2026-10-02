# Plan: goal-model

## Research summary
- **Project conventions (#5 `profile-model`, #6 `profile-page`):**
  - An app is `src/<app>/` with an empty `__init__.py`, `apps.py` (`class XConfig(AppConfig): name = "x"`) and `tests/__init__.py`, and is added to `INSTALLED_APPS` after `"profiles"`.
  - The owner follows `profiles.Profile.user`: `settings.AUTH_USER_MODEL`, `on_delete=CASCADE`, an explicit `related_name`.
  - Migrations are generated with `makemigrations` in the step that changes a model. They are excluded from ruff, and the project-wide `MigrationsTests` (`makemigrations --check`) must stay green after every step.
  - Class-level options (`Meta.ordering`, admin `list_display` etc.) are tuples, because of RUF012.
  - `Tag` trims its name in `clean_fields()` and `save()`, because model `CharField`s don't strip. `Goal` trims its title the same way, but only at the ends: `strip()`, not `Tag`'s whitespace-collapsing `normalize_name`, since a title is free text.
- **Tests:**
  - Django's runner; `TestCase` for the database and `SimpleTestCase` for `test_apps.py`.
  - First reds must be assertions. A new app's first test fails on `apps.is_installed(...)`, and a new model's first test on `"goals.Goal" in {m._meta.label for m in apps.get_models()}`. The refactor of that step switches to a direct import.
  - Guards (behaviour that passes on arrival) each name a mutation that must turn them red, which is then reverted.
  - Admin tests: `assertIn(Model, admin.site._registry)`, plus `force_login` as a superuser and a GET of the changelist.
- **Django 6.1.1 (verified by probes):**
  - **`TextChoices`:** a nested `TextChoices` with `"planned"`, `"in-progress"` and `"done"` gives `.values`, `.labels` and `.choices` in declaration order. `default=Status.PLANNED` works, and `max_length=11` fits "in-progress". `full_clean()` with `status="bogus"` gives `{"status": ["Value 'bogus' is not a valid choice."]}`.
  - **Timestamps:** `auto_now_add` and `auto_now` call `timezone.now()` in `pre_save`, so `unittest.mock.patch("django.utils.timezone.now", return_value=t)` controls them. After creating at t1 and saving at t2, `created_at == t1` and `updated_at == t2`.
  - **Ordering:** `ordering = ("-created_at", "-id")` puts the higher id first when `created_at` ties.
  - **Admin:** the changelist returns 200 for a superuser. `list_filter = ("status",)` shows All, Planned, In progress, Done, and `search_fields = ("title",)` works.
  - **Title validation:** a `CharField` accepts `"   "` unless stripped first. `""` gives "This field cannot be blank.", and 201 characters gives "Ensure this value has at most 200 characters (it has 201).".

## Design decisions
- **`goals.Goal`:**
  - `owner = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="goals")`
  - `title = CharField(max_length=200)`
  - `description = TextField(blank=True)`
  - `status = CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)`: headroom above the 11 characters "in-progress" needs, so a future status doesn't also need a column change
  - `created_at = DateTimeField(auto_now_add=True)` and `updated_at = DateTimeField(auto_now=True)`
- **`class Status(models.TextChoices)`** is nested in `Goal`: `PLANNED = "planned", "Planned"`, `IN_PROGRESS = "in-progress", "In progress"`, `DONE = "done", "Done"`. The hyphen in `in-progress` matches #10's `?status=in-progress`.
- **Title trimming:** a small `strip()` in `clean_fields()` (before `super()`) and in `save()`, so a whitespace-only title fails as blank. Only strings are stripped, as in `Tag`.
- **Status integrity in the database:** `Meta.constraints = (models.CheckConstraint(condition=Q(status__in=Status.values), name="goals_goal_status_valid"),)`. `choices` are only checked by `full_clean()` and forms, so without it `update()`/`bulk_create()` could store any string, and #10's filter and #18's per-status counts rely on valid values.
- **Ordering:** `Meta.ordering = ("-created_at", "-id")`. `__str__` returns the title.
- **Admin:** `GoalAdmin` with `list_display = ("title", "owner", "status", "created_at")`, `list_filter = ("status",)` and `search_fields = ("title",)`.
- **Migrations:** generated per step during TDD (`0001` in step 2, `0002` in step 3, `0003` in step 6). Step 10 then collapses them into a single `0001_initial`, since a brand-new app should ship one clean initial migration and none of these is released yet.
- **Scoping helper, deferred to #8:** the intended pattern for goal views (#8, #9, #10) is a custom QuerySet method, `Goal.objects.owned_by(user)`, used by every view so another user's goal is a 404, like `OwnProfileMixin` for profiles. No view uses it yet, so it isn't built here. #8's plan should start from it.

## Steps
The user approved this plan on 2026-10-02, with four improvements applied after their review: the database `CheckConstraint`, `max_length=20`, one initial migration, and the `owned_by()` note.

Each step is one red–green–refactor cycle and one commit, `feat(goal-model): …`. Test modules: `src/goals/tests/test_apps.py`, `test_models.py` and `test_admin.py`. Guard steps (5, 8) name their mutation.

- [x] 1. The `goals` app is installed. Test: `test_apps.py` (`SimpleTestCase`, `apps.is_installed("goals")`). Expected red: `False is not True`. Impl: `src/goals/__init__.py`, `apps.py` (`GoalsConfig`), `tests/__init__.py`, and `"goals"` in `INSTALLED_APPS`. Covers: AC1.
- [x] 2. `Goal` has the agreed fields, and the description is optional. Test: `test_models.py`.
  - `goals.Goal` is registered.
  - Field introspection shows:
    - `owner` is a `ForeignKey` to `get_user_model()`, with `CASCADE` and `related_name="goals"`
    - `title.max_length == 200`
    - `description` is a `TextField` with `blank=True`
    - `status` is a `CharField` with `max_length == 20`
    - `created_at.auto_now_add` and `updated_at.auto_now` are both true
  - A goal with an empty description passes `full_clean()`.
  - The existing `test_custom_user_model_adds_no_fields` stays green.

  Expected red: `'goals.Goal' not found`. Impl: `src/goals/models.py`, with `status` a plain `CharField(max_length=20)` for now; `makemigrations goals` creates `0001`. Refactor: direct import. Covers: AC2, AC5.
  - Done 2026-10-02: red as expected (`'goals.Goal' not found`), then green. `status` got a plain `default="planned"` here, because AC5's `full_clean()` test would otherwise fail on a blank status. Step 3 still fails first on `hasattr(Goal, "Status")`.
- [x] 3. The status is a `TextChoices` defaulting to planned. Test:
  - `hasattr(Goal, "Status")` is asserted first.
  - `Goal.Status.values == ["planned", "in-progress", "done"]` and `.labels == ["Planned", "In progress", "Done"]`.
  - A new `Goal(owner=…, title="x")` has `status == Goal.Status.PLANNED`.
  - `full_clean()` with `status="bogus"` raises `ValidationError` "Value 'bogus' is not a valid choice." on `status`.
  - `Goal.objects.filter(pk=goal.pk).update(status="bogus")` inside `transaction.atomic()` raises `IntegrityError`.

  Expected red: `False is not True`. Impl: the nested `Status`, `choices` and `default` on the field, and the `CheckConstraint` in `Meta.constraints`; `makemigrations` creates `0002`. Covers: AC3.
  - Done 2026-10-02: red as expected (`False is not true`, and `ValidationError not raised`), then green. The `CheckConstraint` lists the values literally, because `Meta`'s body can't see the nested `Status`. A test that every `Goal.Status` value passes the constraint keeps the two in step.
- [x] 4. The title is required and stored trimmed. Test:
  - `Goal.objects.create(owner=…, title="  Learn Django ")`, then `refresh_from_db()`, gives "Learn Django".
  - With `subTest` for `""` and `"   "`, `full_clean()` fails on `title`.
  - A 201-character title fails with "Ensure this value has at most 200 characters (it has 201)."; 200 characters passes.

  Expected red: `'  Learn Django ' != 'Learn Django'`. Impl: strip in `save()` and `clean_fields()`. Covers: AC4.
- [ ] 5. The timestamps are maintained automatically. Test, with `patch("django.utils.timezone.now")`:
  1. create at t1: `created_at == updated_at == t1`
  2. change the title and save at t2: `created_at == t1` and `updated_at == t2`

  Impl: none, since step 2 defines the fields. Covers: AC6.
  - Guard. Mutation: `updated_at = DateTimeField(auto_now_add=True)`. It must go red (`updated_at` stays at t1). Revert afterwards.
- [ ] 6. Goals are ordered newest first. Test:
  - Create goals a, b and c.
  - Set a's `created_at` to an older time, and b's and c's to the same newer time, via `QuerySet.update`.
  - `list(Goal.objects.all()) == [c, b, a]`.

  Expected red: the default id order `[a, b, c]`. Impl: `Meta.ordering = ("-created_at", "-id")`; `makemigrations` creates `0003`. Covers: AC7.
- [ ] 7. `str(goal)` is the title. Expected red: `'Goal object (1)' != 'Learn Django'`. Impl: `__str__`. Covers: AC8.
- [ ] 8. Ownership. Test:
  - Alice has two goals and bob has one. `alice.goals.all()` holds exactly alice's two.
  - After `alice.delete()`, no goal of alice's remains, and bob's goal still exists.

  Impl: none, since step 2 defines `related_name` and `CASCADE`. Covers: AC9.
  - Guard. Mutation: `on_delete=models.PROTECT`. It must go red (`ProtectedError`). Revert afterwards.
- [ ] 9. `Goal` is in the admin. Test: `test_admin.py`.
  - `assertIn(Goal, admin.site._registry)` comes first.
  - Its `list_display` includes `title`, `owner`, `status` and `created_at`.
  - `"status" in list_filter` and `"title" in search_fields`.
  - As a superuser with a goal, `GET reverse("admin:goals_goal_changelist")` returns 200 and contains the goal's title.

  Expected red: the `assertIn` fails. Impl: `src/goals/admin.py` `GoalAdmin`. Covers: AC10.
- [ ] 10. One initial migration. No new test; this is a refactor, committed as `refactor(goal-model): ship the goals app with one initial migration`.
  - On the dev DB, `migrate goals zero` if any goals migrations were applied.
  - Delete `src/goals/migrations/0001–0003` and regenerate with `makemigrations goals`, giving a single `0001_initial` that holds the fields, the status choices and default, the check constraint and the ordering.
  - The full suite stays green, including `MigrationsTests` (`makemigrations --check`).
  - Then `migrate` the dev DB again.

  Covers: AC11.
- [ ] 11. Docs. No test. Commit `docs(goal-model): document the goals app`.
  - `CLAUDE.md`:
    - A Stack bullet on goals: owned by a user (`user.goals`, deleted with the user), `Goal.Status` values `planned`/`in-progress`/`done` (the hyphen matches the planned `?status=` filter, and a database check constraint enforces them), newest first, and the title stored trimmed. Goal views should scope through a `Goal.objects.owned_by(user)` helper, which #8 introduces.
    - A Layout line for `src/goals/`.
  - `README.md`: a Layout line for `src/goals/`.
  - Manual check:
    - `migrate` on the dev DB applies `goals.0001_initial`, plus `tags.0004` if still pending.
    - In `manage.py shell`, create and save a goal; check its default status and timestamps, then delete it.

## Coverage
| AC | Steps |
|---|---|
| AC1 `goals` app installed | 1 |
| AC2 fields, owner relation, `User` unchanged | 2 |
| AC3 `Goal.Status` values, labels, default, invalid rejected (validation and database) | 3 |
| AC4 title required, trimmed, max 200 | 4 |
| AC5 description optional | 2 |
| AC6 timestamps | 5 |
| AC7 newest-first ordering, id tie-break | 6 |
| AC8 `str(goal)` | 7 |
| AC9 `user.goals`, cascade on user delete | 8 |
| AC10 admin registration and changelist | 9 |
| AC11 migrations complete | 2, 3, 6, 10 (`MigrationsTests` green after each; one `0001_initial` at the end) |
