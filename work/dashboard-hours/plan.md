# Plan: dashboard-hours

## Research summary
- **Model.** `LearningSession` (`src/learning_sessions/models.py`):
  - Fields: `date` (`DateField`, default `timezone.localdate`; future dates rejected only through `full_clean()`), `duration_minutes` (1–1,440), `tags` (M2M to `tags.Tag`, `related_name="sessions"`, `blank=True`, so a session can have no tags).
  - `LearningSessionQuerySet` has `owned_by(user)` (`goal__owner`) and `with_tags()` (tags prefetched by `Lower("name"), "id"`).
  - `Meta.ordering = ("-date", "-created_at", "-id")`.
  - Aggregates live as queryset methods with a one-sentence docstring (e.g. `GoalQuerySet.status_counts()`, `ResourceQuerySet.grouped_by_type()`), and the view chains them after `owned_by(request.user)`.
- **SQL, checked with `str(qs.query)`.**
  - `owned_by(u).values("tags", "tags__name").annotate(total=Sum("duration_minutes"))` LEFT OUTER JOINs the tag tables and groups by tag id and name.
  - Untagged sessions form one `(None, None)` group.
  - A session with N tags counts once in each of its N groups.
  - Ordering by `"-total"` or `Lower("tags__name")` only adds grouped expressions, so it is safe. Ordering by any non-grouped column (e.g. an explicit `order_by("-date")` on the incoming queryset) would split the groups, so call `.order_by()` first, as `status_counts()` does. SQLite sorts NULL first.
  - `TruncWeek("date")` on the `DateField` returns a `datetime.date`, the Monday of its week. SQLite computes `date - weekday()`. `.values("week").annotate(total=Sum(...))` groups by the week only.
- **Display.** The `duration` filter (`{% load session_format %}`) turns minutes into "45 min", "2 h", "1 h 30 min", and `None` or 0 into "0 min". Elsewhere totals are minutes passed through `|duration`, with `aggregate(...)["total"] or 0` because an empty `Sum()` is `None`. The date filter `M j, Y` gives "Sep 28, 2026".
- **Dashboard today** (`src/dashboard/`):
  - View: `DashboardView(LoginRequiredMixin, TemplateView)`, GET/HEAD only. Context: `status_rows`, `total_goals`.
  - Template: `<section class="mt-10" aria-labelledby="…-heading">` with an `<h2 id>` and a table (`thead` with `th scope="col"`; body rows with `th scope="row"` + `td text-right tabular-nums`). The empty-state paragraph is `text-sm text-slate-500`.
  - Tests (`src/dashboard/tests/test_views.py`):
    - Helpers: `LabelledSection(heading_id)`, which gives `.heading()`, `.rows` (header row included) and `.links()`, plus `status_section(client)`, `get_page` and `PASSWORD`.
    - Classes: `DashboardAccessTests`, `DashboardPageTests`, `DashboardStatusCountsTests`, `DashboardEmptyStateTests` and `DashboardQueryCountTests`. The last compares few vs many data (alice with 1 goal, carol with 30) and pins `assertNumQueries(3)`, commented as session, user and the grouped status count.
- **Tests.** There is no freezegun. "Today" is set by `patch("django.utils.timezone.now", return_value=<aware datetime>)`, which `localdate()` uses (example: `learning_sessions/tests/test_views.py:84-89`). Session helpers follow `add_session(goal, tags=(), **fields)`: `LearningSession.objects.create(...)`, then `session.tags.set(Tag.objects.get_or_create_by_name(n)[0] for n in tags)`. The tag-scoping pattern is `learning_sessions/tests/test_models.py` `OwnedByTests` (the `shared` / `alice-only` tags).

## Design decisions
- **Two queryset methods on `LearningSessionQuerySet`**, called as `LearningSession.objects.owned_by(request.user).<method>()`, so scoping keeps its single `owned_by` path and each total can be unit-tested on its own:
  - `minutes_per_tag() -> list[tuple[str | None, int]]` returns `(tag name, minutes)`, largest total first, with ties ordered by `Lower(name)`. Untagged time comes last as `(None, minutes)` and is left out when there is none. It is one query: `.order_by()`, then `values("tags", "tags__name")` + `annotate(Sum)`. The `None` row is moved to the end in Python, because SQL puts NULL first.
  - `minutes_per_week(today, weeks) -> list[tuple[date, int]]` returns `(Monday, minutes)` for exactly `weeks` weeks ending with the week containing `today`, newest first, with 0 for an empty week. It is one query: a date-range filter from the oldest Monday to the current week's Sunday, so later-dated rows are excluded, then `TruncWeek` + `Sum`. The zeros are filled in Python. `today` is a parameter, so the method stays pure and testable. The view passes `timezone.localdate()`.
- **Minutes, not hours.** Both methods return minutes, and the template formats them with `|duration`, as decided at refinement.
- **View.** `get_context_data` adds `tag_rows` and `week_rows`, with `WEEKS_SHOWN = 8` as a module constant in `dashboard/views.py`.
- **Template.**
  - Two new sections after "Goals by status":
    - `aria-labelledby="hours-per-tag-heading"`, with `<h2>` "Hours per tag".
    - `aria-labelledby="hours-per-week-heading"`, with `<h2>` "Hours per week".
  - Each holds a table in the existing style: Tag / Time and Week / Time headers, with "Untagged" for the `None` row and "Week of {{ monday|date:"M j, Y" }}".
  - Under the tag table, the note: "A session with several tags counts under each of them."
  - With no sessions, the tag table and note are replaced by "No sessions logged yet.".
- **Query count.** The pin moves with the step that adds each query: to 4 in step 4 and to 5 in step 6. The suite stays green after every step.

## Steps
- [x] 1. **`minutes_per_tag()` totals per tag.** Fixture:
  - alice: `python` 30 + 45 min; `django` 45 min plus a session tagged both `django` and `python` (60 min); `Zebra` 45 min; `apple` 45 min.
  - bob: `python` 500 min and `bob-only` 10 min.

  `owned_by(alice).minutes_per_tag()` must equal `[("python", 135), ("django", 105), ("apple", 45), ("Zebra", 45)]`: largest first, ties case-insensitive, the multi-tag session counted under both, bob's minutes and his tag never appearing.

  — test: `src/learning_sessions/tests/test_models.py` (`MinutesPerTagTests`) — impl: `src/learning_sessions/models.py` — covers: AC1, AC2, AC3, AC8
- [x] 2. **Untagged time, one query, ordered input.**
  - Alice's untagged sessions (20 + 25 min) come last as `(None, 45)`, after a larger and a smaller tag. The row is left out when there is no untagged time; the step 1 fixture shows that.
  - `owned_by(alice).order_by("-date").minutes_per_tag()` gives the same list, in one query (`assertNumQueries(1)`).

  — test: `src/learning_sessions/tests/test_models.py` (`MinutesPerTagTests`) — impl: `src/learning_sessions/models.py` — covers: AC4, AC11
- [x] 3. **`minutes_per_week(today, weeks)`.** `today = date(2026, 10, 3)` (a Saturday) and `weeks=8`. The result is exactly 8 `(Monday, minutes)` pairs from `date(2026, 9, 28)` back to `date(2026, 8, 10)`, newest first.
  - Fixture:
    - Sunday 2026-09-27 (60 min) counts in the week of Sep 21.
    - Monday 2026-09-28 (30 min) and Saturday 2026-10-03 (15 min) count in the week of Sep 28, giving 45.
    - 2026-08-10 (20 min) is the oldest week.
    - 2026-08-09 (a Sunday before the window, 99 min) is excluded.
    - 2026-10-05 (after the current week, written directly because `full_clean` would refuse it, 99 min) is excluded.
    - Bob has 500 min in the current week.
    - Every other week is 0.
  - Same result with `order_by("-date")` on the input, in one query.

  — test: `src/learning_sessions/tests/test_models.py` (`MinutesPerWeekTests`) — impl: `src/learning_sessions/models.py` — covers: AC5, AC6, AC7, AC8, AC11
- [x] 4. **"Hours per tag" section on the dashboard.**
  - `LabelledSection("hours-per-tag-heading")` shows the heading "Hours per tag".
  - Its rows are `[["Tag", "Time"], ["python", "1 h 30 min"], ["django", "45 min"], ["Untagged", "2 h"]]`.
  - Its text contains "A session with several tags counts under each of them.".
  - Bob's same-name tag and his own tag change nothing.
  - Add a `section(client, heading_id)` helper next to `status_section`.
  - The pin `assertNumQueries(3)` becomes 4 (comment: + per-tag totals).

  — test: `src/dashboard/tests/test_views.py` (`DashboardHoursPerTagTests`, `DashboardQueryCountTests`) — impl: `src/dashboard/views.py` (`tag_rows`), `src/templates/dashboard/dashboard.html` — covers: AC1, AC3, AC4, AC8, AC9
- [ ] 5. **Per-tag empty state.**
  - A user with no sessions (others have some) sees "No sessions logged yet." in the Hours per tag section, with no table rows and no multi-tag note.
  - A user with one session doesn't see that sentence.

  — test: `src/dashboard/tests/test_views.py` (`DashboardHoursPerTagTests`) — impl: `src/templates/dashboard/dashboard.html` — covers: AC10
- [ ] 6. **"Hours per week" section on the dashboard.**
  - With `django.utils.timezone.now` patched to `2026-10-03 12:00 UTC`, `LabelledSection("hours-per-week-heading")` shows the heading "Hours per week".
  - It has a Week / Time header and 8 rows from "Week of Sep 28, 2026" down to "Week of Aug 10, 2026". The fixture weeks show "1 h 15 min" and "2 h", and the others "0 min".
  - A user with no sessions sees all 8 rows at "0 min".
  - The pin moves from 4 to 5 (comment: + per-week totals).

  — test: `src/dashboard/tests/test_views.py` (`DashboardHoursPerWeekTests`, `DashboardQueryCountTests`) — impl: `src/dashboard/views.py` (`WEEKS_SHOWN`, `week_rows`), `src/templates/dashboard/dashboard.html` — covers: AC5, AC6, AC7, AC9, AC10
- [ ] 7. **The query count doesn't grow with sessions or tags.**
  - `DashboardQueryCountTests` setUp gives `few` (alice) 1 session with 1 tag.
  - `many` (carol) gets 40 sessions over 10 weeks and 6 tags, some with several tags and some untagged.
  - The existing equality test then also covers sessions and tags, and the page still takes 5 queries.
  - This is expected to be green on first run (a regression pin); the commit notes it.

  — test: `src/dashboard/tests/test_views.py` (`DashboardQueryCountTests`) — impl: none expected — covers: AC11
- [ ] 8. **Docs.**
  - `CLAUDE.md`:
    - The Dashboard bullet: the two sections, `minutes_per_tag()` / `minutes_per_week()`, `WEEKS_SHOWN`, the Untagged row and the multi-tag note, the empty state, and 5 queries.
    - The Learning sessions bullet: both queryset methods and the grouping rule.
    - Layout: dashboard description.
  - `README.md`: what the dashboard shows.
  - Run the full suite, `ruff check .` and `ruff format --check .`.

  — test: none (docs) — impl: `CLAUDE.md`, `README.md` — covers: docs obligation from ticket notes

## AC coverage
| AC | Steps |
|----|-------|
| AC1 per-tag section and totals | 1, 4 |
| AC2 per-tag order | 1 |
| AC3 multi-tag counted under each, note, no Total | 1, 4 |
| AC4 Untagged row only when present | 2, 4 |
| AC5 8 weeks, newest first, current week | 3, 6 |
| AC6 Monday weeks, "Week of" label | 3, 6 |
| AC7 week sums, 0 weeks, out-of-range excluded | 3, 6 |
| AC8 only own sessions and tags | 1, 3, 4 |
| AC9 `duration` format | 4, 6 |
| AC10 no-sessions state | 5, 6 |
| AC11 ORM aggregation, fixed query count (5) | 2, 3, 4, 6, 7 |
