# Review: ai-next-steps
## Verdict: PASS

First review, base `3e74254` (merge-base with `origin/develop`), plan steps 1–12. Full suite green (436 tests), `ruff check` and `ruff format --check` clean, `makemigrations --check` reports no changes. Code reviewer: 0 high, 0 medium, 4 low. Security reviewer: 0 high, 0 medium, 0 low, 1 info.

## Acceptance criteria
- AC1 (POST route, 405 on GET, anonymous to login): covered by `goals.tests.test_views.GoalNextStepsAccessTests` (`test_the_next_steps_route_is_under_the_goal`, `test_a_get_is_not_allowed`, `test_anonymous_visitors_are_sent_to_log_in`). PASS
- AC2 (another user's goal is the same 404 as a missing one): covered by `GoalNextStepsAccessTests.test_another_users_goal_is_the_same_404_as_a_missing_one`. PASS
- AC3 (route in the scoping test): covered by `GoalViewsScopingTests.test_every_goal_lookup_view_scopes_through_own_goals_mixin` (`next_steps` added to the pinned set). PASS
- AC4 (CSRF): covered by `GoalNextStepsCsrfTests` (`test_a_post_without_a_token_is_rejected`, `test_a_post_with_the_forms_token_suggests`). PASS
- AC5 (same data as the summary, 10 sessions, total, 20 resources, nothing else): covered by `goals.tests.test_prompts.NextStepsMessagesTests.test_the_user_message_describes_the_goal_as_the_summary_does` and `GoalNextStepsSuggestTests.test_one_call_without_retries_with_the_recent_sessions_and_resources`. PASS
- AC6 (system prompt: 2 to 3 concrete steps, build on progress, don't repeat resources, JSON `steps` list): covered by `NextStepsMessagesTests.test_the_system_prompt_asks_for_2_to_3_concrete_steps_as_json` and `test_the_schema_asks_for_a_steps_list_of_strings_and_nothing_else`. PASS
- AC7 (an empty goal is still sent, and says so): covered by `GoalNextStepsEmptyGoalTests.test_a_goal_without_sessions_or_resources_still_gets_steps` and the empty case in `NextStepsMessagesTests`. PASS
- AC8 (structured service call, per-call retries, same error rules, no network): covered by `ai.tests.test_services.CompleteJsonTests` (3 tests) and `CompleteJsonErrorTests` (`test_every_sdk_error_is_the_same_safe_error_logged_once_by_type`, `test_a_reply_without_content_is_the_empty_reply_error`), all on `NoNetworkTestCase`. PASS
- AC9 (malformed reply or wrong count is an AIServiceError, nothing stored, steps trimmed): covered by `CompleteJsonErrorTests.test_a_reply_that_is_not_a_json_object_is_an_unexpected_reply`, `goals.tests.test_prompts.ParseNextStepsTests` (2 tests) and `GoalNextStepsErrorTests.test_a_reply_with_the_wrong_number_of_steps_keeps_the_last_ones`. PASS
- AC10 (stored in order with time, replaces earlier steps, "Next steps suggested."): covered by `GoalNextStepsSuggestTests.test_the_steps_are_stored_trimmed_in_order_with_their_time` and `test_new_steps_replace_the_last_ones`. PASS
- AC11 (Next steps section, `<ol>`, escaped, time, button labels, POST form with CSRF): covered by `GoalDetailNextStepsTests` (4 tests). PASS
- AC12 (`updated_at` unchanged; not in the goal form): covered by `GoalNextStepsSuggestTests.test_suggesting_does_not_change_the_goals_updated_time`, `GoalEditTests.test_editing_keeps_the_next_steps_and_the_form_cannot_set_them` and `goals.tests.test_models.GoalNextStepsFieldTests`. PASS
- AC13 (query count 7): covered by `GoalDetailQueryCountTests.test_the_goal_page_takes_a_fixed_number_of_queries` (steps stored on the measured goal). PASS
- AC14 (errors shown, steps kept, never a 500, chained cause not shown): covered by `GoalNextStepsErrorTests.test_an_ai_failure_goes_back_to_the_goal_with_its_message` (all three service messages). PASS
- AC15 (no retries): covered by `GoalNextStepsSuggestTests.test_one_call_without_retries_with_the_recent_sessions_and_resources` (`max_retries=0` in the exact-call assertion). PASS
- AC16 (docs): `CLAUDE.md` (Goals and OpenAI bullets, Layout) and `README.md` (Setup paragraph, Layout) updated in `6c5c801`; checked by reading. PASS

## Findings
None of these block the release (all low or info). They are recorded here as possible follow-ups, not fixed in review.
- [low] `src/goals/prompts.py` `parse_next_steps`: assumes `reply` is a dict, which `complete_json` guarantees. A non-dict from another caller would raise `AttributeError` rather than `AIServiceError`. Recommendation: treat a non-dict like a missing `steps`, or state the precondition in the docstring.
- [low] `src/templates/goals/goal_detail.html` Next steps section: steps stored without `next_steps_generated_at` (possible through the admin) would render "Suggested" with no time. The Summary section has the same shape. Recommendation: guard the time paragraph with `{% if goal.next_steps_generated_at %}`, in both sections.
- [low] `src/goals/tests/test_views.py`: the summary view's switch from two `exists()` checks to the shared `prompt_data()` lists is covered only by the existing summary tests (empty-goal and one-session-or-resource). This is equivalent behaviour, so no action needed.
- [low] `src/ai/tests/test_services.py`: no test asserts explicitly that `complete()` sends no `response_format`. The existing exact-call test for `complete()` already pins its kwargs, so no action needed.
- [info] `src/ai/services.py` `complete_json`: only `ValueError` is caught around `json.loads`. Pathologically deep nesting would raise `RecursionError` and become a 500. Strict Structured Outputs with `NEXT_STEPS_SCHEMA` rules this out, and no SDK error is chained, so no key can leak. Optional hardening: `except (ValueError, RecursionError)`.

## Reviewed
commit e9f837a, 2026-10-03
