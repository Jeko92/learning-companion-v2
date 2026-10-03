# AI: suggest 2-3 next learning steps
Issue: #17 · Branch: feature/ai-next-steps

## Story
As a logged-in learner, I want the AI to suggest 2-3 concrete next learning steps for one of my goals, based on what I've done so far, and see them on the goal's page as a short list until I ask again, so that I always know what to do next.

## Acceptance criteria

**Route and access**
- [x] AC1 Suggesting is a POST to `/goals/<goal_pk>/next-steps/`. A GET there is not allowed (405) and calls nothing. An anonymous POST is redirected to the login page, stores nothing and doesn't call the AI.
- [x] AC2 A POST for another user's goal is a 404 identical to a missing goal pk: the AI is not called and nothing is stored.
- [x] AC3 The new route is covered by the goals app's owner-scoping test (looked up through `Goal.objects.owned_by`, ownership mixin first, no `model`), added deliberately.
- [x] AC4 A POST without a CSRF token is rejected (403), and nothing is called or stored.

**What is sent**
- [x] AC5 The request contains the same data as the summary: the goal's title, description and status; its 10 most recent sessions, newest first, each with date, duration, tags and notes; the total time over all its sessions; and its 20 newest resources with title, type and URL. Sessions beyond the 10th, and other goals' sessions and resources, are not included.
- [x] AC6 The system prompt asks for 2 to 3 concrete, actionable next learning steps that build on what has been done (not repeating the resources already attached), and for a reply that is a JSON object with a `steps` list.
- [x] AC7 A goal with no sessions and no resources still gets suggestions: the AI is called, and the request says there are no sessions and no resources, so the steps cover how to start.

**Structured reply**
- [x] AC8 `ai.services` can make a call that asks the API for a structured JSON reply matching a given JSON schema and returns the parsed object. It takes the retry count per call like `complete()`, and has the same error rules: every SDK error and an empty reply become an `AIServiceError` with a message safe to show, logged by error type only; no test reaches the network.
- [x] AC9 A reply that isn't valid JSON, doesn't match the schema, or doesn't have 2 to 3 non-blank steps after trimming is an `AIServiceError` ("The AI service returned an unexpected reply." or similar, safe to show), and nothing is stored. Steps are stored trimmed.

**Stored and shown**
- [x] AC10 On success, the steps are stored on the goal in order, with the time they were generated, replacing any earlier ones, and the user is redirected to the goal page with "Next steps suggested.".
- [x] AC11 The goal page has a Next steps section (`aria-labelledby="next-steps-heading"`) below the Summary: the stored steps as an ordered list (each HTML-escaped) with their generation time and a "Suggest new next steps" button, or "No next steps yet." and a "Suggest next steps" button. The button is a POST form with a CSRF token.
- [x] AC12 Suggesting next steps doesn't change the goal's "Updated" time, and editing the goal (its form) doesn't change or clear the steps; the new fields are not in the goal form.
- [x] AC13 The goal page keeps its fixed query count (7): the steps come with the goal row.

**Errors and wait time**
- [x] AC14 When the AI service fails (`AIServiceError`: unavailable, empty reply, malformed reply, wrong number of steps), the user is redirected to the goal page with the error's message, the previously stored steps are unchanged, and the response is never a 500.
- [x] AC15 The call is made without retries (`max_retries=0`), like the summary, so a failing API makes the user wait at most one timeout.

**Docs**
- [x] AC16 `CLAUDE.md` and `README.md` document the next-steps route, view, stored fields, prompt contents, the structured-reply service call and its error cases.

## Out of scope
- Turning suggestions into goals automatically
- Marking steps as done, or a history of earlier suggestions
- Streaming the reply
- Per-user rate limiting or quotas (see #36 deploy-hardening)
- Changing the summary feature (its prompt already mentions "the next focus"; it stays as is)

## Notes
- **Storage:** the user chose to keep the latest steps on the goal with their generation time, like the summary (needs a migration on `goals.Goal`).
- **Format (the issue's open question):** the user chose structured JSON output through the OpenAI API's JSON-schema response format over parsing plain-text lines, so the list parsing is reliable; a reply that doesn't fit is an `AIServiceError`, never a 500. This extends `ai.services` with new service tests (`NoNetworkTestCase`).
- **Prompt data:** the user chose to send the same data as the summary (goal, 10 newest sessions, total time, 20 newest resources), so the steps don't repeat already-attached material.
- **Empty goal:** the user chose to still suggest for a goal with no sessions and no resources (unlike the summary), since "how to start" steps are most useful then.
- **Wait time and errors:** same rules as the summary: no retries for a page action, and every `AIServiceError` is caught and shown, because its chained SDK error can echo part of the key.
- The interview took place on 2026-10-03.
- **Approval:** the user approved the acceptance criteria (AC1–AC16) on 2026-10-03.
