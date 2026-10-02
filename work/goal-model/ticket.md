# Goals: Goal model
Issue: #7 · Branch: feature/goal-model

## Story
As a learner, I want my learning goals stored with a title, a description, a status and timestamps, so that the goal pages, sessions, resources, AI features and dashboard have one owned `Goal` to build on.

## Acceptance criteria
- [ ] AC1 A new `goals` app is installed (`apps.is_installed("goals")`).
- [ ] AC2 `goals.Goal` has these fields:
  - `owner`: a foreign key to `settings.AUTH_USER_MODEL`, with `on_delete=CASCADE` and `related_name="goals"`
  - `title`: up to 200 characters
  - `description`: a text field, which may be blank
  - `status`: one of `Goal.Status`
  - `created_at` and `updated_at`: timestamps

  `accounts.User` gains no fields.
- [ ] AC3 The status is a `Goal.Status` (`TextChoices`) with exactly three members, in this order:

  | Value | Label |
  |---|---|
  | `"planned"` | "Planned" |
  | `"in-progress"` | "In progress" |
  | `"done"` | "Done" |

  - A new goal defaults to `planned`.
  - Any other value fails `full_clean()` with a `ValidationError` on `status`.
  - The database also rejects an invalid status: writing one through `QuerySet.update()` raises `IntegrityError`. Added during planning (2026-10-02), at the user's request: a `CheckConstraint`, so `update()`/`bulk_create()` can't bypass the choices.
- [ ] AC4 The title is required and is stored trimmed.
  - `Goal.objects.create(title="  Learn Django ", …)` stores "Learn Django".
  - A blank or whitespace-only title fails `full_clean()` on `title`.
  - A 201-character title fails `full_clean()` on `title`; 200 characters is accepted.
- [ ] AC5 The description is optional. A goal with an empty description passes `full_clean()`.
- [ ] AC6 The timestamps are maintained automatically.
  - Creating a goal sets `created_at` and `updated_at`.
  - Saving it again leaves `created_at` unchanged and moves `updated_at` forward.
- [ ] AC7 Goals are ordered newest first by default. `Goal.objects.all()` returns goals by `created_at` descending; goals with the same `created_at` are ordered by id descending.
- [ ] AC8 `str(goal)` is the goal's title.
- [ ] AC9 Ownership:
  - `user.goals.all()` lists exactly that user's goals.
  - Deleting a user deletes their goals and leaves other users' goals untouched.
- [ ] AC10 `Goal` is registered in the admin with:
  - `list_display` including `title`, `owner`, `status` and `created_at`
  - `list_filter` on `status`
  - `search_fields` on `title`

  The admin changelist page returns 200 for a superuser.
- [ ] AC11 The migrations are complete: `makemigrations --check` reports no changes. The existing project-wide test stays green.

## Out of scope
- Views and pages for goals: list and create (#8), detail, edit and delete (#9), status filter (#10).
- Sessions and resources, and their cascade on goal deletion (#11, #13).
- AI summary fields on `Goal` (#16), and the dashboard counts (#18).
- Pagination and alternative sort orders.

## Notes
Answers from refinement (2026-10-02):
- **Ordering:** newest first (`-created_at`, then `-id` so equal timestamps stay stable). A goal doesn't move when it's edited.
- **Description:** optional (`blank=True`); a goal can be just a title.
- **Title:** required, up to 200 characters, stored trimmed. Model `CharField`s don't strip, so the model trims it itself, as `Tag` does, and a whitespace-only title fails as blank.
- **Owner deletion:** CASCADE. A user's goals are deleted with the account, like the profile. Later sessions and resources hang off `Goal`.

Defaults I chose (say if you want them changed):
- **The stored status values** are `planned`, `in-progress` and `done`, with a hyphen, matching #10's `?status=in-progress` filter, so no mapping is needed. #18 can count per status from `Goal.Status.choices`, including statuses with zero goals.
- **The admin's** list columns, status filter and title search.

Constraints and context:
- **Owner reference:** always through `settings.AUTH_USER_MODEL` (CLAUDE.md), as `profiles` does. `User` gains no fields; the existing test pins that.
- **Ownership scoping** of goal pages (another user's goal is a 404) belongs to #8 and #9. CLAUDE.md already says any pk-taking view must scope its queryset to `request.user`.
- **Ruff RUF012:** class-level options (`Meta.ordering`, admin `list_display` etc.) are tuples (CLAUDE.md).
- **Docs:** `CLAUDE.md` (Layout, Stack) and `README.md` get the `goals` app. The plan includes this.
- **Workflow change in this branch:** its first commit carries the reviewer-speed changes the user asked to ship with this ticket (`.claude/agents/*.md`, `final-review`).

Status: the user approved these acceptance criteria (AC1–AC11) on 2026-10-02. The next step is `plan-ticket`.
