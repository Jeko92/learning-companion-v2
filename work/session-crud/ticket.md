# Sessions: list, create, edit, delete for a goal
Issue: #12 · Branch: feature/session-crud

## Story
As a logged-in learner, I want to record, review, correct and remove the learning sessions of my own goals, so that I can track the time I spend on each goal.

## Acceptance criteria

URLs use shallow nesting. Collection routes are nested under the goal: `/goals/<goal_pk>/sessions/` (list) and `/goals/<goal_pk>/sessions/new/` (create). Member routes use only the session: `/sessions/<pk>/edit/` and `/sessions/<pk>/delete/`.

**Access and scoping**
- [ ] AC1 An anonymous user is redirected to the login page (with `next`) from all four session pages, and an anonymous POST to create, edit or delete changes nothing.
- [ ] AC2 Listing or creating sessions under another user's goal is a 404, identical to a missing goal pk. The 404 happens before any form handling, so a POST there stores nothing and returns a 404, whether its data is valid or invalid. It never returns a page of validation errors.
- [ ] AC3 Editing or deleting another user's session is a 404, identical to a missing session pk. The 404 happens before any form handling, so a POST there (valid or invalid data) changes or deletes nothing and returns a 404, never a page of validation errors.
- [ ] AC4 A scoping test walks the session URL patterns. For every session view it requires:
  - the goal or session is looked up through the owner-scoped querysets (`Goal.objects.owned_by` / `LearningSession.objects.owned_by`)
  - the ownership mixin comes first in the view's bases
  - no `model` attribute is set

  A new session route has to be added to the test deliberately, as with `GoalViewsScopingTests`.

**Goal detail page**
- [ ] AC5 The goal detail page has a "Sessions" section. It shows that goal's 5 most recent sessions, newest first (date, then creation), each with its date, duration, tags (alphabetical), notes and Edit/Delete links. Sessions of other goals never appear.
- [ ] AC6 The section shows the goal's total time across *all* its sessions, not just the 5 shown (tested with 6 or more sessions). It also has an "Add session" link to the create page and an "All sessions" link to the list page.
- [ ] AC7 A goal without sessions shows an empty-state message and the "Add session" link, and its total time is zero.

**List page**
- [ ] AC8 `/goals/<goal_pk>/sessions/` lists all sessions of that goal, newest first, with the same per-session details and links as AC5. It shows the goal's title, a link back to the goal, and an "Add session" link, and has an empty state.
- [ ] AC9 The list shows 20 sessions per page, with Previous/Next links built with `{% querystring %}`. A page number past the end and a non-numeric page (`?page=abc`) are both 404s.
- [ ] AC10 The goal detail page and the list page each run a fixed number of database queries, whatever the number of sessions and tags per session. There are no N+1 queries: tags are prefetched and the total is computed with one `Sum()` aggregate. This is checked with `assertNumQueries`.

**Create**
- [ ] AC11 The session form has an explicit field allow-list: date, duration (whole minutes), notes and tags. There is no goal field and no timestamp field.
- [ ] AC12 The date field renders as `<input type="date">`. On the create page it defaults to today's date, worked out on each request in the project's `TIME_ZONE` (not when the code is loaded). A test with a mocked clock checks this.
- [ ] AC13 A valid POST creates the session on the goal in the URL, redirects to the goal detail page and shows "Session added.". POSTed `goal`, `created_at` or `updated_at` values are ignored.

**Validation (create and edit)**
- [ ] AC14 Each of these is rejected with a form error, and nothing is saved: a future date; a duration of 0, over 1,440, or not a whole number; notes over 2,000 characters.
- [ ] AC15 Boundary values are accepted: a date of today, a duration of 1, a duration of 1,440, and a minimal submission (date and duration only, with empty notes and no tags).
- [ ] AC16 Tags are typed as comma-separated text. Entries are trimmed and normalised, empty entries are skipped, and duplicates are collapsed ignoring case (the first spelling is kept). An existing tag is reused regardless of case.
- [ ] AC17 Invalid tag entries (over 50 characters, control or invisible characters) are rejected, each one named in the error. More than 20 tags, or more than 1,000 characters of input, is rejected. A rejected form creates no tags.
- [ ] AC18 Tags are created only through `Tag.objects.get_or_create_by_name()`, and only when the session is saved.
- [ ] AC19 Saving a session and its tags is atomic. If the tag step fails (e.g. `get_or_create_by_name` raises), no session is created, an edited session keeps its previous values and tags, and no partial tags are left behind.

**Edit**
- [ ] AC20 The edit page is pre-filled with the session's values. The date is in `YYYY-MM-DD` form so the `type="date"` input shows it, and the tags are comma-separated text in alphabetical order. The page shows which goal the session belongs to.
- [ ] AC21 A valid POST updates the session, replaces its tags with the submitted ones, redirects to the goal detail page and shows "Session updated.". Submitting an empty tags field removes all of the session's tags. The session's goal can't be changed (a posted `goal` is ignored).

**Delete**
- [ ] AC22 A GET to the delete page shows a confirmation (session date, duration and goal) with a POST form and a Cancel link back to the goal. It deletes nothing.
- [ ] AC23 A POST deletes the session, redirects to the goal detail page and shows "Session deleted.". The goal and the tags themselves still exist afterwards.

**Shared tag vocabulary**
- [ ] AC24 Tags are shared between users. When one user edits or deletes their session tagged "python", another user's session keeps its "python" tag, and the `Tag` row still exists.

**Goal delete (goals app)**
- [ ] AC25 The goal delete confirmation page says how many sessions will be deleted along with the goal (e.g. "Its 3 sessions will be deleted too."). For a goal without sessions it shows no such warning. The count covers only that goal's sessions.

**Safety and docs**
- [ ] AC26 POSTs to create, edit and delete without a CSRF token are rejected (403) and change nothing.
- [ ] AC27 User-entered text (notes, tag names, goal title) is HTML-escaped on every session page, on the goal detail section and on the goal delete confirmation.
- [ ] AC28 `CLAUDE.md` documents the session routes, views, form and templates, and the goal delete warning.

## Out of scope
- A global list of sessions across all goals, or a sessions link in the main nav
- A session detail page (the list and goal detail show everything)
- Moving a session to another goal
- Tag autocomplete or picking from existing tags
- Filtering or sorting sessions
- Session-level AI features and dashboard aggregates (#18, #19)

## Notes
- **URLs:** shallow nesting was chosen over full nesting. Member routes carry only the session id, so there's no goal/session id pair to cross-check. Collection routes need the goal, so they are nested under it. The routes live in `learning_sessions/urls.py`, not `goals/urls.py`, so `GoalViewsScopingTests` (which asserts the exact set of goal routes) stays untouched.
- **Listing:** "both". The goal detail page shows the 5 most recent sessions, and a full paginated list page sits at `/goals/<goal_pk>/sessions/`.
- **Tags:** follow the profile focus-areas pattern (`profiles/forms.py`):
  - typed text, so other users' tags are never listed
  - `Tag.objects.clean_name()` before any lookup
  - the same 20-tag / 1,000-character caps
  - tags created in `_save_m2m`
  - `save()` wrapped in `transaction.atomic`
- **Goal fixed:** on create the goal comes from the URL (an owner-scoped lookup). It can't be edited.
- **Duration** is entered in whole minutes (1–1,440, model validators and `CheckConstraint`). The model already defaults the date to today and rejects future dates through `full_clean()`/forms.
- **Date input:** Django's default `DateInput` renders `type="text"` and uses a localized format. A `type="date"` input needs the ISO format (`%Y-%m-%d`), or the browser shows an empty field on edit (AC20).
- **Durations** are displayed as hours and minutes, e.g. "45 min", "2 h", "1 h 30 min". The total time on the goal uses the same format, from `Sum("duration_minutes")`.
- **After create, edit and delete**, the user is redirected to the goal detail page, since there is no session detail page. No `next` parameter is followed.
- **Ownership** is `goal.owner`. Sessions are looked up only through `LearningSession.objects.owned_by(request.user)`, and goals through `Goal.objects.owned_by(request.user)`.
- **Review round:** AC2/AC3 (404 before form handling), AC4 (mixin rules), AC6, AC9, AC10, AC11, AC12, AC15, AC19, AC20, AC21, AC24, AC25 and AC27 were tightened or added after the user asked for a best-practice, robustness and security review of the first draft. The user chose to include the goal delete warning (AC25) in this ticket.
