# Goals: detail, edit and delete
Issue: #9 · Branch: feature/goal-edit-delete

## Story
As a logged-in learner, I want to open, edit and delete my own goals, and be sure nobody else can see or change them, so that my goal list stays accurate.

## Acceptance criteria
- [ ] AC1 Three URLs in the `goals` namespace:
  - `reverse("goals:detail", args=[pk])` is `/goals/<pk>/`
  - `reverse("goals:edit", args=[pk])` is `/goals/<pk>/edit/`
  - `reverse("goals:delete", args=[pk])` is `/goals/<pk>/delete/`
- [ ] AC2 All three require login. An anonymous `GET` to each, and an anonymous `POST` to edit or delete, redirect to `settings.LOGIN_URL` with `next` set to the requested path. Nothing is changed or deleted.
- [ ] AC3 Nobody can see, change or delete another user's goal.
  - For another user's pk, the detail page, the edit page (`GET` and `POST`) and the delete page (`GET` and `POST`) all return **404**.
  - Each of those responses is identical to the one for a pk that doesn't exist, so nothing reveals whether the goal exists.
  - The other user's goal stays unchanged and is not deleted.
- [ ] AC4 The detail page shows your goal.
  - `GET /goals/<pk>/` returns 200 and renders `goals/goal_detail.html`, which extends `base.html`.
  - `<main>` shows the title, the status label, the description (line breaks kept), and the created and updated dates. It shows "No description." when the description is empty.
  - Links: "Edit goal" goes to `goals:edit`, "Delete goal" to `goals:delete`, and "Back to goals" to `goals:list`.
- [ ] AC5 On the list, each goal's title links to its detail page.
- [ ] AC6 The edit page renders your goal in a form.
  - `GET /goals/<pk>/edit/` returns 200 and renders `goals/goal_form.html`.
  - It has one `method="post"` form whose `action` is the edit URL, with a CSRF token, the `title`, `description` and `status` fields pre-filled, and no `owner` field.
  - The heading says "Edit goal", not "New goal".
  - A "Cancel" link goes back to the goal's detail page, matching the delete confirmation.
- [ ] AC7 A valid edit saves and returns to the goal.
  - The title, description and status are saved, with the title trimmed.
  - The response redirects to `/goals/<pk>/`, which shows "Goal updated." and the new values.
  - A posted `owner` is ignored; the owner stays the same.
- [ ] AC8 An invalid edit re-renders the form (200) with the field error, and leaves the goal unchanged. The rules are the same as for create:
  - a blank or whitespace-only title
  - a title over 200 characters
  - a description over 2,000 characters
  - an unknown status
- [ ] AC9 Delete asks for confirmation.
  - `GET /goals/<pk>/delete/` returns 200, renders `goals/goal_confirm_delete.html` (`DeleteView`'s default name), and shows "Delete “<title>”?".
  - It has one `method="post"` form with a CSRF token and a "Delete" button, plus a "Cancel" link to the goal's detail page.
  - A `GET` never deletes.
- [ ] AC10 Confirming deletes the goal. `POST /goals/<pk>/delete/` deletes it and redirects to `/goals/`, which shows "Goal deleted." and no longer lists it.
- [ ] AC11 Creating a goal now opens it. A valid create on `/goals/new/` redirects to the new goal's detail page (still with "Goal created."). This deliberately changes #8's AC6, and its test is updated in the same step.
- [ ] AC12 CSRF is enforced on edit and delete. With CSRF checks enforced, a `POST` without a token returns 403 and changes or deletes nothing. A `POST` with the token from the rendered form succeeds.
- [ ] AC13 Goal values are shown escaped. A title and description containing `<script>alert(1)</script>` appear only escaped on the detail page, the edit page and the delete confirmation. This pins the description escaping that #8's list couldn't cover.
- [ ] AC14 A wrongly ordered ownership mixin fails loudly. `OwnGoalsMixin` no longer sets `model`. A view that lists it *after* the generic view, e.g. `class V(DetailView, OwnGoalsMixin)`, raises `ImproperlyConfigured` instead of silently serving unscoped goals. This hardening comes from the #8 security review.
- [ ] AC15 `Goal.get_absolute_url()` returns `reverse("goals:detail", args=[goal.pk])`.
  - Create and edit redirect through it (the generic views' default success URL).
  - Templates link to a goal with `{{ goal.get_absolute_url }}`, and the admin shows "View on site".

## Out of scope
- Sessions, resources and AI actions on the detail page (#11+, #16, #17).
- The status filter on the list (#10), and keeping query parameters in pagination links (#10's notes).
- Bulk delete, undo or soft delete.

## Notes
Answers from refinement (2026-10-02):
- **Another user's goal is a 404,** identical to a missing goal, so nothing reveals that it exists. This matches `/profile/<id>/`.
- **After create and after edit,** the user goes to the goal's detail page, with "Goal created." or "Goal updated.". The create redirect changes #8 deliberately (AC11).
- **Delete uses a confirmation page** at `/goals/<pk>/delete/`: "Delete “<title>”?", with a POST button and a Cancel link. A `GET` never deletes. After deleting, the user goes to the list with "Goal deleted.".

From the #8 review (comment on #9):
- **Every pk-taking view lists `OwnGoalsMixin` first,** so lookups go through `Goal.objects.owned_by(request.user)`.
- **The mixin drops `model = Goal`,** so a wrongly ordered view raises `ImproperlyConfigured` instead of leaking (AC14).
- **There's a 404 test for each view and method** (AC3), and description escaping is pinned on the detail page (AC13).
- **Edit keeps `GoalForm`'s field allow-list,** so a posted owner is ignored (AC7).

Defaults I chose (say if you want them changed):
- **The edit page** reuses `goal_form.html`, with an "Edit goal" heading.
- **The detail page** shows the created and updated dates, and "No description." when the description is empty.
- **List titles** become links to the detail page.
- **The messages** are "Goal updated." and "Goal deleted.".

Added after a best-practice review (2026-10-02, the user's choice):
- **`Goal.get_absolute_url()`** (AC15): it is the generic views' success URL and the templates' link target, and the admin gets "View on site".
- **Django's default template names:** `goals/goal_detail.html`, `goals/goal_form.html` (shared by create and edit) and `goals/goal_confirm_delete.html`.
- **A Cancel link on the edit page** (AC6).

Constraints and context:
- **Ruff RUF012:** class-level options are tuples (CLAUDE.md).
- **Docs:** `CLAUDE.md` (Goals bullet, Layout) and `README.md` get the new pages. The plan includes this.

Status: waiting for the user to approve the acceptance criteria (AC1–AC15).
