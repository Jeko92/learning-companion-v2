# Plan: ai-next-steps

## Research summary
- **AI service** (`src/ai/services.py`): `get_client(max_retries)` is the only place an `OpenAI` client is built. `complete(system, user, *, max_retries=MAX_RETRIES)` makes one `chat.completions.create(model=settings.OPENAI_MODEL, messages=[system, user])` call. Every `OpenAIError` is logged as `logger.error("OpenAI request failed: %s", type(error).__name__)` and re-raised as `AIServiceError("The AI service is unavailable right now. Please try again later.") from error`. An empty reply (no choices, `content` None or blank) is logged and raised as `AIServiceError("The AI service returned an empty reply.")`. There is no `response_format` support yet.
- **SDK** openai 3.24.0 (`requirements.txt`: `>=3.24,<3.25`). `create()` accepts a plain-dict `response_format={"type": "json_schema", "json_schema": {"name", "schema", "strict"}}`; pydantic classes are only for `parse()`. The message has `content` and `refusal`; a refusal leaves `content` None. Whether strict mode supports `minItems`/`maxItems` is not confirmed in the installed SDK.
- **Service tests** (`src/ai/tests/test_services.py`):
  - `NoNetworkTestCase` makes `ai.services.OpenAI` raise.
  - `FakeClient(reply=, error=)` records `create(**kwargs)` in `.calls` and is injected with `patch("ai.services.get_client", ...)`.
  - `response(*contents)` builds a fake reply, and `sdk_errors()` gives one of each SDK error (built with `httpx2`).
  - Log checks use `assertLogs("ai.services", "ERROR")`: exactly one record, the type name in it, no key, no SDK text, `exc_info is None`.
- **Summary feature** (the template for this ticket):
  - `GoalSummaryView(OwnGoalsMixin, SingleObjectMixin, View)` is POST only. It gathers sessions and resources through `owned_by(...).filter(goal=goal)`: `SUMMARY_SESSIONS = 10` newest `with_tags()`, the total over all sessions as one `Sum()`, and `SUMMARY_RESOURCES = 20` newest resources.
  - It calls `services.complete(system, user, max_retries=0)` and catches `AIServiceError` into `messages.error`, then saves with `update_fields`. Every outcome redirects to the goal.
  - `goals/prompts.py::summary_messages(goal, sessions, total_minutes, resources)` is a pure function returning `(system, user)`. Its user message has Goal, Status, Description, Total time, then "Recent sessions, newest first:" with one line per session, then "Resources:" with one line per resource. Missing parts are named ("No description.", "No sessions.", "No resources.").
- **Model**: `Goal.summary` is a `TextField(blank=True)` and `summary_generated_at` is nullable. The latest migration is `0003_goal_summary`. There's no JSONField in the project yet. `GoalAdmin` sets no `fields`, so new fields show up as editable on the change form, like the summary.
- **Goal view tests** (`src/goals/tests/test_views.py`):
  - Helpers: `add_session`, `add_resource`, `get_page(...).forms("main")`, `LabelledSectionText(heading_id)` for text inside an `aria-labelledby` section, and `login_redirect`.
  - Messages are checked by following the redirect (`assertContains(self.client.get(response.url), ...)`).
  - The clock is patched with `patch("django.utils.timezone.now", ...)`.
  - The summary tests follow `SummaryTestCase`: it patches `ai.services.OpenAI` to fail and `ai.services.complete` with a return value, and provides `assert_nothing_stored()`. The subclasses are Access, Generate, EmptyGoal, Error, DetailSection and Csrf.
  - `GoalViewsScopingTests` pins `set(views) == {"list", "detail", "edit", "delete", "summary"}`.
  - `GoalDetailQueryCountTests` pins `assertNumQueries(7)`.
  - `GoalEditTests.test_editing_keeps_the_summary_and_the_form_cannot_set_it` posts the summary fields and checks they're ignored.
- **Model and prompt tests**:
  - `goals/tests/test_models.py::GoalSummaryFieldTests` uses `getattr(..., default)` so a missing field fails rather than errors, and reads back through `Goal.objects.get`.
  - `goals/tests/test_prompts.py::SummaryMessagesTests` imports through `importlib` after a `find_spec` assertion. It checks exact lines with `assertIn(line, user.splitlines())` and order with `assertLess(user.index(a), user.index(b))`.
- **Docs**:
  - `CLAUDE.md`: the Goals bullet (summary part), the OpenAI bullet, and the Layout bullets for `src/goals/` and `src/ai/`.
  - `README.md`: the Setup paragraph on the Summary section, and the Layout bullet for `src/ai/`.
- **Commands**:
  - One module: `./.venv/bin/python src/manage.py test goals.tests.test_views --verbosity 2`
  - Full suite: `./.venv/bin/python src/manage.py test src`
  - Lint: `./.venv/bin/ruff check .`

## Design decisions
- **New service call `complete_json(system, user, *, name, schema, max_retries=MAX_RETRIES) -> dict`** in `ai/services.py`. It sends `response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}}` and returns the parsed JSON object. `complete()` and `complete_json()` share one private request helper (a refactor on green), so the SDK error wrapping, logging and empty-reply rule exist only once. Its only new error is a reply that isn't a JSON object (invalid JSON, for example truncated, or a non-object): `AIServiceError("The AI service returned an unexpected reply.")`, logged once without the reply text. A refusal has no `content`, so it is the existing empty-reply error.
- **The schema has no `minItems`/`maxItems`.** The installed SDK doesn't confirm strict mode accepts them, and an unsupported keyword would make every request a 400. The 2-3 count is asked for in the prompt and enforced in our own parsing.
- **The schema and the parsing live in `goals/prompts.py`**, next to the prompt, as pure functions:
  - `NEXT_STEPS_SCHEMA` is `{"type": "object", "properties": {"steps": {"type": "array", "items": {"type": "string"}}}, "required": ["steps"], "additionalProperties": false}`.
  - `parse_next_steps(reply) -> list[str]` trims each step and drops blank ones. It raises the same unexpected-reply `AIServiceError` if `steps` is missing, isn't a list, holds a non-string, or leaves fewer than 2 or more than 3 steps. So the view has one `except AIServiceError` for every failure.
- **`next_steps_messages(goal, sessions, total_minutes, resources) -> (system, user)`** reuses the summary's user message. The goal, sessions and resources lines are extracted into one shared builder (a refactor on green; `SummaryMessagesTests` stays unchanged), so both features describe a goal the same way. Only the system prompt differs.
- **Storage:** `Goal.next_steps = JSONField(default=list, blank=True)` (an ordered list of strings; a newline-joined text field would break on multi-line steps) and `next_steps_generated_at = DateTimeField(null=True, blank=True)`, added in migration `0004`. They're saved with `update_fields`, so `updated_at` doesn't move, and they're not in `GoalForm`. The admin shows them the way it shows the summary (no admin change).
- **View `GoalNextStepsView(OwnGoalsMixin, SingleObjectMixin, View)`**, POST only, at `<int:pk>/next-steps/` (`goals:next_steps`). The summary's data gathering (10 sessions, total, 20 resources, all through `owned_by`) moves into one shared helper used by both views (a refactor on green; the summary tests stay unchanged). There's no empty-goal check (the user's choice). It calls `services.complete_json(system, user, name="next_steps", schema=NEXT_STEPS_SCHEMA, max_retries=0)`, then `parse_next_steps()`. Any `AIServiceError` becomes `messages.error` and the old steps are kept. On success it shows `messages.success("Next steps suggested.")`, and every outcome redirects to the goal.
- **Tests** follow the summary's: a `NextStepsTestCase` in `goals/tests/test_views.py` patches `ai.services.OpenAI` to fail and `ai.services.complete_json` to return `{"steps": [...]}`, and provides `assert_nothing_stored()`.
- **Display:** a `<section aria-labelledby="next-steps-heading">` right after the Summary section, with the heading "Next steps".
  - With steps: an `<ol>` of the steps (auto-escaped), "Suggested <j M Y, H:i>" and a "Suggest new next steps" button.
  - Without steps: "No next steps yet." and a "Suggest next steps" button.
  - The steps come with the goal row, so the query count stays at 7.

## Steps
- [x] 1. **Structured call in the AI service.** `complete_json()` sends one request with the model, the system and user messages, and `response_format` set to a strict `json_schema` with the given name and schema. It returns the parsed object (surrounding whitespace is fine), and the retries are set per call with a default of 2. — test: `src/ai/tests/test_services.py` (`CompleteJsonTests`) — impl: `src/ai/services.py` — covers: AC8
- [x] 2. **Structured-call errors match `complete()`.** Every SDK error becomes the same safe `AIServiceError` with the SDK error as its `__cause__`, logged once by type with no key, no SDK text and no traceback. A reply with no content (none, blank or a refusal) is the empty-reply error. Refactor: one private request helper shared by `complete()` and `complete_json()`, with the existing `complete()` tests unchanged and green. — test: `src/ai/tests/test_services.py` (`CompleteJsonErrorTests`) — impl: `src/ai/services.py` — covers: AC8
- [x] 3. **A reply that isn't a JSON object** (invalid or truncated JSON, a list, a string, a number) becomes `AIServiceError("The AI service returned an unexpected reply.")`, logged once without the reply text. — test: `src/ai/tests/test_services.py` (`CompleteJsonErrorTests`) — impl: `src/ai/services.py` — covers: AC8, AC9
- [x] 4. **Next-steps fields on `Goal`.** A new goal has `next_steps == []` and `next_steps_generated_at is None`. A list of steps and its time are stored and read back in order. Migration `0004`. Editing a goal keeps the steps, and posting `next_steps`/`next_steps_generated_at` to the edit form changes nothing. — test: `src/goals/tests/test_models.py` (`GoalNextStepsFieldTests`), `src/goals/tests/test_views.py` (`GoalEditTests`) — impl: `src/goals/models.py`, `src/goals/migrations/0004_*.py` — covers: AC12
- [x] 5. **The next-steps prompt.**
  - The system prompt asks for 2 to 3 concrete, actionable next learning steps that build on what has been done, not repeating attached resources, with "how to start" when there are no sessions yet, as a JSON object with a `steps` list.
  - The user message has the same goal, session, total and resource lines as the summary's, including "No sessions." and "No resources." for an empty goal.
  - `NEXT_STEPS_SCHEMA` requires `steps` as an array of strings, with no other properties.
  - Refactor: one shared user-message builder, with `SummaryMessagesTests` unchanged.
  — test: `src/goals/tests/test_prompts.py` (`NextStepsMessagesTests`) — impl: `src/goals/prompts.py` — covers: AC5, AC6, AC7
- [x] 6. **Parsing the reply.** `parse_next_steps()` returns the steps trimmed and in order, dropping blank ones. It raises the unexpected-reply `AIServiceError` if `steps` is missing, isn't a list, holds a non-string, or leaves fewer than 2 or more than 3 steps. — test: `src/goals/tests/test_prompts.py` (`ParseNextStepsTests`) — impl: `src/goals/prompts.py` — covers: AC9
- [x] 7. **Route, POST only and access.**
  - `goals:next_steps` resolves to `/goals/<pk>/next-steps/`.
  - A GET is a 405 that calls nothing.
  - An anonymous POST is redirected to log in, with nothing called or stored.
  - Another user's goal is the same 404 as a missing pk, with nothing called or stored.
  - `next_steps` is added to `GoalViewsScopingTests`.
  — test: `src/goals/tests/test_views.py` (`NextStepsTestCase`, `GoalNextStepsAccessTests`, `GoalViewsScopingTests`) — impl: `src/goals/views.py`, `src/goals/urls.py` — covers: AC1, AC2, AC3
- [x] 8. **Suggesting stores the steps.**
  - There's exactly one `complete_json` call, made with `next_steps_messages()` over the 10 newest sessions (`with_tags()`), the total over all sessions and the 20 newest resources (other goals' data excluded), plus `name="next_steps"`, `schema=NEXT_STEPS_SCHEMA` and `max_retries=0`.
  - The parsed steps are stored trimmed with the patched time, replacing any earlier ones.
  - The user is redirected to the goal with "Next steps suggested.", and `updated_at` is unchanged.
  - Refactor: one shared data-gathering helper for both views, with the summary tests unchanged.
  — test: `src/goals/tests/test_views.py` (`GoalNextStepsSuggestTests`) — impl: `src/goals/views.py` — covers: AC5, AC10, AC12, AC15
- [x] 9. **An empty goal still gets suggestions.** A goal with no sessions and no resources calls the AI once, and the request contains "No sessions." and "No resources.". The steps are stored. — test: `src/goals/tests/test_views.py` (`GoalNextStepsEmptyGoalTests`) — impl: `src/goals/views.py` (expected to pass with step 8's code; if it's green on first run, the test is kept as a regression pin and noted in the commit) — covers: AC7
- [ ] 10. **AI errors.** Each service error (unavailable, empty reply, unexpected reply) and a parse failure (a wrong number of steps) redirects to the goal page with the error's message. The chained cause's text never shows up, the previously stored steps and time are unchanged, and it's never a 500. — test: `src/goals/tests/test_views.py` (`GoalNextStepsErrorTests`) — impl: `src/goals/views.py` — covers: AC9, AC14
- [ ] 11. **The Next steps section on the goal page.**
  - With no steps: "No next steps yet." and a "Suggest next steps" button, without the word "new".
  - With stored steps: an ordered list of the steps in order, each escaped, "Suggested 1 Oct 2026, 09:30" and a "Suggest new next steps" button.
  - The section comes after the Summary section.
  - Exactly one form in `main` posts to the route, with a CSRF token.
  - A POST without a token is a 403 that calls nothing; with the form's token it suggests.
  - `GoalDetailQueryCountTests` stores steps on its goal and still pins 7 queries.
  — test: `src/goals/tests/test_views.py` (`GoalDetailNextStepsTests`, `GoalNextStepsCsrfTests`, `GoalDetailQueryCountTests`) — impl: `src/templates/goals/goal_detail.html` — covers: AC4, AC11, AC13
- [ ] 12. **Docs.**
  - `CLAUDE.md`:
    - The Goals bullet: the next-steps route, view, stored fields, prompt and parsing, the no-empty-goal-check choice and `NextStepsTestCase`.
    - The OpenAI bullet: `complete_json()`, strict JSON schema, the unexpected-reply error, no `minItems`/`maxItems`.
    - The Layout bullets for `src/goals/` and `src/ai/`.
  - `README.md`: the Setup paragraph on the Next steps section, and the Layout bullet for `src/ai/`.
  — test: none (docs) — impl: `CLAUDE.md`, `README.md` — covers: AC16

## AC coverage
| AC | Steps |
|----|-------|
| AC1 route, 405, anonymous | 7 |
| AC2 cross-user 404 | 7 |
| AC3 scoping test | 7 |
| AC4 CSRF | 11 |
| AC5 what is sent | 5, 8 |
| AC6 system prompt | 5 |
| AC7 empty goal still suggested | 5, 9 |
| AC8 structured service call | 1, 2, 3 |
| AC9 malformed / wrong count | 3, 6, 10 |
| AC10 stored, replaced, message | 8 |
| AC11 Next steps section | 11 |
| AC12 updated_at, form | 4, 8 |
| AC13 query count 7 | 11 |
| AC14 errors shown, steps kept | 10 |
| AC15 no retries | 8 |
| AC16 docs | 12 |
