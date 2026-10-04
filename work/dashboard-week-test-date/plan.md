# Plan: dashboard-week-test-date

## Research summary
Done inline rather than with sub-agents: the ticket touches one test module and one comment, all of which were read during refinement.

- `src/dashboard/tests/test_views.py` holds `NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)  # a Saturday`, shared by two classes patched with `@patch("django.utils.timezone.now", return_value=NOW)`:
  - `DashboardHoursPerWeekTests`: `setUp` adds bob's 500 min session on 2026-10-01 (scoping check). `test_lists_the_last_eight_weeks_newest_first` adds alice's 45 min (Sep 29), 30 min (Oct 1) and 120 min (Sep 15) and expects the eight "Week of Sep 28, 2026" … "Week of Aug 10, 2026" rows. `test_without_sessions_every_week_shows_zero` is date-agnostic.
  - `DashboardBarTests`: sessions on Oct 1 (90, tag Django), Oct 1 (30, tag ORM), Sep 22 (45, untagged) for the tag bars; Oct 1 (90), Sep 29 (30), Sep 22 (45) for the week bars (120 newest week, 45 the week before). The all-zero test is date-agnostic.
- `add_session(user, minutes, tags=(), day=date(2026, 9, 1))` uses `LearningSession.objects.create()`, so `reject_future_dates` (a `full_clean()` validator) doesn't run and 2030 dates are fine.
- `TIME_ZONE = "UTC"`, `USE_TZ = True`: `timezone.localdate()` under the patch is `NOW.date()`.
- The view (`dashboard/views.py:27`) calls `minutes_per_week(timezone.localdate(), weeks=WEEKS_SHOWN)` (`WEEKS_SHOWN = 8`).
- `LearningSessionQuerySet.minutes_per_week` (`src/learning_sessions/models.py:49`) filters `date__gte=mondays[-1], date__lt=newest + 1 week`, groups by `TruncWeek`, then fills `[(monday, found.get(monday, 0)) for monday in mondays]`, so the filter only limits the rows scanned.
- Run one module: `./.venv/bin/python src/manage.py test dashboard.tests.test_views --verbosity 2`; full suite `./.venv/bin/python src/manage.py test src`.

New pin: Sat Mar 16, 2030 12:00 UTC. Its week starts Mon Mar 11, 2030; the eight Mondays shown are Mar 11, Mar 4, Feb 25, Feb 18, Feb 11, Feb 4, Jan 28, Jan 21 (2030).

## Design decisions
- Keep one shared `NOW` (the user's choice: both classes move). Fixture dates keep the same offsets from `NOW` as before, so the expected minutes and bar values don't change:
  - Oct 1 (Thu, current week) → Mar 14, 2030 (Thu); Sep 29 (Tue, current week) → Mar 12, 2030 (Tue); Sep 22 (Tue, previous week) → Mar 5, 2030 (Tue); Sep 15 (Tue, two weeks back) → Feb 26, 2030 (Tue).
- The guard test (AC4) lives in its own small class without the `timezone.now` patch, next to `NOW`, and compares the real date, `datetime.now(UTC).date()` (ruff's DTZ011 rejects `date.today()`; `TIME_ZONE` is UTC and the patch never touches `datetime.now`), with the window computed from `NOW.date()`: from its Monday minus 7 weeks through its Sunday. Its failure message says to move `NOW` and the fixture dates.
- The guard test is written first: with today's real date (Oct 4, 2026) inside the current pin's window it is red for the right reason, and moving `NOW` plus the fixtures makes it green. That gives the ticket a genuine red-green cycle.
- Before committing step 1, a throwaway mutation check (not committed, `src/` reverted afterwards): make the view use `date.today()` instead of `timezone.localdate()` and confirm the per-week and week-bar tests fail. This is the property the ticket is about.
- Found during step 1 (user's decision, 2026-10-04): a class-level `@patch` only wraps `test_*` methods, so `setUp`'s `force_login` ran at the real date and its session (2-week age) had expired by 2030: every request landed on log-in. Both classes now start the patch in `setUp` with `self.enterContext(patch("django.utils.timezone.now", return_value=NOW))` before creating users and logging in, so users, session and requests share the pinned date; the test methods lose their `_now` argument.
- AC5 is a comment-only refactor on green, its own step and `refactor(...)` commit. CLAUDE.md's dashboard line ("page tests fix 'today' by patching `django.utils.timezone.now`") gains a few words about the guard in the same step.

## Steps
- [x] 1. A guard test fails while the real date lies in the pinned 8-week window; `NOW` moves to Sat Mar 16, 2030 12:00 UTC and the fixture dates and "Week of …" labels of `DashboardHoursPerWeekTests` (bob's session included) and `DashboardBarTests` move with it, expected values unchanged; both classes start the `timezone.now` patch in `setUp` (before `force_login`) instead of a class decorator — test: `src/dashboard/tests/test_views.py` (new guard class, red first) — impl: `src/dashboard/tests/test_views.py` (`NOW`, fixture dates, expected labels); mutation check as above, then revert — covers: AC1, AC2, AC3, AC4
- [x] 2. The `minutes_per_week` comment says the date-range filter only limits the rows scanned, because the zero-fill reads only the shown Mondays (no behaviour change, suite stays green); CLAUDE.md mentions the guard test — test: none (refactor on green, full suite + `ruff check .` + `ruff format --check .`) — impl: `src/learning_sessions/models.py`, `CLAUDE.md` — covers: AC5, AC6

## Coverage
- AC1 → step 1
- AC2 → step 1
- AC3 → step 1
- AC4 → step 1
- AC5 → step 2
- AC6 → steps 1 and 2 (full suite and lint before each commit)
