# Dashboard: goal counts per status
Issue: #18 · Branch: feature/dashboard-status

## Story
As a logged-in learner, I want a dashboard that shows how many of my goals are planned, in progress and done, and that I land on after logging in, so that I see where I stand at a glance and can jump straight to the goals in each status.

## Acceptance criteria
- [x] AC1 An anonymous `GET /dashboard/` redirects to the login page with `next=/dashboard/`.
- [x] AC2 A logged-in `GET /dashboard/` returns 200 with the page title and `<h1>` "Dashboard" and a "Goals by status" section (`aria-labelledby` its heading) containing a table with one row per `Goal.Status`, in choice order (Planned, In progress, Done), each with the user's goal count, followed by a Total row with the sum.
- [x] AC3 A status with no goals is listed with 0. For example, a user whose goals are all planned sees In progress 0 and Done 0.
- [x] AC4 The counts come from one grouped ORM aggregation (`values("status")` + `annotate(Count(...))`, with the model's default ordering cleared). The page's query count is fixed and doesn't grow with the number of goals (pinned with `assertNumQueries`).
- [x] AC5 Only the current user's goals are counted (through `Goal.objects.owned_by`). Another user's goals in any status never change the numbers.
- [x] AC6 Each status row links to the goal list filtered by that status (`/goals/?status=<value>`). The Total row links to the unfiltered `/goals/`.
- [x] AC7 A user with no goals sees all three statuses at 0, a Total of 0 and a "Create your first goal" link to `goals:create`. A user with at least one goal doesn't see that link.
- [x] AC8 The logged-in nav has a "Dashboard" link to `/dashboard/`. The anonymous nav doesn't.
- [x] AC9 Logging in without a `next` parameter redirects to `/dashboard/`. A same-site `next` is still followed, and an off-site `next` falls back to `/dashboard/`.
- [x] AC10 A successful sign-up redirects to `/dashboard/`, and a logged-in user who opens the sign-up or log-in page is redirected to `/dashboard/`.
- [x] AC11 Logging out still redirects to `/`, and `/` stays the public home page, unchanged for both anonymous and logged-in visitors.
- [x] AC12 `/dashboard/` responds only to GET (and HEAD). A POST returns 405.

## Out of scope
- Session hours per tag and per week (#19 dashboard-hours). That ticket adds its sections to this page.
- CSS bars or charts. Counts are shown as a table only.
- Showing the dashboard at `/` or redirecting `/` for logged-in users.
- An active-link marker (`aria-current`) in the main nav.
- Per-status counts on the goal list's filter links.

## Notes
- The issue's open question "Should the dashboard become the landing page for logged-in users?" was answered with **redirect after login**. `LOGIN_REDIRECT_URL` points to the dashboard, which covers log-in, the sign-up success redirect and already-authenticated visitors to sign-up and log-in. `LOGOUT_REDIRECT_URL` stays `/`, because the landing page after log-out must be public. `next` handling stays restricted to same-site URLs (`url_has_allowed_host_and_scheme`).
- Some existing auth tests assert `"/"` as the post-login or post-sign-up target (e.g. `accounts/tests/test_signup.py`), and they will change with AC9 and AC10. Tests that use `settings.LOGIN_REDIRECT_URL` symbolically keep working.
- Display: a table plus a Total row, as allowed by the handout ("simple tables or bars"). Counts link to the existing `?status=` filter (`goals:list`, which accepts exactly `Goal.Status.values`).
- `Goal` has a default ordering (`-created_at`, `-id`). A `values().annotate()` grouping must clear it with `.order_by()`, otherwise the ordering columns split the groups.
- Updating `CLAUDE.md` (the dashboard page and its place in the layout, plus the new `LOGIN_REDIRECT_URL`) and, where it applies, `README.md` is part of this ticket.
- Handout: `instructions/challenge.md` → "Learning Companion - Dashboard and reporting". Depends on #8, which is done.
- **Approval:** the user approved the acceptance criteria (AC1–AC12) on 2026-10-03.
