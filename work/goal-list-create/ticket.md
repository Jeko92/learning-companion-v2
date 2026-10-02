# Goals: list and create your goals
Issue: #8 · Branch: feature/goal-list-create

## Story
As a logged-in learner, I want to see a list of my own goals and add new ones, so that I can keep track of what I'm learning, and nobody else sees my goals.

## Acceptance criteria
- [x] AC1 Two URLs in a `goals` namespace: `reverse("goals:list")` is `/goals/` and `reverse("goals:create")` is `/goals/new/`.
- [x] AC2 Both pages require login. An anonymous `GET` to either, and an anonymous `POST` to `/goals/new/`, redirect to `settings.LOGIN_URL` with `next` set to the requested path, and the `POST` creates no goal.
- [x] AC3 `Goal.objects.owned_by(user)` returns exactly that user's goals, in the model's default order (newest first). It is a custom QuerySet method, so it chains, e.g. `Goal.objects.owned_by(user).filter(status=…)`.
- [x] AC4 The list page shows only your own goals.
  - `GET /goals/` returns 200 and renders `goals/goal_list.html`, which extends `base.html`.
  - `<main>` lists the current user's goals newest first, each with its title and status label (e.g. "In progress").
  - Another user's goal titles never appear.
  - A "New goal" link points to `goals:create`.
  - With no goals, `<main>` shows "No goals yet."
- [x] AC5 The create page renders a goal form.
  - `GET /goals/new/` returns 200 and renders `goals/goal_form.html`, which extends `base.html`.
  - `<main>` has one `method="post"` form whose `action` is `/goals/new/`. It has a CSRF token, a `title` input, a `description` textarea and a `status` select.
  - The `status` select offers exactly Planned, In progress and Done, with Planned selected.
  - The form has **no `owner` field**.
- [x] AC6 A valid create saves the goal for the current user and returns to the list.
  - The new goal's `owner` is `request.user`, its title is trimmed, and the chosen status is saved.
  - The response redirects to `/goals/`, which shows "Goal created." and lists the new goal first.
- [x] AC7 The owner can never be chosen. A `POST` that also sends `owner=<another user's id>` creates the goal owned by the logged-in user (mass-assignment guard).
- [x] AC8 Invalid input re-renders the form (200) with a field error, and creates nothing:
  - a blank or whitespace-only title gives "This field is required." on `title`
  - a 201-character title gives the standard length error on `title`
  - a description over 2,000 characters gives the standard length error on `description`. The limit is a `MaxLengthValidator(2000)` on the model field, so `full_clean()`, the admin and every form share it.
  - an unknown status gives the standard invalid-choice error on `status`
- [x] AC9 CSRF is enforced on create. With CSRF checks enforced, a `POST` without a token returns 403 and creates nothing. A `POST` with the token from the rendered form succeeds.
- [x] AC10 The logged-in nav links to the goals list.
  - "Goals" becomes a link to `goals:list`.
  - The logged-in nav's exact text stays "Goals alice Log out".
  - `links("nav")` is `[(reverse("goals:list"), "Goals"), (reverse("profiles:mine"), "alice")]`.
  - The anonymous nav no longer shows "Goals": its exact text is "Log in Sign up", with only those two links.
  - This deliberately changes the earlier nav and home tests (#2 AC4, #3 AC9, #4 AC10, #6 AC11), which pinned "Goals" as a non-link placeholder. Those tests are updated in the same step.
- [x] AC11 Goal values are shown escaped. A title and description containing `<script>alert(1)</script>` appear only escaped on the list page, never as raw markup.
- [x] AC12 The list is paginated, 20 goals per page.
  - With 21 goals, `/goals/` shows the 20 newest, and `/goals/?page=2` shows the oldest one.
  - Page links ("Previous"/"Next") appear only when there is such a page.
  - An out-of-range page (`?page=99`) returns 404, Django's default.
  - Pagination counts only the current user's goals.

## Out of scope
- Goal detail, edit and delete pages (#9). Until then, list items aren't links.
- Filtering the list by status (#10), and other sort orders.
- Sessions and resources on goals (#11+).
- Changing the admin's owner field. The #7 review suggested `raw_id_fields`; that is optional and left for later.

## Notes
Answers from refinement (2026-10-02):
- **Class-based generic views:** `ListView` and `CreateView` share a login-required mixin whose queryset is `Goal.objects.owned_by(request.user)`, like `OwnProfileMixin` for profiles. This sets the pattern for #9 (detail, update and delete views on the same mixin) and #10 (filtering the same queryset).
- **URLs:** `/goals/` (`goals:list`) and `/goals/new/` (`goals:create`). #9 adds `/goals/<pk>/`, `/goals/<pk>/edit/` and `/goals/<pk>/delete/`.
- **After create:** redirect to the list with "Goal created.". The new goal appears first, because goals are ordered newest first. Once #9 adds a detail page, it may redirect there instead.
- **Nav:** "Goals" is a link for logged-in users and absent for anonymous visitors.
- **Duplicate titles are allowed.** Two goals can share a title (e.g. a repeated "Learn Django" after one is done), so there is deliberately no uniqueness constraint.
- **Added after a best-practice review (2026-10-02, user's choice):**
  - pagination at 20 per page (AC12)
  - the description cap as a model-level `MaxLengthValidator(2000)` rather than form-only (AC8; a `goals/0002` migration that changes validators only, not the schema)
  - a separate backlog item for `LoginRequiredMiddleware` (secure by default)
- **From the #7 security review** (comment on #8):
  - the owner is never form input; it's set from `request.user`, and a test proves a posted `owner` is ignored (AC7)
  - every query goes through `Goal.objects.owned_by(user)` (AC3)
  - the description is capped (AC8)

Defaults I chose (say if you want them changed):
- **Create form:** status is selectable on create, defaulting to Planned.
- **List items:** title plus status label. There is no date column yet, since #10 and the dashboard handle status views.
- **Empty state:** "No goals yet."

Constraints and context:
- CLAUDE.md: any pk-taking view must scope its queryset to `request.user`. This ticket takes no pk yet, but `owned_by` is the helper #9 builds on.
- `LOGIN_URL = "accounts:login"`. Profile pages already use `LoginRequiredMixin`.
- Ruff RUF012: class-level options are tuples.
- `CLAUDE.md` (Stack, Layout) and `README.md` get the goal pages. The plan includes this.

Status: the user approved these acceptance criteria (AC1–AC12) on 2026-10-02. The next step is `plan-ticket`.
