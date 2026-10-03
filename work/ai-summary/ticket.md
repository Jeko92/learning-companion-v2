# AI: generate a progress summary for a goal
Issue: #16 · Branch: feature/ai-summary

## Story
As a logged-in learner, I want to generate an AI progress summary of one of my goals from its recent sessions and resources, and see it on the goal's page until I regenerate it, so that I can quickly see how far I've got and what to focus on next.

## Acceptance criteria

**Route and access**
- [ ] AC1 Generating is a POST to `/goals/<goal_pk>/summary/`. A GET there is not allowed (405) and calls nothing. An anonymous POST is redirected to the login page, stores nothing and doesn't call the AI.
- [ ] AC2 A POST for another user's goal is a 404 identical to a missing goal pk: the AI is not called and nothing is stored.
- [ ] AC3 The new route is covered by the owner-scoping test of the app it lives in (looked up through `Goal.objects.owned_by`, ownership mixin first, no `model`), added deliberately.
- [ ] AC4 A POST without a CSRF token is rejected (403), and nothing is called or stored.

**What is sent**
- [ ] AC5 The request (through `ai.services.complete`) contains the goal's title, description and status; its 10 most recent sessions, newest first, each with date, duration, tags and notes; the total time over all its sessions; and its 20 newest resources with title, type and URL. Sessions beyond the 10th, and other goals' sessions and resources, are not included.
- [ ] AC6 The system prompt asks for a short progress summary: time spent, what has been covered, and the next focus.
- [ ] AC7 For a goal with no sessions and no resources, the AI is not called and nothing is stored; the user is sent back to the goal page with "Log a session or attach a resource first."

**Stored and shown**
- [ ] AC8 On success the trimmed reply is stored on the goal with the time it was generated, replacing any earlier summary, and the user is redirected to the goal page with "Summary generated.".
- [ ] AC9 The goal page has a Summary section: the stored summary (HTML-escaped, line breaks kept) with its generation time and a "Regenerate summary" button, or "No summary yet." and a "Generate summary" button. The button is a POST form with a CSRF token.
- [ ] AC10 Generating a summary doesn't change the goal's "Updated" time, and editing the goal (its form) doesn't change or clear the summary; the summary fields are not in the goal form.
- [ ] AC11 The goal page keeps its fixed query count (7): the summary comes with the goal row.

**Errors and wait time**
- [ ] AC12 When the AI service fails (`AIServiceError`, both the unavailable and the empty-reply case), the user is redirected to the goal page with the error's message, the previously stored summary is unchanged, and the response is never a 500.
- [ ] AC13 The summary call is made without retries, so a failing API makes the user wait at most one timeout. `ai.services.complete` takes the retry count per call; callers that don't pass it keep the default of 2.

**Docs**
- [ ] AC14 `CLAUDE.md` and `README.md` document the summary route, view, stored fields, prompt contents, the no-retries choice, and reword "30-second timeout" to "30 seconds per network phase".

## Out of scope
- Streaming the reply
- A history of earlier summaries
- Per-user rate limiting or quotas (see #36 deploy-hardening)
- Styling error messages differently from success messages
- The next-steps feature (#17)

## Notes
- **Recent:** the user chose the 10 newest sessions, plus the total time over all of them. Resources are capped at the 20 newest (my default, so the prompt stays bounded; the user can change it at approval).
- **Storage:** the user chose to keep the latest summary on the goal (with its generation time) over showing it once. Needs a migration on `goals.Goal`.
- **Wait time:** a #15 review follow-up. The user chose no retries for this page action. The SDK's 30 s applies per network phase and it honours `Retry-After` up to 120 s between retries, so with 2 retries a click could hang for minutes.
- **Errors:** the other #15 follow-up: the view must catch `AIServiceError` and show its message, so its chained SDK error (which can echo the key's last characters) never reaches a 500 page or error log.
- **Empty goal:** the user chose not to call the AI when there is nothing to summarise.
- **Display:** after any POST the user lands back on the goal page (post/redirect/get), as with the other goal actions; the result is shown through the stored summary and a message.
- The issue's open questions ("recent" and storage) were answered in the interview on 2026-10-03.
