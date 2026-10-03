# Review: resource-attach
## Verdict: FAIL

AC18 is delivered wrong: the goal delete confirmation shows the resource warning twice, and its tests pass anyway because they only check that the text is present. A criterion whose test passes on a broken page isn't proven, so this goes back to implementation.

## Acceptance criteria
- AC1 — `ResourceCreateAccessTests.test_anonymous_visitors_are_sent_to_log_in`, `ResourceDeleteAccessTests.test_anonymous_visitors_are_sent_to_log_in` — PASS
- AC2 — `ResourceCreateAccessTests.test_another_users_goal_is_the_same_404_as_a_missing_one` — PASS
- AC3 — `ResourceDeleteAccessTests.test_another_users_resource_is_the_same_404_as_a_missing_one` — PASS
- AC4 — `ResourceViewsScopingTests.test_every_resource_view_scopes_through_the_own_resources_mixins` — PASS
- AC5 — `GoalDetailResourcesTests.test_resources_are_grouped_by_type_in_a_fixed_order`, `ResourceGroupedByTypeTests` — PASS
- AC6 — `GoalDetailResourcesTests.test_each_resource_links_to_its_url_in_a_new_tab_and_can_be_deleted`, `test_resources_of_other_goals_never_appear` — PASS
- AC7 — `GoalDetailResourcesTests.test_a_goal_without_resources_says_so_and_offers_the_form` — PASS
- AC8 — `GoalDetailResourcesTests.test_the_attach_form_posts_to_the_create_route` — PASS
- AC9 — `GoalDetailQueryCountTests` (pin 7, large vs small), `ResourceGroupedByTypeTests.test_it_runs_one_query_and_follows_the_queryset` — PASS
- AC10 — `ResourceCreatePageTests.test_the_form_posts_to_itself_with_the_allowed_fields_only`, `ResourceCreateTests.test_a_posted_goal_or_timestamps_are_ignored` — PASS
- AC11 — `ResourceCreateTests.test_a_valid_post_attaches_the_resource_to_the_goal` — PASS
- AC12 — `ResourceCreatePageTests` (GET page, Cancel), `ResourceCreateValidationTests.test_an_invalid_post_keeps_the_entered_values` — PASS
- AC13 — `ResourceCreateValidationTests.test_invalid_input_is_rejected_and_nothing_is_saved`, `test_a_url_with_another_scheme_gets_exactly_one_error` — PASS
- AC14 — `ResourceCreateValidationTests.test_boundary_values_are_accepted` — PASS
- AC15 — `ResourceFormDuplicateTests`, `ResourceCreateDuplicateTests`, `ResourceCreateRaceTests` — PASS
- AC16 — `ResourceDeleteTests.test_a_get_asks_for_confirmation_and_deletes_nothing` — PASS
- AC17 — `ResourceDeleteTests.test_a_post_deletes_the_resource_only` — PASS
- AC18 — `GoalDeleteResourceWarningTests` — **FAIL**: the tests pass, but the warning renders twice (`goal_confirm_delete.html:9-14`); the tests use `assertIn` and can't see it
- AC19 — `ResourceCreateCsrfTests`, `ResourceDeleteCsrfTests` — PASS
- AC20 — `ResourceCreatePageTests.test_the_goal_title_is_escaped`, `ResourceCreateValidationTests.test_an_entered_title_is_escaped_when_the_form_comes_back`, `ResourceDeleteTests.test_the_title_url_and_goal_title_are_escaped`, `GoalDetailResourcesTests.test_resource_title_and_url_are_escaped` — PASS
- AC21 — `CLAUDE.md` Resources and Layout bullets updated (docs, no test) — PASS

Full suite (356 tests) green, ruff check and format clean, `makemigrations --check` reports no changes.

## Findings
- [medium] src/templates/goals/goal_confirm_delete.html:9-14 — the `{% if resource_count %}` warning block is in the template twice, so "Its N resources will be deleted too." shows twice on the goal delete page (found by both reviewers). — Remove the second block; make `GoalDeleteResourceWarningTests` assert the warning appears exactly once.
- [low] src/goals/tests/test_views.py:70 — `GoalDetailResourcesTests.resources_text()` splits the page text on the first "Resources", which breaks if the word appears earlier (a goal title, session notes). — Scope the checks to the Resources `<section>` itself (e.g. an `id`/`aria-labelledby` on it) instead of splitting on a word.
- [low, no change] src/resources/tests/test_models.py:413 — the reviewer called `assertTrue(hasattr(ResourceQuerySet, "grouped_by_type"))` in `setUp` a red-phase scaffold. It's the file's deliberate convention (`ResourceGoalTests`, `ResourceOwnedByTests`: "Asserted first, so a missing model fails cleanly"), so it stays.
- [low, no change] The inline attach form's invalid submissions re-render the standalone create page; that's the planned design (plan, design decisions).
- Security review: no findings. IDOR on attach and delete, link injection (form validator, model validator, DB constraint, autoescaped `href` with `rel="noopener noreferrer"`), CSRF, duplicate-error leakage and redirects all checked.

## Reviewed
commit e030b7e, 2026-10-03 (base 1b7373d)
