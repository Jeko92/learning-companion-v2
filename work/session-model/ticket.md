# Sessions: LearningSession model
Issue: #11 · Branch: feature/session-model

## Story
As a learner, I want each learning session I log to be stored against one of my goals with its date, duration, notes and tags, so that later features (session pages, AI summaries, the hours dashboard) can show and total the time I spent.

## Acceptance criteria
- [x] AC1 A new app `learning_sessions` is installed and holds `LearningSession`. Its migration is generated with `makemigrations`, and `makemigrations --check` reports no changes.
- [x] AC2 A session belongs to one goal. `goal` is a required foreign key to `goals.Goal`, with `related_name="sessions"` (`goal.sessions`) and `on_delete=CASCADE`.
  - Deleting a goal deletes its sessions.
  - Deleting a user deletes their sessions, through their goals.
- [x] AC3 `date` is a `DateField` that defaults to today (`timezone.localdate()`). `full_clean()` accepts today and past dates and rejects a future date (tomorrow) with an error on `date`.
- [x] AC4 `duration_minutes` is a required `PositiveIntegerField` of whole minutes, from 1 to 1,440.
  - `full_clean()` accepts 1 and 1,440 and rejects 0 and 1,441 with an error on `duration_minutes`.
  - A database `CheckConstraint` enforces the same range, so `update()` to 0 or 1,441 raises `IntegrityError`.
- [x] AC5 `notes` is an optional `TextField` (`blank=True`), capped at 2,000 characters by a model-level `MaxLengthValidator`. `full_clean()` accepts 2,000 characters and rejects 2,001 with an error on `notes`.
- [x] AC6 `tags` is a `ManyToManyField` to `tags.Tag`, with `blank=True` and `related_name="sessions"`. A session can carry several tags, and one tag can be shared by sessions of different users.
- [x] AC7 `LearningSession.objects.owned_by(user)` returns only the sessions whose goal belongs to `user`. With alice and bob each having sessions, including sessions that share a tag:
  - `owned_by(bob)` never contains alice's sessions.
  - The tags reached through `owned_by(bob)` (`Tag.objects.filter(sessions__in=...)`) never include a tag that only alice uses.
- [x] AC8 Sessions are ordered newest first: `-date`, then `-created_at`, then `-id`. `created_at` (`auto_now_add`) and `updated_at` (`auto_now`) are set. `str(session)` is `"<goal title> · <YYYY-MM-DD> · <n> min"`.
- [x] AC9 `LearningSession` is registered in the admin:
  - `list_display` includes goal, date and `duration_minutes`
  - `list_filter` includes date
  - `autocomplete_fields` covers goal and tags
  - a superuser can load the changelist (200)

## Out of scope
- Views, URLs, forms and templates for sessions (#12 session-crud).
- Typed tag input and its normalisation. That arrives with the session form in #12, through `Tag.objects.get_or_create_by_name()`.
- Hour totals per tag or per week (#19 dashboard-hours), and AI summaries (#16, #17).
- Warning on the goal delete page that the goal's sessions go with it.

## Notes
Answers from refinement (2026-10-02):
- **Duration:** whole minutes, 1 to 1,440 (24 hours), as a `PositiveIntegerField`. Validators and a `CheckConstraint` both enforce the range. `Sum()` gives minutes; the dashboard divides by 60.
- **App:** a new `learning_sessions` app. An app labelled `sessions` would clash with `django.contrib.sessions`. #12 puts the session pages here too.
- **Goal deletion:** `CASCADE`. Sessions go with their goal, as goals go with their user.
- **Date:** defaults to today. A future date is rejected, since a session logs time already spent.

Defaults chosen during refinement (veto at approval):
- **The field is `duration_minutes`, not `duration`.** The handout says `duration`, but naming the unit keeps aggregation code from mixing up minutes and hours.
- **No `owner` field on the session.** Ownership comes from `goal.owner`, so the two can never disagree. `owned_by(user)` filters on `goal__owner`.
- **Timestamps and ordering** follow `Goal` (`created_at`/`updated_at`, newest first with the id as tiebreak).
- **Notes are capped at 2,000 characters**, as `Goal.description` is.

From the #5 (profile-model) security review (comment on #11):
- Session tags reuse `tags.Tag` through their own many-to-many field.
- Tags are a shared global vocabulary, so queries start from the owner's sessions and never list sessions through `tag.sessions` unscoped. AC7 pins this.
- Typed tags must go through `Tag.objects.get_or_create_by_name()`. That applies when #12 adds the form.

Constraints and context:
- `TIME_ZONE = "UTC"` with `USE_TZ = True`, so "today" is `timezone.localdate()` in UTC.
- Tests follow `src/goals/tests/` (`test_models.py`, `test_admin.py`, `test_apps.py`). Constraint tests use `update()` inside `transaction.atomic()` and expect `IntegrityError`.
- **Docs:** `CLAUDE.md` (Stack and Layout) and `README.md`, where it applies, describe the new app and model. The plan includes this.

Status: the user approved these acceptance criteria (AC1–AC9) on 2026-10-02. The next step is `plan-ticket`.
