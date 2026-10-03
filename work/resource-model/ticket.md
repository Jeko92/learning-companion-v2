# Resources: Resource model
Issue: #13 · Branch: feature/resource-model

## Story
As a learner, I want reference material (articles, videos, repos, docs) stored against my goals, so that a later ticket (#14) can let me attach it to a goal and see it on the goal's page.

## Acceptance criteria

The model is `resources.Resource`, in a new app `resources`.

**Relation and ownership**
- [ ] AC1 A resource belongs to exactly one goal: a required foreign key with `on_delete=CASCADE` and `related_name="resources"`. Deleting a goal, or its owner, deletes that goal's resources and no others.
- [ ] AC2 `Resource.objects.owned_by(user)` returns only resources on that user's goals and can be chained (e.g. `.filter(goal=...)`). Another user's resources never appear.

**URL**
- [ ] AC3 `url` holds up to 2,048 characters and is stored trimmed. Through `full_clean()`:
  - `http://` and `https://` URLs are accepted, including an upper-case scheme.
  - `javascript:`, `data:`, `ftp:`, `mailto:`, relative and blank values are rejected.
  - A 2,048-character URL is accepted and a 2,049-character one is rejected.
- [ ] AC4 A database `CheckConstraint` rejects a URL that doesn't start with `http://` or `https://` (case-insensitive) when it is written through `update()`, so validator bypasses can't store e.g. `javascript:` URLs.

**Title**
- [ ] AC5 `title` is required, up to 200 characters, and stored trimmed by both `save()` and `full_clean()`. Through `full_clean()`, a blank or whitespace-only title is rejected, and so is a 201-character one.

**Type**
- [ ] AC6 `type` uses `Resource.Type`, a `TextChoices` with `article`, `video`, `repo` and `doc`, and defaults to `article`. `full_clean()` rejects any other value.
- [ ] AC7 A database `CheckConstraint` rejects any other type value written through `update()`.

**Uniqueness**
- [ ] AC8 The same URL can't be attached twice to one goal. `full_clean()` raises a `ValidationError` reading "This goal already has this resource.", and a direct database write raises `IntegrityError` (a `UniqueConstraint` on `goal` and `url`). The same URL on a different goal (the same user's or another user's) is allowed.

**Timestamps, ordering, display**
- [ ] AC9 `created_at` is set on creation and `updated_at` on every save. Resources are ordered newest first (`-created_at`, then `-id`).
- [ ] AC10 `str(resource)` is its title.

**Admin and migration**
- [ ] AC11 `Resource` is registered in the admin:
  - the changelist shows title, type and goal
  - it filters by type and searches title and URL
  - the goal is picked with autocomplete
  - the changelist and add pages load for a superuser
- [ ] AC12 The app is in `INSTALLED_APPS`, its initial migration is generated with `makemigrations`, and `makemigrations --check` reports no changes.
- [ ] AC13 `CLAUDE.md` documents the `resources` app and the `Resource` model contract (fields, validation, constraints, `owned_by`). `README.md` is updated too, where it lists apps.

## Out of scope
- Forms, views and display on the goal page (#14 `resource-attach`)
- Fetching page titles automatically
- URL normalisation for the uniqueness check (trailing slashes, host case, tracking parameters): URLs are compared exactly as stored, after trimming
- Editing or removing resources in the UI

## Notes
- **Title:** required (no fallback to the URL), and stored trimmed like `Goal.title`.
- **URL:** only `http` and `https`, because #14 renders resources as links and other schemes (`javascript:`, `data:`) would be an XSS vector.
  - The scheme is enforced twice: by the validator (`full_clean()`, forms, admin) and by a database `CheckConstraint`, so `update()` and `bulk_create()` can't bypass it.
  - The max length is 2,048, since Django's `URLField` default of 200 is too short for real documentation URLs.
- **Duplicates:** a `UniqueConstraint` on `(goal, url)` with `violation_error_message="This goal already has this resource."`, which `full_clean()` reports through `validate_constraints`.
- **Type:** defaults to `article`. As with `Goal.status`, a `CheckConstraint` keeps `update()` and `bulk_create()` from storing anything else.
- **Conventions applied without asking**, following `goals` and `learning_sessions`:
  - ownership through `goal.owner` (no owner field), with an `owned_by` queryset
  - timestamps
  - newest-first ordering
  - class-level options as tuples (RUF012)
  - admin autocomplete for the goal, through `GoalAdmin`'s existing search
- The app label `resources` is free (Django has no built-in app by that name).
