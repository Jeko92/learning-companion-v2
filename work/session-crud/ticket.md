# Sessions: list, create, edit, delete for a goal
Issue: #12 · Branch: feature/session-crud

## Story
As a logged-in learner, I want to record, review, correct and remove the learning sessions of my own goals, so that I can track the time I spend on each goal.

## Acceptance criteria

URLs use shallow nesting. Collection routes are nested under the goal: `/goals/<goal_pk>/sessions/` (list) and `/goals/<goal_pk>/sessions/new/` (create). Member routes use only the session: `/sessions/<pk>/edit/` and `/sessions/<pk>/delete/`.

**Access and scoping**
- [ ] AC1 An anonymous user is redirected to the login page (with `next`) from all four session pages, and an anonymous POST to create, edit or delete changes nothing.
- [ ] AC2 Listing or creating sessions under another user's goal is a 404, identical to a missing goal pk. A POST to create there stores nothing.
- [ ] AC3 Editing or deleting another user's session is a 404, identical to a missing session pk. A POST there changes or deletes nothing.
- [ ] AC4 A scoping test walks the session URL patterns and requires every session view to look its goal or session up through the owner-scoped querysets (`Goal.objects.owned_by` / `LearningSession.objects.owned_by`). A new session route has to be added to that test deliberately, as with `GoalViewsScopingTests`.

**Goal detail page**
- [ ] AC5 The goal detail page has a "Sessions" section. It shows that goal's 5 most recent sessions, newest first (date, then creation), each with its date, duration, tags, notes and Edit/Delete links. Sessions of other goals never appear.
- [ ] AC6 The section shows the goal's total time across all its sessions, plus an "Add session" link to the create page and an "All sessions" link to the list page.
- [ ] AC7 A goal without sessions shows an empty-state message and the "Add session" link, and its total time is zero.

**List page**
- [ ] AC8 `/goals/<goal_pk>/sessions/` lists all sessions of that goal, newest first, with the same per-session details and links as AC5. It shows the goal's title, a link back to the goal, and an "Add session" link, and has an empty state.
- [ ] AC9 The list shows 20 sessions per page, with Previous/Next links built with `{% querystring %}`. A page number past the end is a 404.

**Create**
- [ ] AC10 The create form has date, duration (whole minutes), notes and tags fields, and no goal field. The date defaults to today.
- [ ] AC11 A valid POST creates the session on the goal in the URL, redirects to the goal detail page and shows "Session added.". A `goal` value in the POST data is ignored.

**Validation (create and edit)**
- [ ] AC12 A future date, a duration of 0, a duration over 1,440 or a non-integer duration, and notes over 2,000 characters are each rejected with a form error. Nothing is saved.
- [ ] AC13 Tags are typed as comma-separated text. Entries are trimmed and normalised, empty entries are skipped, and duplicates are collapsed ignoring case (the first spelling is kept). An existing tag is reused regardless of case.
- [ ] AC14 Invalid tag entries (over 50 characters, control or invisible characters) are rejected, each one named in the error. More than 20 tags, or more than 1,000 characters of input, is rejected. A rejected form creates no tags.
- [ ] AC15 Tags are created only through `Tag.objects.get_or_create_by_name()`, and only when the session is saved.

**Edit**
- [ ] AC16 The edit page is pre-filled with the session's values, including its tags as comma-separated text. It shows which goal the session belongs to.
- [ ] AC17 A valid POST updates the session, replaces its tags with the submitted ones, redirects to the goal detail page and shows "Session updated.". The session's goal can't be changed (a posted `goal` is ignored).

**Delete**
- [ ] AC18 A GET to the delete page shows a confirmation (session date, duration and goal) with a POST form and a Cancel link back to the goal. It deletes nothing.
- [ ] AC19 A POST deletes the session, redirects to the goal detail page and shows "Session deleted.". The goal and the tags themselves still exist afterwards.

**Safety and docs**
- [ ] AC20 POSTs to create, edit and delete without a CSRF token are rejected (403) and change nothing.
- [ ] AC21 User-entered text (notes, tag names, goal title) is HTML-escaped on every session page and on the goal detail section.
- [ ] AC22 `CLAUDE.md` documents the session routes, views, form and templates.

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
- **Tags:** follow the profile focus-areas pattern (`profiles/forms.py`): typed text so other users' tags are never listed, `Tag.objects.clean_name()` before any lookup, the same 20-tag / 1,000-character caps, and tags created in `_save_m2m`.
- **Goal fixed:** on create the goal comes from the URL (an owner-scoped lookup). It can't be edited.
- **Duration** is entered in whole minutes (1–1,440, model validators and `CheckConstraint`). The model already defaults the date to today and rejects future dates through `full_clean()`/forms.
- **Durations** are displayed as hours and minutes, e.g. "45 min", "2 h", "1 h 30 min". The total time on the goal uses the same format, from `Sum("duration_minutes")`.
- **After create, edit and delete**, the user is redirected to the goal detail page, since there is no session detail page.
- **Ownership** is `goal.owner`. Sessions are looked up only through `LearningSession.objects.owned_by(request.user)`, and goals through `Goal.objects.owned_by(request.user)`.
