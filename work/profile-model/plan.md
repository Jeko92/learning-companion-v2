# Plan: profile-model

## Research summary
- **Project layout (from #3/#4):**
  - Apps live in `src/<app>/` with an empty `__init__.py`, `apps.py` (`class XConfig(AppConfig): name = "x"`, no `default_auto_field`), and tests in `src/<app>/tests/` (also with `__init__.py`).
  - `INSTALLED_APPS` ends with `"django_tailwind_cli", "core", "accounts"`. `DEFAULT_AUTO_FIELD` is unset, so Django 6 uses `BigAutoField`. `AUTH_USER_MODEL = "accounts.User"`.
  - `accounts/admin.py` is three imports plus `admin.site.register(get_user_model(), UserAdmin)`, the stock `UserAdmin` with no subclass. The admin is mounted at `admin/` (`config/urls.py:22`).
  - `SignUpView` is a `CreateView`, so the user is saved through `form.save()`.
  - Migrations are Django-generated, and `src/**/migrations` is excluded from ruff (both check and format). Ruff uses its defaults (line length 88, rules E4/E7/E9/F).
- **Tests:**
  - Django's runner. Classes are `<Thing>Tests`. `TestCase` is used for anything touching the DB, and `SimpleTestCase` for `test_apps.py`, which asserts `apps.is_installed(...)`.
  - Users are built inline with `create_user(USERNAME, password=PASSWORD)` (`"alice"`, `"Tr4ck-Learning!"`). Sign-up posts `{"username", "password1", "password2"}` to `/accounts/signup/`.
  - `accounts/tests/test_models.py` already pins four things:
    - `User` adds no fields. It compares `_meta.fields` and `_meta.many_to_many`, so a reverse `profile` relation doesn't break it.
    - The User admin is an `isinstance(..., UserAdmin)`, so a subclass passes.
    - `makemigrations --check` runs project-wide, so the new apps' migrations must be committed with each model change.
  - No existing test logs into the admin, and none uses `MigrationExecutor` or `TransactionTestCase`.
  - `PageParser` (`core/tests/html.py`) exposes `elements`: `(tag, attrs)` for every start tag, which covers admin form inputs.
- **Django 6.1.1 (from the source and probes):**
  - **Functional unique constraint:** `UniqueConstraint(Lower("name"), name=...)` works on SQLite. It creates `CREATE UNIQUE INDEX … ((LOWER("name")))`, and a duplicate in a different case raises `IntegrityError`.
    - `full_clean()` reports it as a `ValidationError` under `__all__`, with the generic "Constraint “…” is violated." unless `violation_error_message` is set.
    - SQLite's `LOWER()` and `iexact` (`LIKE … ESCAPE`) are both **ASCII-only**. "Ärger" and "ärger" count as different tags. The two are consistent with each other, so lookups and the constraint agree.
  - **Model `CharField`** neither strips whitespace nor rejects `"   "` in `full_clean()`, because `EMPTY_VALUES` doesn't include it. Only `""` raises "This field cannot be blank.". Trimming must be done by the model itself.
  - **`post_save`:**
    - It sends `created` and `raw`.
    - `create_user`, `create_superuser` (`UserManager._create_user` → `save()`) and `ModelForm.save()` all go through `Model.save()`.
    - Probe: `[create_user True, create_superuser True, UserCreationForm.save True, re-save False]`.
    - Connect the receiver in `AppConfig.ready()` with `sender=settings.AUTH_USER_MODEL` (a lazy string is fine) and a `dispatch_uid`.
  - **Admin:** `UserAdmin` renders inlines on the **add** view as well. On add, `save_model` fires the signal and creates the profile. Then `save_related` saves a changed inline form as a second profile, which raises `IntegrityError` and rolls back the atomic `add_view`.
    - The idiomatic fix is `get_inlines(request, obj)` returning `[]` when `obj is None`, mirroring `UserAdmin.get_fieldsets` and `get_form`.
    - The admin's autodiscover imports `<app>.admin` in `INSTALLED_APPS` order, so unregistering and re-registering from `profiles/admin.py` would depend on that order. Instead, `accounts/admin.py` imports the inline directly and owns the single `UserAdmin` subclass.
  - **Data migration:**
    - Dependencies: `migrations.swappable_dependency(settings.AUTH_USER_MODEL)` plus the previous profiles migration.
    - `apps.get_model(settings.AUTH_USER_MODEL)` accepts a dotted label.
    - Historical models fire no real signal receivers, so the migration creates the profiles explicitly.
    - Reverse: `migrations.RunPython.noop`.
  - **Testing a data migration needs `TransactionTestCase`.** On SQLite the schema editor refuses to run inside `TestCase`'s atomic block (`NotSupportedError`). The verified pattern:
    1. `MigrationExecutor(connection)`
    2. `migrate([("profiles", "<from>")])`
    3. take historical models from `loader.project_state(...).apps` and create rows (no signal fires)
    4. `loader.build_graph()`
    5. `migrate([("profiles", "<to>")])`
    6. assert
    7. in `tearDown`, migrate back to `loader.graph.leaf_nodes()`, so the schema is at the latest state for the other tests

## Design decisions
- **Two apps, `tags` and `profiles`**, installed after `accounts`. `Tag` is shared vocabulary that sessions (#11) also use, so it gets its own app, and `profiles` depends on it.
- **`Tag`:**
  - `name = CharField(max_length=50)`.
  - `Meta.constraints = [UniqueConstraint(Lower("name"), name="tags_tag_name_ci_unique", violation_error_message="A tag with this name already exists.")]`, and `ordering = ["name"]`.
  - `__str__` returns the name.
  - Trimming happens in two places:
    - `save()` strips `name`, for `objects.create` and other direct saves.
    - `clean_fields()` strips `name` before calling `super()`, so a whitespace-only name becomes `""` and fails as blank in `full_clean()`.
- **`TagManager.get_or_create_by_name(name) -> (tag, created)`:**
  - It strips `name`, looks it up with `name__iexact`, which has the same ASCII-only case folding as the constraint, and returns `(tag, False)` if found.
  - Otherwise it builds `Tag(name=...)`, runs `full_clean()` (so blank raises `ValidationError`) and saves, returning `(tag, True)`.
  - This is the single entry point #6 and #11 will use for typed input.
- **`Profile`:**
  - `user = OneToOneField(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="profile")`
  - `name = CharField(max_length=100, blank=True)`
  - `cohort = CharField(max_length=50, blank=True)`
  - `focus_areas = ManyToManyField("tags.Tag", blank=True, related_name="profiles")`
  - `__str__` returns `self.name or self.user.get_username()`.
- **Signal:** `profiles/signals.py` has a `post_save` receiver for `settings.AUTH_USER_MODEL` that does `Profile.objects.get_or_create(user=instance)` when `created` is true and `raw` is false. It is connected in `ProfilesConfig.ready()` (`from . import signals`) with a `dispatch_uid`. `get_or_create` together with the `created` check makes a re-save a no-op.
- **Admin:**
  - `tags/admin.py`: `TagAdmin` with `search_fields = ("name",)`.
  - `profiles/admin.py`: `ProfileInline(StackedInline)` with `model = Profile`, `can_delete = False` and `fields = ("name", "cohort", "focus_areas")`. It uses `autocomplete_fields = ("focus_areas",)`, which needs the `TagAdmin` search.
  - `accounts/admin.py`: `class UserAdmin(auth_admin.UserAdmin)` with `inlines = [ProfileInline]` and `get_inlines()` returning `[]` when `obj is None`, registered once.
- **Backfill:** `profiles/migrations/0002_create_missing_profiles.py` is a hand-written `RunPython`. It creates a `Profile` for every user without one and is idempotent, with a `noop` reverse.
- **Migrations are generated with `makemigrations`** in the step that changes a model, so `MigrationsTests` stays green after every step. The tags constraint gets its own migration, `0002`.
- **Red phases and missing names.** A test module must not import a model that doesn't exist yet, because that is an import error. So the first test of each new model asserts the model is registered (`{m._meta.label for m in apps.get_models()}`), giving an assertion-red. The refactor of that step switches to a direct import.
  - Where a step's behaviour is a new method (step 6), the expected red is the `AttributeError` for the missing method. That is the missing behaviour itself, not a broken test.
- **Guard steps** (10, 11, 13) pass on arrival because earlier steps' design already gives the behaviour. Each names a mutation that must turn it red, after which the mutation is reverted, as in #4.

## Steps
The user approved this plan on 2026-10-02.

Each step is one red–green–refactor cycle and one commit, `feat(profile-model): …`. Test commands: `./.venv/bin/python src/manage.py test <app>.tests.test_<x>` for the step, and the full suite before every commit.

- [ ] 1. The `tags` app is installed. Test: `src/tags/tests/test_apps.py` (`SimpleTestCase`, `apps.is_installed("tags")`). Expected red: `False is not True`. Impl: `src/tags/__init__.py`, `src/tags/apps.py` (`TagsConfig`), `src/tags/tests/__init__.py`, and `"tags"` added to `INSTALLED_APPS` after `"accounts"`. Covers: AC1.
- [ ] 2. `Tag` exists with a `name` of at most 50 characters and shows it. Test: `src/tags/tests/test_models.py`:
  - `tags.Tag` is registered
  - `Tag._meta.get_field("name").max_length == 50`
  - `str(Tag.objects.create(name="Python")) == "Python"`

  Expected red: `'tags.Tag' not found in {…}`. Impl: `src/tags/models.py`; `makemigrations tags` creates `0001_initial`. Refactor: the test imports `from tags.models import Tag` directly. Covers: AC2.
- [ ] 3. The name is stored trimmed. `Tag.objects.create(name="  Python ")`, then `refresh_from_db()`, gives `name == "Python"`. Expected red: `'  Python ' != 'Python'`. Impl: `Tag.save()` strips `name`. Covers: AC2.
- [ ] 4. A blank or whitespace-only name fails validation. With `subTest` for `""` and `"   "`, `Tag(name=…).full_clean()` raises `ValidationError` with `"name"` in `error_dict`. Expected red: the `"   "` subtest doesn't raise. Impl: `Tag.clean_fields()` strips `name` before `super()`. Covers: AC2.
- [ ] 5. Names are unique regardless of case, enforced by the database:
  - with `"Python"` saved, `Tag.objects.create(name="python")` inside `transaction.atomic()` raises `IntegrityError`
  - `Tag(name="PYTHON").full_clean()` raises `ValidationError` whose messages include "A tag with this name already exists."

  Expected red: no `IntegrityError`. Impl: the `UniqueConstraint(Lower("name"), …)` with `violation_error_message`; `makemigrations tags` creates `0002`. Covers: AC3.
- [ ] 6. Get-or-create by name, which is case- and whitespace-insensitive. With `"Python"` saved:
  - `Tag.objects.get_or_create_by_name(" PYTHON ")` returns `(that tag, False)`, its name stays `"Python"`, and the count stays at 1
  - `get_or_create_by_name(" Django ")` returns `(new tag, True)` with name `"Django"`
  - `get_or_create_by_name("   ")` raises `ValidationError` and creates nothing

  Expected red: `AttributeError` (no such manager method). Impl: `TagManager` with `get_or_create_by_name`, and `objects = TagManager()`. Covers: AC3.
- [ ] 7. The `profiles` app is installed. Test: `src/profiles/tests/test_apps.py`. Expected red: `False is not True`. Impl: the `profiles` package, `apps.py` (`ProfilesConfig`, no `ready()` yet), `tests/__init__.py`, and `"profiles"` added to `INSTALLED_APPS` after `"tags"`. Covers: AC1.
- [ ] 8. `Profile` has the agreed fields. Test: `src/profiles/tests/test_models.py`. `profiles.Profile` is registered, and introspection with `_meta.get_field` shows:
  - `user`: a `OneToOneField` to `get_user_model()`, with `on_delete` `CASCADE` and `related_name` `"profile"`
  - `name`: `max_length` 100, `blank` true
  - `cohort`: 50, `blank` true
  - `focus_areas`: a `ManyToManyField` to `Tag`, `blank` true, `related_name` `"profiles"`

  The existing `test_custom_user_model_adds_no_fields` must stay green. Expected red: `'profiles.Profile' not found`. Impl: `src/profiles/models.py`; `makemigrations profiles` creates `0001_initial`. Refactor: direct import. Covers: AC4.
- [ ] 9. Every new user gets exactly one empty profile. Test: `src/profiles/tests/test_signals.py`, one `subTest` per path:
  - `create_user`
  - `create_superuser`
  - a successful `POST /accounts/signup/`

  Each asserts `Profile.objects.filter(user=user).count() == 1`, `name == ""`, `cohort == ""` and no `focus_areas`. Expected red: `0 != 1`. Impl: `src/profiles/signals.py` (the receiver as designed) and `ProfilesConfig.ready()` importing it. Covers: AC5.
- [ ] 10. Saving an existing user again creates no second profile and doesn't raise. Change `first_name` and `save()` twice, then check the count is still 1. Test: `test_signals.py`. Impl: none. Covers: AC5.
  - Guard. Mutation: the receiver creates `Profile.objects.create(user=instance)` without checking `created`. It must go red (`IntegrityError` on the re-save). Revert afterwards.
- [ ] 11. Deleting a user deletes their profile. `user.delete()`, then `Profile.objects.filter(pk=profile_pk).exists()` is false. Test: `test_models.py`. Impl: none, because `CASCADE` comes from step 8. Covers: AC6.
  - Guard. Mutation: `on_delete=models.PROTECT` in a scratch edit, with a matching migration not needed for the run. It must go red (`ProtectedError`). Revert afterwards.
- [ ] 12. `str(profile)` is the name, or the username when the name is blank. Subtests: blank gives `"alice"`; `name="Alice Smith"` gives `"Alice Smith"`. Test: `test_models.py`. Expected red: `'Profile object (1)' != 'alice'`. Impl: `Profile.__str__`. Covers: AC7.
- [ ] 13. Focus areas are shared tags. Alice's profile gets `Python` and `Django`, and Bob's gets `Python`. Assert:
  - Alice has both tags, and `Tag.objects.count() == 2` (one shared `Python` row)
  - `python.profiles` contains both profiles
  - after `python.delete()`, both profiles still exist, Alice keeps only `Django`, and Bob has none

  Test: `test_models.py`. Impl: none. Covers: AC8.
  - Guard. Mutation: drop `related_name="profiles"` from `focus_areas`, and regenerate nothing (`MigrationsTests` is not run). It must go red (`'Tag' object has no attribute 'profiles'`). Revert afterwards.
- [ ] 14. `Tag` is registered in the admin with a search on `name`. Test: `src/tags/tests/test_admin.py`: `admin.site._registry[Tag]` exists and has `"name"` in `search_fields`. Expected red: `KeyError` or `None`; written as `assertIn(Tag, admin.site._registry)`, so the red is an assertion. Impl: `src/tags/admin.py`. Covers: AC9.
- [ ] 15. The User admin's change page shows the profile inline. Test: `src/profiles/tests/test_admin.py`, as a superuser (`create_superuser` + `force_login`).
  - `GET reverse("admin:accounts_user_change", args=[alice.pk])` returns 200.
  - `PageParser.elements` contains inputs or selects named `profile-0-name`, `profile-0-cohort` and `profile-0-focus_areas`.
  - The registered User admin is still an `isinstance(…, auth_admin.UserAdmin)`.

  Expected red: the `profile-0-name` input is missing. Impl: `src/profiles/admin.py` (`ProfileInline`), and `accounts/admin.py` with a `UserAdmin` subclass using `inlines = [ProfileInline]`. Covers: AC9.
- [ ] 16. Adding a user in the admin creates exactly one profile. Test: `test_admin.py`, as a superuser.
  - `GET reverse("admin:accounts_user_add")` has no `profile-TOTAL_FORMS` input, so the inline is not on the add page.
  - Posting the add form (username plus the password fields of Django 6.1's admin add form, to be confirmed on the red run) creates the user, with `Profile.objects.filter(user=new_user).count() == 1`.

  Expected red: `profile-TOTAL_FORMS` is present on the add page. Impl: `UserAdmin.get_inlines()` returns `[]` when `obj is None`. Covers: AC5 (the admin path) and AC9.
- [ ] 17. Users who existed before get a profile through a data migration. Test: `src/profiles/tests/test_migrations.py`, a `TransactionTestCase`.
  1. Assert `("profiles", "0002_create_missing_profiles")` is in the executor's graph nodes, so the red is an assertion.
  2. Migrate `profiles` to `0001_initial`.
  3. With historical models, create user `old` with no profile, and user `has` with a profile (created by hand, since historical models fire no signal).
  4. `build_graph()`, then migrate to `0002_create_missing_profiles`.
  5. Assert each user has exactly one profile, and `old`'s is empty.

  `tearDown` migrates back to the leaf nodes. Expected red: the node is not in the graph. Impl: the hand-written `src/profiles/migrations/0002_create_missing_profiles.py` (`RunPython(create_missing_profiles, RunPython.noop)`, dependencies on `("profiles", "0001_initial")` and `swappable_dependency(settings.AUTH_USER_MODEL)`). Covers: AC10, and AC11 (`MigrationsTests` stays green).
- [ ] 18. Docs. No test. Commit `docs(profile-model): document the profiles and tags apps`.
  - `CLAUDE.md`:
    - The Stack auth bullet: every user gets a `Profile` (`user.profile`: `name`, `cohort`, `focus_areas`), created by a `post_save` signal in `profiles` and backfilled by a data migration.
    - A Stack line on tags: a shared `tags.Tag`, unique regardless of case (ASCII-only on SQLite). Always turn typed names into tags with `Tag.objects.get_or_create_by_name()`.
    - Layout lines for `src/tags/` and `src/profiles/`.
  - `README.md`: Layout lines for both apps.
  - Manual check:
    - `migrate` on the dev DB reports `0002_create_missing_profiles` applied, and in `manage.py shell` the user count equals the profile count.
    - `runserver`: the admin user change page shows the Profile inline with tag autocomplete, and the add-user page has no inline.

## Coverage
| AC | Steps |
|---|---|
| AC1 `tags` and `profiles` installed | 1, 7 |
| AC2 Tag name: max 50, `str`, trimmed, blank rejected | 2, 3, 4 |
| AC3 case-insensitive unique (DB) and get-or-create by name | 5, 6 |
| AC4 Profile fields, one-to-one `user.profile`, User unchanged | 8 |
| AC5 auto-created exactly once on every creation path, no duplicate on re-save | 9, 10, 16 |
| AC6 deleting a user deletes the profile | 11 |
| AC7 `str(profile)` | 12 |
| AC8 shared tags, reverse lookup, deleting a tag keeps profiles | 13 |
| AC9 Tag admin with search; User admin inline on the change page | 14, 15, 16 |
| AC10 backfill for existing users | 17 |
| AC11 migrations complete | 2, 5, 8, 17 (`MigrationsTests` green after each) |

Known limitation, recorded as accepted: case folding is ASCII-only on SQLite, so "Ärger" and "ärger" are separate tags. The lookup and the constraint agree, so no duplicate error is ever surprising.
