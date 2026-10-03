# Plan: resource-model

## Research summary

**Patterns to mirror**
- `goals/models.py`: a `strip()` helper; `clean_fields()` and `save()` trim the title so that `"   "` fails as blank; a `Status` `TextChoices`; a `CheckConstraint(condition=Q(status__in=(...literals...)), name="goals_goal_status_valid")`.
- `learning_sessions/models.py`: an FK to `"goals.Goal"` with CASCADE and a `related_name`; a `QuerySet` subclass with `owned_by(user)` → `filter(goal__owner=user)` and `objects = ...as_manager()`; `created_at` / `updated_at`; `Meta.ordering` and `Meta.constraints` as tuples (RUF012).
- Constraint names follow `<app>_<model>_<field>_valid`, each with a comment saying why the database enforces it too.
- Admin: `@admin.register`, `list_display`, `list_filter`, `search_fields`. `autocomplete_fields = ("goal",)` relies on `GoalAdmin.search_fields = ("title",)`, already used by `LearningSessionAdmin`.
- Apps are plain `AppConfig` classes with `name` only. `INSTALLED_APPS` ends with `"goals", "learning_sessions"`.

**Tests**
- `TestCase`, users from `get_user_model().objects.create_user("alice")`.
- Field checks use `_meta.get_field` with `assertIsInstance` and `remote_field.on_delete` / `related_name`. A `setUp` that checks the field exists fails cleanly while it is missing.
- `full_clean` checks loop with `subTest` and assert the key in `caught.exception.error_dict`. Values that should pass are simply run through `full_clean()`.
- Database constraints are tested with `with (subTest(...), assertRaises(IntegrityError), transaction.atomic()): qs.update(...)`. Every valid enum value also goes through `update()`, which keeps the hard-coded constraint list in step with the enum.
- Timestamps patch `django.utils.timezone.now`. Ordering forces `created_at` via `update()`, and ties are broken by id.
- `__str__` is tested on unsaved instances. `owned_by` is tested with `hasattr`, set comparisons and a chained `.filter()`. Cascade is tested on both goal delete and user delete.
- Admin tests:
  - registration via `admin.site._registry`
  - the changelist columns, filters and search fields as attributes
  - autocomplete by parsing the add page with `core.tests.html.PageParser` (`admin-autocomplete` class on the `<select>`)
  - a superuser logged in with `force_login`
- `InstalledAppsTests(SimpleTestCase)` checks `apps.is_installed("<app>")`.
- `accounts/tests/test_models.py:MigrationsTests` already runs `makemigrations --check --dry-run` for the whole project, so a missing `resources` migration fails the suite.

**Django 6.1 facts**
- `models.URLField.default_validators = [URLValidator()]` (http, https, ftp, ftps), and `max_length` defaults to 200. A validator passed in `validators=` is *added* to it, so a non-URL would report "Enter a valid URL." twice.
- `URLValidator` compares the scheme lower-cased, so `HTTPS://` passes.
- `Model.full_clean()` skips constraint validation for fields that already failed field validation, so a bad URL doesn't produce a second, constraint-level error.
- A `UniqueConstraint(fields=("goal", "url"), violation_error_message=...)` error lands in `NON_FIELD_ERRORS`. Its `validate()` is skipped when any of its fields is excluded, e.g. a ModelForm without a `goal` field (relevant for #14).
- A `CheckConstraint` with `Q(url__istartswith="http://") | Q(url__istartswith="https://")` works on SQLite (LIKE, which is case-insensitive for ASCII).

## Design decisions

- **New app `resources`** (`src/resources/`: `apps.py`, `models.py`, `admin.py`, `migrations/`, `tests/`), appended to `INSTALLED_APPS` after `learning_sessions`.
- **`HttpURLField(models.URLField)`** in `resources/models.py`, with `default_validators = (URLValidator(schemes=("http", "https")),)`. Rationale: it *replaces* rather than adds to the default validator, so there is one clean "Enter a valid URL." and no ftp/ftps. `url = HttpURLField(max_length=2048)`.
- **Belt and braces for the scheme:** `CheckConstraint(condition=Q(url__istartswith="http://") | Q(url__istartswith="https://"), name="resources_resource_url_http")`, so `update()` and `bulk_create()` can't store `javascript:`.
- **Trimming:** `clean_fields()` and `save()` trim `title` and `url` with a local `strip()` (the same one-liner as goals'; it isn't worth a shared module for two lines).
- **`Resource.Type`** `TextChoices`: `ARTICLE="article"`, `VIDEO="video"`, `REPO="repo"`, `DOC="doc"`, with labels "Article", "Video", "Repo", "Doc". `type = CharField(max_length=20, choices=Type.choices, default=Type.ARTICLE)`, plus `CheckConstraint(condition=Q(type__in=(...literals...)), name="resources_resource_type_valid")`.
- **`UniqueConstraint(fields=("goal", "url"), name="resources_resource_goal_url_unique", violation_error_message="This goal already has this resource.")`.**
  - Recorded for #14: a form without a `goal` field skips this check, so its view must validate it, e.g. by setting the goal on the instance and calling `validate_constraints()`, or by handling the duplicate in `clean()`.
- **`ResourceQuerySet.owned_by(user)`** → `filter(goal__owner=user)`. Ownership lives only on `goal.owner`, as for sessions.
- **One initial migration.** Nothing is released yet, so each step that changes the model regenerates `resources/migrations/0001_initial.py` (delete it, then `makemigrations resources`) rather than stacking migrations. The project-wide `MigrationsTests` keeps every step honest. The final migration depends on `goals.0002_alter_goal_description`.
- **Test helper.** `make_resource(goal, **fields)` in `resources/tests/test_models.py` fills in a distinct URL and title (a counter) once those fields exist. Earlier tests use it, so the later unique constraint doesn't break them; the helper is extended in the step that adds each field.
- **Red, not import errors.** Step 1's test is `apps.is_installed("resources")`, which is an assertion. Later model tests import `from resources import models as resource_models` (it exists after step 1) and check `hasattr(resource_models, "Resource")` / field existence in `setUp`, so a missing model or field fails an assertion.

## Steps

- [x] 1. **App installed.** `apps.is_installed("resources")` is true. — test: `resources/tests/test_apps.py` (`InstalledAppsTests`) — impl: `resources/__init__.py`, `resources/apps.py` (`ResourcesConfig`), `resources/models.py` (empty), `resources/migrations/__init__.py`, `config/settings.py` (`INSTALLED_APPS`) — covers: AC12
- [x] 2. **A resource belongs to one goal.**
  - The `goal` FK is required, targets `Goal`, uses CASCADE, and has `related_name="resources"`.
  - `goal.resources` lists them.
  - Deleting a goal deletes only its resources; deleting a user deletes only their goals' resources.

  — test: `resources/tests/test_models.py` (`ResourceGoalTests`) — impl: `resources/models.py` (`Resource` with `goal`), `resources/migrations/0001_initial.py` — covers: AC1
- [x] 3. **URL field.**
  - `url` is an `HttpURLField` with `max_length == 2048`, stored trimmed by `save()` and `full_clean()`.
  - `full_clean()` accepts `https://docs.djangoproject.com/en/6.1/`, `http://example.com` and `HTTPS://EXAMPLE.COM/x`, plus a URL of exactly 2,048 characters.
  - It rejects `javascript:alert(1)`, `data:text/html,x`, `ftp://example.com/f`, `mailto:a@example.com`, `/relative/path`, `""` and a 2,049-character URL, each with `"url"` in `error_dict` and exactly one message.
  - `make_resource` gains distinct URLs.

  — test: `resources/tests/test_models.py` (`ResourceUrlTests`) — impl: `resources/models.py` (`HttpURLField`, `url`, `strip`, `clean_fields`, `save`), regenerate migration — covers: AC3
- [x] 4. **URL scheme in the database.** `update(url=...)` with `javascript:alert(1)`, `data:text/html,x` and `ftp://example.com` raises `IntegrityError`. `http://…`, `https://…` and `HTTP://…` pass `update()`. — test: `ResourceUrlTests` (constraint test) — impl: `resources/models.py` (`Meta.constraints` url check), regenerate migration — covers: AC4
- [x] 5. **Title.**
  - `title` is a `CharField` with `max_length == 200`, not blank.
  - `"  Read the docs "` is stored as `"Read the docs"` on `save()`, and trimmed by `full_clean()`.
  - `""`, `"   "` and `"x" * 201` are each rejected with `"title"` in `error_dict`. 200 characters are accepted.
  - `make_resource` gains distinct titles.

  — test: `ResourceTitleTests` — impl: `resources/models.py` (`title`, trimming), regenerate migration — covers: AC5
- [x] 6. **Type choices.**
  - `Resource.Type.values == ["article", "video", "repo", "doc"]`, and the labels are "Article", "Video", "Repo", "Doc".
  - A new resource's type is `article`.
  - `full_clean()` rejects `"book"` with `"type"` in `error_dict` ("Value 'book' is not a valid choice.").

  — test: `ResourceTypeTests` — impl: `resources/models.py` (`Type`, `type`), regenerate migration — covers: AC6
- [x] 7. **Type in the database.** `update(type="book")` raises `IntegrityError`, and every `Resource.Type.values` entry passes `update()`. — test: `ResourceTypeTests` (constraint test) — impl: `resources/models.py` (type `CheckConstraint`), regenerate migration — covers: AC7
- [x] 8. **One URL per goal.**
  - A second resource with the same URL on the same goal fails `full_clean()` with "This goal already has this resource." in `error_dict[NON_FIELD_ERRORS]`, and `objects.create()` raises `IntegrityError`.
  - The same URL on alice's other goal and on bob's goal saves.

  — test: `ResourceUniquenessTests` — impl: `resources/models.py` (`UniqueConstraint`), regenerate migration — covers: AC8
- [x] 9. **Timestamps and ordering.**
  - `created_at` (`auto_now_add`) and `updated_at` (`auto_now`) work with `timezone.now` patched: `(t1, t1)` on create, `(t1, t2)` after a save at `t2`.
  - `Resource.objects.all()` is newest first, with ties on `created_at` broken by `-id`.

  — test: `ResourceTimestampTests`, `ResourceOrderingTests` — impl: `resources/models.py` (timestamps, `Meta.ordering`), regenerate migration — covers: AC9
- [x] 10. **Display.** `str(Resource(goal=..., title="Read the docs", url=...)) == "Read the docs"`. — test: `ResourceStrTests` — impl: `resources/models.py` (`__str__`) — covers: AC10
- [x] 11. **`owned_by`.**
  - `Resource.objects.owned_by(alice)` returns exactly alice's resources across her goals, never bob's.
  - It chains: `.owned_by(alice).filter(goal=goal)`.
  - The order stays newest first.

  — test: `ResourceOwnedByTests` — impl: `resources/models.py` (`ResourceQuerySet`, `objects`) — covers: AC2
- [x] 12. **Admin.**
  - `Resource` is in `admin.site._registry`.
  - `list_display` includes title, type and goal; `list_filter` includes type; `search_fields` includes title and url.
  - As a superuser, the changelist (`admin:resources_resource_changelist`) lists a resource's title, and the add page returns 200 with the goal `<select>` carrying `admin-autocomplete`.

  — test: `resources/tests/test_admin.py` (`ResourceAdminTests`) — impl: `resources/admin.py` (`ResourceAdmin`) — covers: AC11
- [x] 13. **Docs.** Docs only; the suite and `makemigrations --check` stay green (`docs(resource-model): ...`).
  - `CLAUDE.md`: a Resources stack bullet with the model contract (fields, `HttpURLField`, the trimming, the three constraints and why, `owned_by`, and the #14 note that a form without `goal` skips the unique check), plus a Layout entry for `src/resources/`.
  - `README.md`: an app list entry.

  — test: full suite, `ruff check .`, `makemigrations --check` — impl: `CLAUDE.md`, `README.md` — covers: AC13 (and AC12 verified)

## AC coverage

| AC | Steps |
|----|-------|
| AC1 belongs to one goal, cascade | 2 |
| AC2 `owned_by` | 11 |
| AC3 URL validation, trim, 2,048 | 3 |
| AC4 URL scheme database constraint | 4 |
| AC5 title required, trimmed, 200 | 5 |
| AC6 type choices, default article | 6 |
| AC7 type database constraint | 7 |
| AC8 unique URL per goal | 8 |
| AC9 timestamps, ordering | 9 |
| AC10 `__str__` | 10 |
| AC11 admin | 12 |
| AC12 installed and migration | 1, 2–9 (each regenerates 0001; `MigrationsTests`), 13 |
| AC13 docs | 13 |
