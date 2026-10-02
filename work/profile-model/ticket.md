# Profile: model with name, cohort, focus areas
Issue: #5 · Branch: feature/profile-model

## Story
As a learner using the Learning Companion, I want every account to have a profile with my name, cohort and focus areas, so that later pages can show my own data and the dashboard can group my learning by topic.

## Acceptance criteria
- [x] AC1 Two new apps are installed: `tags` and `profiles` (`apps.is_installed("tags")` and `apps.is_installed("profiles")` are both true).
- [x] AC2 `tags.Tag` has a `name` of at most 50 characters, and `str(tag)` is its name.
  - The name is stored trimmed: `Tag.objects.create(name="  Python ")` stores `"Python"`.
  - A blank or whitespace-only name fails `full_clean()` with a `ValidationError`.
- [x] AC3 Tag names are unique regardless of case.
  - Creating `"python"` when `"Python"` exists raises an `IntegrityError`, enforced by the database, not only by validation.
  - A get-or-create lookup by name returns the existing tag for any case and surrounding-whitespace variant (`" PYTHON "` finds `"Python"`), keeping the first spelling. It creates a new tag only when none matches.
- [x] AC4 `profiles.Profile` is linked one-to-one to `settings.AUTH_USER_MODEL`, reachable as `user.profile`. Its fields:
  - `name`: up to 100 characters, may be blank
  - `cohort`: up to 50 characters, may be blank
  - `focus_areas`: many-to-many to `Tag`, may be empty

  `accounts.User` gains no fields; profile data lives only on `Profile`.
- [x] AC5 Every new user automatically gets exactly one profile, with an empty name and cohort and no focus areas. This applies to every way a user is created:
  - `create_user`
  - `create_superuser`
  - a successful `POST /accounts/signup/`

  Saving an existing user again doesn't create a second profile and doesn't raise.
- [x] AC6 Deleting a user deletes their profile.
- [x] AC7 `str(profile)` is the profile's name when it is set, and the username when it is blank.
- [x] AC8 Focus areas work as shared tags.
  - A profile can hold several tags.
  - Two profiles can share the same `Tag` row, so no duplicate is created.
  - A tag lists the profiles that use it.
  - Deleting a tag removes it from profiles without deleting any profile.
- [x] AC9 The admin covers both models.
  - `Tag` is registered with a search on `name`.
  - The `User` admin is still a `UserAdmin` and shows the profile inline (name, cohort, focus areas).
  - The admin's change page for a user returns 200 and contains the inline's fields.
- [x] AC10 Users who existed before this ticket get a profile too. Applying the `profiles` migrations to a database that already has users leaves every user with exactly one empty profile (a data migration, tested with the migration executor).
- [x] AC11 The migrations are complete: `makemigrations --check` reports no changes (the existing project-wide test stays green).

## Out of scope
- Profile pages and forms (view or edit your own profile): ticket #6, `profile-page`. It decides which fields the edit form requires.
- Collecting the name or cohort at sign-up. The #3 sign-up form stays username + password.
- Session tags. #11, `session-model`, reuses `Tag` through its own many-to-many.
- Tag extras such as slugs, colours, descriptions, or cleaning up unused tags.
- Per-user tag ownership. Tags are a shared vocabulary; whose data is shown is decided by the profile and session owner, not the tag.

## Notes
Answers from refinement (2026-10-02):
- **Tags: a dedicated `Tag` model in its own `tags` app, with many-to-many fields.**
  - Chosen over django-taggit (a new dependency, and generic relations make aggregating per tag across models awkward) and over a JSON list (it can't be shared or grouped in the ORM on SQLite).
  - #11 (`LearningSession.tags`) reuses `Tag`. #19 (dashboard hours per tag) can then `annotate` across the many-to-many.
  - The `tags` app is separate from `profiles` because sessions use it too.
- **`name` and `cohort` are optional:** blank when the profile is auto-created. Sign-up collects neither, and #6's edit form decides what to require.
- **Tag names are trimmed and unique regardless of case.**
  - The first spelling is kept for display, so "Python" and "python" are one tag, and duplicates can't split the dashboard totals.
  - Uniqueness is a database constraint on the lowercased name, not only form validation.
  - A get-or-create by name (AC3) is what #6 and #11 will use to turn typed input into tags.
- **Admin and backfill:** the profile is edited inline on the `User` admin, and `Tag` has its own admin page. A data migration creates profiles for users who already exist, so no account is left without one.
- **Auto-creation must cover every creation path.** Sign-up, `createsuperuser` and the admin's add-user page all end in `User.save()`. Raw saves (fixtures) and `bulk_create` are not covered, and nothing in this project uses them for users.

Constraints and context:
- `CLAUDE.md` says profile data goes on a `Profile` model, never on `User`, and to refer to the user through `get_user_model()` or `settings.AUTH_USER_MODEL`. `accounts/tests/test_models.py` already pins that `User` adds no fields.
- The project-wide `makemigrations --check` test (`accounts/tests/test_models.py`) covers the new apps automatically.
- `CLAUDE.md` (Layout, Stack) and `README.md` get the two new apps and the tag decision. The plan includes this.
- Depends on #3 (custom user model and sign-up), which is done.

Status: the user approved these acceptance criteria (AC1–AC11) on 2026-10-02. The next step is `plan-ticket`.
