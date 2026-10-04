# Plan: goals-board

Issue #80, branch `feature/goals-board`. Outside the refine/plan/review skills at the user's request (2026-10-04); the state file is driven by hand (implementing → done → releasing), TDD and the hooks still apply.

## Decisions (interview)
- Dragging between columns changes the status only; each column stays newest first (no position field).
- Drag and drop through vendored SortableJS 1.15.7 (version and sha256 pinned by a test, like daisyUI), touch included.
- Every card also has a CSS-only "Move to" dropdown (a POST form): keyboard, screen-reader and no-JS users move goals with it.
- The status tabs stay: "All" shows the three columns, a filtered tab shows just that column (no dragging there). No pagination on the board.

## Design
- `goals:move` (`/goals/<pk>/move/`), `GoalMoveView(OwnGoalsMixin, SingleObjectMixin, View)`, POST only, `GoalMoveForm(StyledFormMixin, forms.Form)` with `status`. Saves `update_fields=["status", "updated_at"]`.
  - Form POST: success message "Moved “<title>” to <label>." and redirect to a same-site `next` (`url_has_allowed_host_and_scheme`) or `goals:list`; an invalid status is an error message, nothing saved.
  - `Accept: application/json` (the board's fetch): 200 `{"status", "label"}`, 400 `{"error"}`, no flash message.
- Board: `section[data-board-column]` per status (`aria-labelledby`, h2 + count badge in the status colour), `ul[data-board-list][data-status]` of `li[data-goal]` cards (title link + Move menu). Columns stack below `lg`, three side by side from `lg`. A "No goals." placeholder per empty column.
- `base.html` gets `{% block scripts %}`; the list loads `js/vendor/sortable.min.js` and `js/goal-board.js` (deferred) only on the All view with goals. The script POSTs with the card form's CSRF token, moves the card back and shows an error alert on failure, updates counts, placeholders and menus, and announces the move in a polite live region.
- Badges on the cards go: the column says the status (its count badge keeps the colour cue).

## Steps
- [x] 1. Move endpoint: form POST moves and redirects (message, safe `next`), invalid status, 404 for another user's goal, 405 for GET, CSRF enforced, JSON replies; `move` added to `GoalViewsScopingTests` — test: `goals/tests/test_board.py`, `goals/tests/test_views.py` — impl: `goals/forms.py`, `goals/views.py`, `goals/urls.py`
- [x] 2. Board markup: columns in status order with counts and placeholders, cards newest first, only your goals, filtered tab shows one column, no pagination (replaces the pagination tests deliberately), card badges replaced by column count badges (badge test updated deliberately) — test: `goals/tests/test_board.py`, `goals/tests/test_views.py` — impl: `templates/goals/goal_list.html`, `goals/views.py`
- [ ] 3. Move menu per card: one POST form to `goals:move` with CSRF and `next`, a "Move to <label>" button per other status — test: `goals/tests/test_board.py` — impl: `templates/goals/goal_list.html`, `components/_icon.html`
- [ ] 4. Drag and drop: vendored SortableJS pinned by version + sha256, `goal-board.js`, scripts only on the All view with goals, `board-ghost` style, Tailwind doesn't scan the vendored file — test: `goals/tests/test_board.py` — impl: `assets/js/`, `templates/base.html`, `templates/goals/goal_list.html`, `tailwind/source.css`
- [ ] 5. Docs: CLAUDE.md (no longer "no JavaScript": the board's progressive enhancement, the move endpoint, vendored SortableJS and how to update it), README — no test change

## Verification
Full suite, ruff, `makemigrations --check`, `tailwind build`, then Playwright at 360/768/1280 px in both colour schemes: drag a card between columns (persisted after reload), the Move menu with the keyboard, an error rollback.
