# Review: goal-status-filter
## Verdict: FAIL

## Acceptance criteria
- AC1 — covered by `GoalStatusFilterTests.test_a_status_filters_the_list` (one subtest per status). Newest-first order is covered by `GoalFilteredPaginationTests.test_pagination_keeps_the_filter`, which asserts the ordered `done` titles. — PASS
- AC2 — covered by `GoalStatusFilterTests.test_a_missing_empty_or_invalid_status_shows_all` — PASS
- AC3 — covered by `GoalStatusFilterTests.test_the_filter_never_shows_other_users_goals` — PASS
- AC4 — covered by `GoalStatusFilterTests.test_filter_links_mark_the_active_filter` — PASS
- AC5 — covered by `GoalFilteredPaginationTests.test_pagination_keeps_the_filter` and `test_filter_links_start_at_page_one` — PASS
- AC6 — covered by `GoalFilterEmptyStateTests.test_an_empty_filter_says_so` and `test_no_goals_at_all_says_no_goals_yet` — PASS
- AC7 — covered by `GoalFilteredPaginationTests.test_query_parameters_are_never_reflected_raw` — PASS
- AC8 — `GoalViewsScopingTests.test_every_goal_lookup_view_scopes_through_own_goals_mixin` passes, but it doesn't prove the AC as written. It asserts `model is None` and the base-class order. It does not assert that `get_queryset` resolves to `OwnGoalsMixin.get_queryset`. — NOT COVERED

Suite: 195 tests OK. `ruff check` and `ruff format --check` are clean, and `makemigrations --check` reports no changes.

## Findings
- [medium] src/goals/tests/test_views.py:736 — Both reviewers raised this. The AC8 guard checks only `model is None` and that `OwnGoalsMixin` comes before Django's `SingleObjectMixin`/`MultipleObjectMixin` in the MRO. A detail, edit or delete view could list the mixin first and still define `get_queryset()` without `super()` (e.g. `return Goal.objects.all()`). That view would pass the test and serve every user's goals. Only the list view has a behavioural scoping test (AC3). The approved AC8 asks that `get_queryset` resolve to `OwnGoalsMixin.get_queryset`. Step 8 dropped that check because the list view overrides `get_queryset`, and recorded it in the plan, but the AC was never amended. Nothing is exploitable today: no view skips `super()`. — Recommendation: plan step 10.
- [low] src/goals/views.py:48 — `has_goals` runs an extra `EXISTS` query on every list render, but only the empty-state branch uses it. — Optional: compute it only when `object_list` is empty. Accepted as is: one cheap query.
- [low] src/goals/tests/test_views.py:625 — `test_a_status_filters_the_list` compares sets, with one goal per status, so ordering within a filtered list isn't asserted there. Ordering doesn't depend on the status, and the pagination test asserts it for `done`. — No change required.

Security review (OWASP, authn/authz, secrets): no high, medium or low findings. The XSS, owner-scoping and status-validation risks were checked and are not issues. The one info item is the AC8 gap above.

## Reviewed
commit e8ab36c, 2026-10-02
