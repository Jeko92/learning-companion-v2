# Dashboard: pin the week test's today far from the real date
Issue: #66 · Branch: fix/dashboard-week-test-date

## Story
As a developer, I want the dashboard's per-week page tests to pin "today" to a date far from the real one, so that they prove the view takes "today" from `timezone.localdate()` (the patched `django.utils.timezone.now`) on whatever day the suite runs, instead of passing by coincidence while the real date sits in the pinned week.

## Acceptance criteria
- [x] AC1 The `NOW` constant in `src/dashboard/tests/test_views.py` is a Saturday in 2030, Sat Mar 16, 2030 12:00 UTC (the 8 weeks shown start on Mondays Mar 11 back to Jan 21, 2030).
- [x] AC2 `DashboardHoursPerWeekTests.test_lists_the_last_eight_weeks_newest_first` uses fixture dates inside the new window and expects the eight "Week of ..." labels for Mar 11, 2030 back to Jan 21, 2030, newest first, with the same shape as before: two sessions in the newest week (1 h 15 min), one two weeks earlier (2 h), the other weeks at "0 min". Bob's session moves into the window too, so scoping is still checked.
- [x] AC3 `DashboardBarTests` (which shares `NOW`) uses fixture dates inside the new window, and its expected bar values are unchanged (tag bars 90/30/45 of 90; week bars 120, 45, then six 0 of 120; all-zero table `("0", "1")` x 8).
- [x] AC4 A guard test fails if the 8-week window ending with the pinned week (`NOW`'s Monday minus 7 weeks through that week's Sunday) contains the real `date.today()`, so the pin can't silently become non-discriminating again.
- [x] AC5 The `minutes_per_week` code in `src/learning_sessions/models.py` says that the date-range filter only limits the rows scanned, because the zero-fill reads only the shown Mondays. Comment-only change, no behaviour change.
- [x] AC6 The full suite and `ruff check` / `ruff format --check` stay green.

## Out of scope
- Any change to what the dashboard shows or how it computes it.
- Other test modules that patch or depend on the date.
- The `add_session` helper's default `day` (used only by tests that don't depend on "today").

## Notes
- Acceptance criteria approved by the user on 2026-10-04.
- Interview answers (2026-10-04): the pin is a Saturday in 2030 (user's choice over a 2024 date); both `DashboardHoursPerWeekTests` and `DashboardBarTests` move with the shared `NOW`; both optional extras are in scope (the `minutes_per_week` comment, from review finding 2 of `work/dashboard-hours/review.md`, and the guard test).
- Future fixture dates are fine: `add_session` uses `LearningSession.objects.create()`, which skips `full_clean()` and so `reject_future_dates`. The guard test (AC4) will start failing in early 2030, when the real date reaches the pinned window; that is intended, it says the pin needs moving.
- Today (Sun Oct 4, 2026) is in the same week as the old pin (Sat Oct 3, 2026), so the current tests can't tell a patched today from the real one.
- Labelled `type:fix`, hence the `fix/` branch. Depends on #19 (done).
