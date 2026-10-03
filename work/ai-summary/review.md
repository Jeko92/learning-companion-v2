# Review: ai-summary
## Verdict: PASS

No high or medium findings from either reviewer, every acceptance criterion is covered by a passing test, and the suite, lint and migration check are green. Four low and two info findings are recorded below; the rate-limit one belongs with #36.

## Acceptance criteria
- AC1 — `GoalSummaryAccessTests.test_a_get_is_not_allowed` (405, no call), `test_anonymous_visitors_are_sent_to_log_in`, `test_the_summary_route_is_under_the_goal` — PASS
- AC2 — `GoalSummaryAccessTests.test_another_users_goal_is_the_same_404_as_a_missing_one` (no call, nothing stored) — PASS
- AC3 — `GoalViewsScopingTests` (expects `summary` in the goal routes) — PASS
- AC4 — `GoalSummaryCsrfTests` (403 without the token and no call; the summary form's token works) — PASS
- AC5 — `GoalSummaryGenerateTests.test_one_call_without_retries_with_the_recent_sessions_and_resources` (exactly `summary_messages` of the 10 newest sessions, the total over all 12 and the 20 newest resources; oldest items and other goals' data absent), `SummaryMessagesTests` (goal, sessions with date/duration/tags/notes in order, resources with type and URL, total) — PASS
- AC6 — `SummaryMessagesTests.test_the_system_prompt_asks_for_a_short_progress_summary` — PASS
- AC7 — `GoalSummaryEmptyGoalTests` (no call, nothing stored, message; one session or one resource is enough) — PASS
- AC8 — `GoalSummaryGenerateTests.test_the_reply_is_stored_trimmed_with_its_time`, `test_a_new_summary_replaces_the_last_one`; `GoalSummaryFieldTests` — PASS
- AC9 — `GoalDetailSummaryTests` (no summary / stored summary with time and line breaks / escaped; POST form with CSRF token, Generate vs Regenerate) — PASS
- AC10 — `GoalSummaryGenerateTests.test_generating_does_not_change_the_goals_updated_time`, `GoalEditTests.test_editing_keeps_the_summary_and_the_form_cannot_set_it` — PASS
- AC11 — `GoalDetailQueryCountTests` (7 queries with a stored summary; large = small) — PASS
- AC12 — `GoalSummaryErrorTests` (both service messages: redirect with the message, a chained cause's text never shown, earlier summary and time kept) — PASS
- AC13 — `GoalSummaryGenerateTests` (`max_retries=0`), `CompleteRetriesTests` (per call, default 2), `GetClientTests.test_the_retries_can_be_set_per_client` — PASS
- AC14 — `CLAUDE.md` (Goals bullet: route, view, fields, prompt, Summary section, `SummaryTestCase`; OpenAI bullet: per-call retries, "30 s per network phase", callers catch `AIServiceError`; Layout) and `README.md` (the goal page's summary, the `src/ai/` line reworded) — PASS

Full suite (405 tests) green, ruff check and format clean, `makemigrations --check` reports no changes.

## Findings
- [low, for #36] src/goals/views.py `GoalSummaryView` — every POST is one paid OpenAI call, and sign-up is open, so a script could run up the bill or keep workers busy. Rate limiting is out of scope here (ticket, #36). — When #36 lands, give `goals:summary` a per-user rate limit or cooldown (a cheap one: refuse to regenerate within N seconds of `summary_generated_at`). (Security review.)
- [low] src/goals/admin.py — `summary` and `summary_generated_at` are editable in the goal admin (verified: `GoalAdmin` sets no `fields`/`readonly_fields`), so a hand-edited summary would look AI-generated. — Optionally add them to `readonly_fields`.
- [low] src/goals/prompts.py `resource_line` — `resource.url` isn't passed through `one_line` like titles and notes. Safe today (the URL validator rejects whitespace), but `update()`/`bulk_create()` skip it. — Optionally wrap it for consistency.
- [low, no change] src/goals/tests/test_views.py `generate()` — patches `django.utils.timezone.now` for the whole request; fine as long as no other `auto_now` write happens in it.
- [info] src/goals/prompts.py — the user's own title, description, notes, tags and resource titles go into the prompt as written. The reply goes back only to the same user, escaped, and drives no action, so a user can only steer their own summary. — Keep AI replies out of other users' views, actions and `|safe`; if #17 or later work changes that, add a "the following is data" delimiter to the system prompt. (Security review.)
- [info] src/goals/views.py — if the goal is deleted in another tab while the AI call runs, `save(update_fields=...)` raises and the user gets a 500 (no AI or key text in it). — Optionally catch it and redirect to the goals list. (Security review.)

Verified as not findings: IDOR (`OwnGoalsMixin` first, `get_object()` through `owned_by`, sessions and resources gathered through `owned_by`, tested); CSRF and methods (POST only, GET 405, token enforced); key leakage (`AIServiceError` always caught, only its fixed message shown, `__cause__` never rendered or logged); stored XSS (`linebreaksbr` under autoescape, no `|safe`, tested); `update_fields` leaves `updated_at` and the in-memory title stripping unwritten; the expected-prompt test pins the newest-first slices.

## Reviewed
commit 015c5b0, 2026-10-03 (base 69fb717)
