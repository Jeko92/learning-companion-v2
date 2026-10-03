# Review: dashboard-status
## Verdict: FAIL

Both findings are low severity, but the verdict is FAIL on purpose. The first one puts wrong guidance into `CLAUDE.md`, which every later ticket reads as authoritative. #19 dashboard-hours does more grouped aggregation and would inherit the mistake. The two fixes are small (steps 13 and 14 in `plan.md`).

## Acceptance criteria
- AC1: anonymous user redirected to log in. Covered by `dashboard.tests.test_views.DashboardAccessTests.test_anonymous_visitors_are_sent_to_log_in`. PASS
- AC2: page, title, `<h1>`, table and Total. Covered by `DashboardPageTests.test_the_dashboard_is_served_with_its_title_and_heading` and `DashboardStatusCountsTests.test_lists_your_goal_count_per_status_in_order_then_the_total`. PASS
- AC3: statuses with no goals listed with 0. Covered by `DashboardStatusCountsTests.test_statuses_without_goals_are_listed_with_zero` and `goals.tests.test_models.GoalStatusCountsTests` (both tests). PASS
- AC4: one grouped query and a fixed query count. Covered by `GoalStatusCountsTests.test_a_user_without_goals_gets_zero_for_every_status_in_one_query`, `DashboardQueryCountTests` (both tests: same count for 1 and 30 goals, `assertNumQueries(3)`). PASS. Finding 1 says the test never exercises `.order_by()`.
- AC5: only the user's own goals are counted. Covered by `DashboardStatusCountsTests` (bob has goals in every status) and `GoalStatusCountsTests.test_counts_every_status_in_choice_order_with_zeros`. PASS
- AC6: rows link to the filtered goal list. Covered by `DashboardStatusCountsTests.test_each_row_links_to_the_goal_list_filtered_by_its_status`. PASS
- AC7: empty-state link. Covered by `DashboardEmptyStateTests` (both tests). PASS
- AC8: nav link. Covered by `accounts.tests.test_nav.NavTests.test_logged_in_nav_links_dashboard_goals_the_profile_and_has_logout` and `test_anonymous_nav_has_only_login_and_signup_links`. PASS
- AC9: log-in redirect and `next`. Covered by `accounts.tests.test_login`: `LoginSubmitTests` (both tests), `LoginNextTests.test_safe_next_is_carried_in_the_form_and_followed`, `test_unsafe_next_is_never_followed` and `test_unsafe_next_is_dropped_from_the_form_a_browser_submits`. PASS
- AC10: sign-up redirect and already-authenticated visitors. Covered by `accounts.tests.test_signup`: `test_valid_signup_logs_the_user_in_and_redirects`, `test_the_dashboard_welcomes_the_new_user_after_signup` and `SignUpLoggedInTests`. Also covered by `accounts.tests.test_login.LoginLoggedInTests` (all three tests). PASS
- AC11: log-out and home page unchanged. Covered by `accounts.tests.test_logout.LogoutTests.test_post_logs_out_and_redirects_with_a_message`, `test_landing_page_says_the_user_logged_out` and `core.tests.test_home.HomePageTests.test_logged_in_visitors_get_the_same_home_page_not_a_redirect`. PASS
- AC12: GET only, POST returns 405. Covered by `DashboardAccessTests.test_a_post_is_not_allowed`. PASS

Suite: 450 tests, OK. `ruff check` and `ruff format --check` are clean. `makemigrations --check` reports no changes.

## Findings
- [low] `src/goals/models.py:20`, `src/goals/tests/test_models.py:167`, `CLAUDE.md` (Goals bullet): the claim that the default ordering splits the groups is wrong. Since Django 3.1, `Meta.ordering` isn't added to GROUP BY queries. Only an explicit `order_by(...)` on the queryset is. I checked the SQL: plain gives `GROUP BY 1`, `order_by("-created_at")` gives `GROUP BY 1, created_at`, and adding `.order_by()` brings it back to `GROUP BY 1`. The code reviewer removed `.order_by()` and `GoalStatusCountsTests` still passed. **Recommendation:** add a test that chains an explicit `.order_by("-created_at")` before `status_counts()` so the `.order_by()` call is exercised, and correct the comments and the `CLAUDE.md` sentence. (Plan step 13.)
- [low] `src/dashboard/tests/test_views.py:62`: `LabelledSection.handle_endtag` ends heading capture on any end tag starting with `h`, which includes `</header>`, `</head>` and `</hr>`. That's harmless with today's template but fragile. **Recommendation:** match only `h1` to `h6`. (Plan step 14.)

Security review: no findings. Scoping is through `owned_by`. `LOGIN_REDIRECT_URL` is always resolved through `resolve_url` or `redirect`. The `next` check is still Django's same-site check. There is no redirect loop. Template values come from fixed choices and are escaped.

The code reviewer also found these sound:
- The `LabelledSection` parser can't pass vacuously.
- The literal `/dashboard/` auth tests lost no coverage.
- `{% if not total_goals %}` is correct.

## Reviewed
commit 5cc67e8, 2026-10-03
