# Goals: filter the list by status
Issue: #10 · Branch: feature/goal-status-filter

## Story
As a logged-in learner, I want to filter my goals list by status, so that I can focus on what I'm working on, what's planned, or what's done.

## Acceptance criteria
- [x] AC1 `?status=<value>` filters the list. For each of `planned`, `in-progress` and `done`, `GET /goals/?status=<value>` lists only the current user's goals with that status, newest first.
- [x] AC2 A missing, empty or invalid status shows all goals. `GET /goals/`, `?status=` and `?status=bogus` each return 200 and list all of the current user's goals, with no error.
- [x] AC3 The filter stays scoped to the owner. With another user having goals of the same status, `?status=<value>` never lists that user's goals.
- [x] AC4 A filter control of links sits above the list in `<main>`: "All", "Planned", "In progress" and "Done".
  - "All" points to `/goals/`; each other link points to `/goals/?status=<value>`.
  - The active filter is not a link. It is shown with `aria-current="page"`.
  - With no status or an invalid one, "All" is the active filter.
- [x] AC5 Pagination keeps the filter. With 21 goals of status `done` (and others of other statuses):
  - Page 1 of `?status=done` has a "Next" link to `?status=done&page=2`.
  - Page 2 lists only the oldest `done` goal, and its "Previous" link keeps `status=done`.
  - Choosing a filter link always starts at page 1.
- [x] AC6 There are two empty states.
  - A filter that matches none of the user's goals shows "No goals with this status."
  - A user with no goals at all sees "No goals yet." with or without a filter.
- [x] AC7 Query parameters are never reflected as raw markup. `GET /goals/?status=done&x=<script>alert(1)</script>` returns 200, and the page doesn't contain the raw `<script>alert(1)</script>`. This applies even though pagination links carry the query string forward.
- [x] AC8 Every goal view is pinned to `OwnGoalsMixin`. A test walks the views routed in `goals.urls` and, for the list, detail, edit and delete views, asserts:
  - the view sets no `model`
  - its `get_queryset` resolves to `OwnGoalsMixin.get_queryset`

  The create view is exempt: it looks no goal up, and sets the owner in `form_valid`. This comes from the #9 security review (comment on #10).

## Out of scope
- Search, sorting, and filters other than status.
- Per-status counts on the filter links (the dashboard's job, #18).
- Carrying the filter into the detail, edit and delete pages or their redirects. "Back to goals" returns to the unfiltered list; the browser's Back button still returns to the filtered page.

## Notes
Answers from refinement (2026-10-02):
- **Filter control:** plain links for All, Planned, In progress and Done. The active one is marked with `aria-current="page"` and isn't a link. One click, no JavaScript, and every filtered view is bookmarkable.
- **Scope of the filter:** it lives only in the list URL. Pagination keeps it (AC5); the goal pages don't.
- **Empty states:** "No goals with this status." for an empty filter, kept separate from "No goals yet." (no goals at all).
- **No counts** on the filter links.

From earlier reviews (comments on #10):
- **#8:** pagination links must keep `?status=` (AC5). They're built from the current query with only `page` replaced, so AC7 guards that nothing is reflected raw.
- **#9:** a test pins that every pk-taking goal view, and the list, scopes through `OwnGoalsMixin` with no `model` (AC8).

Constraints and context:
- **Status values** are `Goal.Status.values` (`planned`, `in-progress`, `done`; #7). Filtering happens on `Goal.objects.owned_by(request.user)` via `OwnGoalsMixin.get_queryset`, so it can never widen to other users' goals.
- **The list** is paginated at 20 per page (#8). An out-of-range page stays a 404.
- **Docs:** `CLAUDE.md` (Goals bullet) and `README.md` get the filter. The plan includes this.

Status: the user approved these acceptance criteria (AC1–AC8) on 2026-10-02. The next step is `plan-ticket`.
