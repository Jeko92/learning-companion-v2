# Plan: ai-summary

## Research summary

- **AI service** (`ai/services.py`, from #15): `complete(system, user)` builds its client with `get_client()` (no arguments: key, `TIMEOUT_SECONDS = 30`, `MAX_RETRIES = 2`), sends `[system, user]` with `settings.OPENAI_MODEL`, returns the trimmed text, and raises `AIServiceError` ("The AI service is unavailable right now. Please try again later." / "The AI service returned an empty reply."). Tests: `ai/tests/test_services.py` with `response()`, `FakeClient` (records `create` kwargs) and `NoNetworkTestCase` (patches `ai.services.OpenAI` to fail); `GetClientTests` pins `OpenAI(api_key=…, timeout=30, max_retries=2)`.
- **Goals** (`goals/`): `Goal` has `owner`, `title`, `description` (≤ 2,000), `status` (`TextChoices`, `get_status_display`), `created_at`, `updated_at` (`auto_now`); latest migration `0002_alter_goal_description`. `GoalForm.Meta.fields = ("title", "description", "status")`. Admin: `list_display`, `list_filter`, `search_fields` only. Routes in `goals/urls.py` (`app_name = "goals"`): `""` list, `new/`, `<int:pk>/`, `<int:pk>/edit/`, `<int:pk>/delete/`. Every view but create is `OwnGoalsMixin, …` (`get_queryset()` = `Goal.objects.owned_by(user)`). `GoalViewsScopingTests` iterates `goal_urls.urlpatterns` (skipping `create`), asserts the exact name set `{"list", "detail", "edit", "delete"}`, `model is None`, a `SingleObjectMixin`/`MultipleObjectMixin` in the MRO after `OwnGoalsMixin`, `get_queryset is OwnGoalsMixin.get_queryset`, and scoping via `setup(request, pk=…)`. No POST-only view exists yet (Django's `View.http_method_names` answers other methods with 405).
- **Goal page**: `GoalDetailView` context has `recent_sessions` (5, `with_tags()`), `total_minutes` (`Sum`), `resource_groups`, `resource_form`; the template has Sessions and Resources (`aria-labelledby="resources-heading"`) sections. `GoalDetailQueryCountTests` pins `assertNumQueries(7)` (login session, user, goal, total, recent sessions, their tags, resources) and large = small.
- **Data**: sessions are newest first (`-date`, `-created_at`, `-id`), `with_tags()` prefetches tags case-insensitively alphabetical; the `duration` filter (`learning_sessions/templatetags/session_format.py`) is plain Python ("45 min", "2 h", "1 h 30 min"). Resources are newest first, `type` has `get_type_display`. All lookups go through `owned_by(user)`.
- **Messages**: `django.contrib.messages` is installed; `base.html` renders every message the same way (outside `<main>`). Successful goal actions redirect with `SuccessMessageMixin`.
- **Tests**: `goals/tests/test_views.py` has `PASSWORD`, `get_page()` (`PageParser`), `add_session()`, `add_resource()`, `LabelledSectionText(heading_id)`; users via `create_user`, `force_login`. Clock patching: `patch("django.utils.timezone.now", return_value=…)` (as in `GoalTimestampTests`). CSRF: `Client(enforce_csrf_checks=True)` and the form's token from the page.

## Design decisions

- **The view lives in the goals app**: `GoalSummaryView(OwnGoalsMixin, SingleObjectMixin, View)` at `goals/urls.py` `<int:pk>/summary/` (name `summary`, so `/goals/<pk>/summary/`), `http_method_names = ["post"]` (GET is 405). Rationale: the summary belongs to a goal; `SingleObjectMixin` + `OwnGoalsMixin` gives the owner-scoped `get_object()` 404 for free and fits `GoalViewsScopingTests`, whose expected set gets `"summary"` added deliberately.
- **Prompts live in `goals/prompts.py`**: `summary_messages(goal, sessions, total_minutes, resources) -> (system, user)`, a pure function (no queries). Rationale: the `ai` app stays a generic service; the prompt is tested on its own without views; #17 adds its own function next to it.
- **The view gathers the data** through `owned_by`: the 10 newest sessions (`with_tags()`), the total over all sessions (`Sum`), the 20 newest resources. `SUMMARY_SESSIONS = 10`, `SUMMARY_RESOURCES = 20` on the view.
- **Stored on `Goal`**: `summary = TextField(blank=True)` and `summary_generated_at = DateTimeField(null=True, blank=True)`, migration `0003`. Saved with `save(update_fields=["summary", "summary_generated_at"])`, so `updated_at` (`auto_now`) isn't written (AC10). `GoalForm` keeps its allow-list, so editing can't touch them.
- **Per-call retries**: `complete(system, user, *, max_retries=MAX_RETRIES)` passes it to `get_client(max_retries=MAX_RETRIES)`; the summary view calls it with `max_retries=0`. Rationale: default callers are unchanged (AC13), and the client is still built in one place.
- **The view calls `services.complete`** (`from ai import services`), so tests patch `ai.services.complete`; the goal-view test classes for the summary also patch `ai.services.OpenAI` to fail, as `NoNetworkTestCase` does, so a missed patch can't reach the network.
- **Errors and empty goals redirect with a message** (`messages.error` / `messages.info`), success with `messages.success("Summary generated.")`; every outcome is post/redirect/get to the goal page.
- **Display**: a Summary section on the goal page with `aria-labelledby="summary-heading"` (so tests read it with `LabelledSectionText`), the text through `linebreaksbr` (autoescaped), the time as `"j M Y, H:i"`, and a POST form to `goals:summary` with the button "Generate summary" / "Regenerate summary".

## Steps

- [x] 1. **Per-call retries in the AI service.** `get_client(max_retries=0)` builds the client with `max_retries=0`; `get_client()` still uses 2. `complete(system, user, max_retries=0)` builds its client with 0, and `complete(system, user)` with 2 (checked through a patched `get_client`). — test: `ai/tests/test_services.py` (`GetClientTests`, `CompleteTests`) — impl: `ai/services.py` — covers: AC13 (service)

- [x] 2. **Summary fields on `Goal`.** A new goal has `summary == ""` and `summary_generated_at is None`; both are stored and read back; `GoalForm` still offers only title, description and status, and posting the edit form leaves a stored summary and its time unchanged. Migration `0003` added (`makemigrations --check` clean). — test: `goals/tests/test_models.py` (`GoalSummaryFieldTests`), `goals/tests/test_views.py` (`GoalEditKeepsSummaryTests`) — impl: `goals/models.py`, `goals/migrations/0003_goal_summary.py` — covers: AC8 (storage), AC10 (form)

- [x] 3. **The summary prompt.** `summary_messages(goal, sessions, total_minutes, resources)` returns `(system, user)`. The system prompt asks for a short progress summary: time spent, what has been covered, the next focus. The user message contains the goal's title, description and status label; one line per given session in the given order with date, duration (`duration` format), tags and notes; the total time; one line per resource with title, type label and URL. Without description, sessions or resources it says so ("No description.", "No sessions.", "No resources.") instead of leaving blanks. — test: `goals/tests/test_prompts.py` (new) — impl: `goals/prompts.py` (new) — covers: AC5 (content), AC6

- [x] 4. **Route, POST-only and access.** `reverse("goals:summary", args=[pk])` is `/goals/<pk>/summary/`. With `ai.services.complete` patched to a mock in every case: an owner's GET is 405; an anonymous POST redirects to login (with `next`); a POST for bob's goal is a 404 with the same content as a missing pk; none of them calls `complete` or stores a summary. `GoalViewsScopingTests` expects `{"list", "detail", "edit", "delete", "summary"}`. (The owner's POST only redirects to the goal page in this step.) — test: `goals/tests/test_views.py` (`GoalSummaryAccessTests`, `GoalViewsScopingTests`) — impl: `goals/urls.py`, `goals/views.py` (`GoalSummaryView`) — covers: AC1, AC2, AC3

- [x] 5. **Generating stores the summary.** For a goal with 12 sessions (one tagged, one with notes) and 22 resources, plus sessions and resources on alice's other goal and bob's goal: one `complete` call with `max_retries=0` and exactly the `(system, user)` that `summary_messages` builds from the 10 newest sessions (with tags), the total over all 12, and the 20 newest resources (so the 11th/12th session, the 21st/22nd resource and other goals' data are absent). The reply `"  Keep going \n"` is stored as `"Keep going"` with the (patched) current time; the response redirects to the goal page and shows "Summary generated."; `updated_at` is unchanged; a second run replaces the first summary and time. — test: `goals/tests/test_views.py` (`GoalSummaryGenerateTests`) — impl: `goals/views.py` — covers: AC5, AC8, AC10 (updated time), AC13

- [ ] 6. **Nothing to summarise.** For a goal with no sessions and no resources: `complete` isn't called, nothing is stored, and the user is redirected to the goal page with "Log a session or attach a resource first.". A goal with only a session, or only a resource, does call it. — test: `goals/tests/test_views.py` (`GoalSummaryEmptyGoalTests`) — impl: `goals/views.py` — covers: AC7

- [ ] 7. **AI errors.** With `complete` raising `AIServiceError` with each of the service's two messages: the response is a redirect to the goal page (never a 500), the page shows that message, and an earlier stored summary and its time are unchanged. — test: `goals/tests/test_views.py` (`GoalSummaryErrorTests`) — impl: `goals/views.py` — covers: AC12

- [ ] 8. **The Summary section on the goal page.** Without a summary: "No summary yet." and a POST form to `/goals/<pk>/summary/` with a CSRF token and a "Generate summary" button. With one: the text (an HTML payload escaped, line breaks as `<br>`), "Generated <j M Y, H:i>", and "Regenerate summary". `GoalDetailQueryCountTests` (with a stored summary on the large goal) still counts 7. CSRF: posting without the token is 403 and `complete` isn't called; with the token from this form it redirects. — test: `goals/tests/test_views.py` (`GoalDetailSummaryTests`, `GoalSummaryCsrfTests`, `GoalDetailQueryCountTests`) — impl: `templates/goals/goal_detail.html` — covers: AC4, AC9, AC11

- [ ] 9. **Docs.** `CLAUDE.md`: Goals bullet (the summary route and view, the stored fields and `update_fields`, the Summary section, the scoping test's new route), the OpenAI bullet (`complete(..., max_retries=)`, the summary's `max_retries=0`, "30 s per network phase" instead of a 30-second timeout, callers catch `AIServiceError`), Layout (`goals/prompts.py`). `README.md`: the goal page's summary, and the `src/ai/` line's "30-second timeout" reworded. No test (docs only). — test: none — impl: `CLAUDE.md`, `README.md` — covers: AC14

## AC coverage

| AC | Steps |
|----|-------|
| AC1 POST-only route, anonymous | 4 |
| AC2 other user's goal 404, no call | 4 |
| AC3 scoping test | 4 |
| AC4 CSRF | 8 |
| AC5 prompt contents and limits | 3, 5 |
| AC6 system prompt | 3 |
| AC7 empty goal | 6 |
| AC8 stored, replaced, message | 2, 5 |
| AC9 Summary section | 8 |
| AC10 updated time, edit keeps summary | 2, 5 |
| AC11 query count 7 | 8 |
| AC12 errors | 7 |
| AC13 no retries, default 2 | 1, 5 |
| AC14 docs | 9 |
