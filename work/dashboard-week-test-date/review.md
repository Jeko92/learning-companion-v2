# Review: dashboard-week-test-date
## Verdict: PASS
## Acceptance criteria
- AC1 — covered by `DashboardHoursPerWeekTests.test_lists_the_last_eight_weeks_newest_first` (labels from Mar 11, 2030) and `PinnedTodayTests` (window computed from `NOW`) — PASS
- AC2 — covered by `DashboardHoursPerWeekTests.test_lists_the_last_eight_weeks_newest_first` (fixtures in the 2030 window, bob's 500 min in the newest week not counted) and `test_without_sessions_every_week_shows_zero` — PASS
- AC3 — covered by `DashboardBarTests.test_tag_bars_follow_the_rows_and_scale_to_the_largest`, `test_week_bars_follow_the_rows_and_scale_to_the_largest`, `test_an_all_zero_week_table_still_has_bars` (expected values unchanged) — PASS
- AC4 — covered by `PinnedTodayTests.test_the_real_date_is_outside_the_weeks_shown_around_now` (red against the old pin, green against the new one) — PASS
- AC5 — comment-only, no test by design; checked by the code reviewer against `minutes_per_week` (`src/learning_sessions/models.py:56-57`) — PASS
- AC6 — full suite (663 tests) OK, `ruff check .` and `ruff format --check .` clean, `makemigrations --check --dry-run` no changes — PASS

Mutation check (step 1): with the view reading `date.today()` instead of `timezone.localdate()`, the per-week and week-bar tests fail; reverted.

## Findings
- None. Code review: 0 high, 0 medium, 0 low (pinned dates, fixture offsets, guard window, `enterContext` placement and cleanup, comment and CLAUDE.md wording confirmed). Security review: 0 findings (per-user scoping still exercised by bob's session in the newest week; no production change, no secrets).

## Reviewed
commit abaa671, 2026-10-04
