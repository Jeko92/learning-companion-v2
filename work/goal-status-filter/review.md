# Review: goal-status-filter
## Verdict: PASS

Re-review after the FAIL of 2026-10-02. The scope was only fix step 10 (`5f1da7d..5c25a76`).

## Acceptance criteria
- AC1 — covered by `GoalStatusFilterTests.test_a_status_filters_the_list` (one subtest per status). Newest-first order is covered by `GoalFilteredPaginationTests.test_pagination_keeps_the_filter`, which asserts the ordered `done` titles. — PASS
- AC2 — covered by `GoalStatusFilterTests.test_a_missing_empty_or_invalid_status_shows_all` — PASS
- AC3 — covered by `GoalStatusFilterTests.test_the_filter_never_shows_other_users_goals` — PASS
- AC4 — covered by `GoalStatusFilterTests.test_filter_links_mark_the_active_filter` — PASS
- AC5 — covered by `GoalFilteredPaginationTests.test_pagination_keeps_the_filter` and `test_filter_links_start_at_page_one` — PASS
- AC6 — covered by `GoalFilterEmptyStateTests.test_an_empty_filter_says_so` and `test_no_goals_at_all_says_no_goals_yet` — PASS
- AC7 — covered by `GoalFilteredPaginationTests.test_query_parameters_are_never_reflected_raw` — PASS
- AC8 — covered by `GoalViewsScopingTests.test_every_goal_lookup_view_scopes_through_own_goals_mixin`. For each of list, detail, edit and delete, it checks:
  - the view sets no `model`
  - `OwnGoalsMixin` comes first in the MRO
  - `get_queryset is OwnGoalsMixin.get_queryset` for views without their own override
  - behaviourally, as alice, `get_queryset()` contains her goal and not bob's

  — PASS

Suite: 195 tests OK. `ruff check` and `ruff format --check` are clean, and `makemigrations --check` reports no changes.

## Findings
Previous findings:
- [medium] src/goals/tests/test_views.py — AC8 guard didn't prove `get_queryset` resolves to the mixin — **resolved** by step 10. Both reviewers confirmed it. Mutations went red each time:
  - the plan's: `GoalDetailView.get_queryset` returning `Goal.objects.all()`
  - the code reviewer's: the list view's `get_queryset` starting from `Goal.objects.all()`
  - the code reviewer's: `GoalUpdateView.get_queryset` returning `Goal.objects.all()`
- [low] src/goals/views.py:48 — extra `has_goals` `EXISTS` query per list render — accepted as is.
- [low] src/goals/tests/test_views.py:625 — filter test compares sets; ordering is covered by the pagination test — no change.

New findings: none (code review 0/0/0, security review 0/0/0/0).

The security reviewer noted two guard limits, neither a vulnerability nor within AC8. They're recorded for later work:
- a view overriding `get_object()` instead of `get_queryset()` would get past the guard
- the behavioural list check runs without `?status=`; the filtered case is covered by the AC3 test

## Reviewed
commit 5c25a76, 2026-10-02
