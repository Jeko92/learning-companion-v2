# Review: goal-list-create

## Verdict: PASS

This was a first review, scoped to `971e9e7..ae6ed40`. Neither reviewer found a high or medium issue. The suite passes (164 tests), and `ruff check`, `ruff format --check` and `makemigrations --check` are clean.

## Acceptance criteria
- AC1: covered by `goals.tests.test_views.GoalListTests.test_the_goals_list_is_served` and `GoalCreatePageTests.test_the_create_page_renders_a_goal_form`. PASS
- AC2: covered by `GoalListTests.test_anonymous_visitors_are_sent_to_log_in` and `GoalCreateTests.test_anonymous_visitors_are_sent_to_log_in_and_nothing_is_created` (GET and POST). PASS
- AC3: covered by `goals.tests.test_models.OwnedByTests.test_owned_by_returns_only_that_users_goals_newest_first`. PASS
- AC4: covered by `GoalListTests` (the list is served; only your goals, newest first with status; empty state) and `GoalCreatePageTests.test_the_list_links_to_the_create_page`. PASS
- AC5: covered by `GoalCreatePageTests.test_the_create_page_renders_a_goal_form`. PASS
- AC6: covered by `GoalCreateTests.test_a_valid_create_saves_your_goal_and_returns_to_the_list`. PASS
- AC7: covered by `GoalCreateTests.test_a_posted_owner_is_ignored`. PASS
- AC8: covered by `GoalCreateTests.test_invalid_input_rerenders_the_form_and_creates_nothing`. PASS
- AC9: covered by `GoalCreateCsrfTests` (both tests). PASS
- AC10: covered by `accounts.tests.test_nav.NavTests` (anonymous and logged-in) and `core.tests.test_home.HomePageTests.test_anonymous_nav_has_no_goals_link`. PASS
- AC11: covered by `GoalListTests.test_goal_values_are_shown_escaped`. PASS for the title; see finding 2 on the description.
- AC12: covered by `GoalListPaginationTests` (20 per page, owner-scoped; out-of-range page is 404). PASS

## Findings (none blocking)
1. **[low] (code) `src/templates/goals/goal_list.html`: the pagination links are bare `?page=N`.**
   - **Problem:** they drop other query parameters, so #10's `?status=` filter would reset on Previous/Next.
   - **Later fix:** in #10, build the links from `request.GET` with `page` replaced, and pin it with a test.
2. **[low] (code) `src/goals/tests/test_views.py` `test_goal_values_are_shown_escaped`: the description half of AC11 holds vacuously.**
   - **Problem:** the list doesn't render the description, so the payload there proves nothing.
   - **Later fix:** pin description escaping on the page that first renders it (#9's detail page).
3. **[info] (security) `src/goals/views.py` `OwnGoalsMixin` sets `model = Goal`.**
   - **Problem:** if a #9 view lists the mixin *after* the generic view (`class GoalDetailView(DetailView, OwnGoalsMixin)`), `get_queryset()` silently falls back to `Goal._default_manager.all()`, which is unscoped (IDOR). `LoginRequiredMixin.dispatch` is also skipped.
   - **Recommendation for #9:** drop `model = Goal` from the mixin, so a wrongly ordered view raises `ImproperlyConfigured` instead; `get_queryset()` already supplies the model. Add an "another user's pk is 404" test per view.

## Reviewed
commit ae6ed40, 2026-10-02
