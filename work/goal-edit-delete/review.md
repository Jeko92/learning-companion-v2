# Review: goal-edit-delete

## Verdict: PASS

This was a first review, scoped to `f529a11..e6b80e7`.
- Neither reviewer found a high, medium or low issue. The security reviewer reported one info item.
- The suite passes (185 tests), and `ruff check`, `ruff format --check` and `makemigrations --check` are clean.

## Acceptance criteria
- AC1: covered by `GoalDetailTests.test_the_detail_page_is_served`, `GoalEditTests.test_the_edit_page_renders_your_goal_in_a_form` and `GoalDeleteTests.test_delete_asks_for_confirmation_and_a_get_deletes_nothing`. PASS
- AC2: covered by `GoalDetailTests.test_anonymous_visitors_are_sent_to_log_in` and `GoalEditDeleteAccessTests.test_anonymous_visitors_are_sent_to_log_in` (edit and delete, GET and POST). PASS
- AC3: covered by `GoalDetailTests.test_another_users_goal_is_not_found_like_a_missing_one` and `GoalEditDeleteAccessTests.test_another_user_gets_the_same_404_as_for_a_missing_goal`. PASS
- AC4: covered by `GoalDetailTests` (served, shows the goal, placeholder), `GoalEditTests.test_the_detail_page_links_to_the_edit_page` and `GoalDeleteTests.test_the_detail_page_links_to_delete`. PASS
- AC5: covered by `GoalListTests.test_each_title_links_to_its_goal`. PASS
- AC6: covered by `GoalEditTests.test_the_edit_page_renders_your_goal_in_a_form`. PASS
- AC7: covered by `GoalEditTests.test_a_valid_edit_saves_and_returns_to_the_goal`. PASS
- AC8: covered by `GoalEditTests.test_an_invalid_edit_rerenders_the_form_and_changes_nothing`. PASS
- AC9: covered by `GoalDeleteTests.test_delete_asks_for_confirmation_and_a_get_deletes_nothing`. PASS
- AC10: covered by `GoalDeleteTests.test_confirming_deletes_the_goal`. PASS
- AC11: covered by `GoalCreateTests.test_a_valid_create_saves_your_goal_and_opens_it`. PASS
- AC12: covered by `GoalEditDeleteCsrfTests` (both tests). PASS
- AC13: covered by `GoalPagesEscapingTests.test_goal_values_are_escaped_on_every_goal_page`. PASS
- AC14: covered by `OwnGoalsMixinOrderTests.test_a_wrongly_ordered_mixin_fails_loudly`. PASS; see the correction in the notes below.
- AC15: covered by `GoalUrlTests.test_a_goal_knows_its_detail_url`, `GoalAdminTests.test_the_change_page_links_to_the_goal_on_the_site`, `GoalListTests.test_each_title_links_to_its_goal` and `GoalCreateTests.test_a_valid_create_saves_your_goal_and_opens_it`. PASS

## Findings (none blocking)
1. **[info] (security) `src/goals/views.py` `OwnGoalsMixin`: the remaining ordering risk is guarded only by docs.**
   - **Problem:** a future goal view that sets `model = Goal` on itself and lists the mixin second would serve every user's goals with no error, and no test would catch it.
   - **Recommendation:** add a test that walks every goal view in `goals.urls`, and asserts each sets no `model` and resolves `get_queryset` to `OwnGoalsMixin.get_queryset`. It's worth adding when the next goal view arrives (#10's filter touches the list view).

## Reviewer note corrected
- The code reviewer stated that `test_a_wrongly_ordered_mixin_fails_loudly` "would fail if `model = Goal` returned to the mixin". **That is incorrect.**
  - During implementation (plan step 15), a diagnosis with `model = Goal` restored on the mixin showed that the wrongly ordered view *still* raises `ImproperlyConfigured`. Django's `SingleObjectMixin.model = None` precedes the mixin in the MRO.
  - So the test pins Django's loud failure, not the removal of `model`. The real remaining risk is the security info above.

## Reviewed
commit e6b80e7, 2026-10-02
