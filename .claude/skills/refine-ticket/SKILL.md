---
name: refine-ticket
description: Turn a board issue, rough ticket or feature idea into a refined ticket with acceptance criteria. First phase of the development workflow; starts a new ticket, creates the feature/ or fix/ branch from develop. Use when factory-manager picks the next board ticket or the user brings a new task, story, or bug report.
---

# Refine a ticket

Input (`$ARGUMENTS` if provided): normally a board issue handed over by `factory-manager` (`#<issue> <ticket-id>: <title>`), otherwise the user's rough ticket — pasted text, a file path, or a one-line idea.

## Preconditions

Read `.claude/state/workflow.json` (if it exists). If a ticket is already in progress (phase is not `idle` or `done`), stop and ask the user whether to abandon it or finish it first. Do not silently start a second ticket.

If the phase is `done`, the previous ticket has not been closed out and released yet: stop and point to `factory-manager`, which squash-merges its PR and then runs the `release` skill.

The previous ticket must also be on `main` before a new one starts: run `git fetch origin`, then `git rev-list --count origin/main..origin/develop`. If it is greater than 0, `develop` has work `main` lacks: stop and point to `factory-manager`, which runs the release first. (`guard-bash.sh` blocks creating the ticket branch in that state anyway.)

Exception: if `release_status` in the state file is `blocked`, a release could not finish and only a fix can unblock it. Then accept only issues labelled `type:fix` (their `fix/` branch is allowed by the hook); for any other issue, stop and report the blocked release and its `release_reason`.

## Steps

1. **Resolve the issue.**
   - Board issue given: read it with `gh issue view <issue> -R <GH_REPO> --json number,title,body,labels`. The ticket id is the `Ticket id:` line in the body. Use the issue body as the starting point for the interview.
   - No issue yet (user brought a new idea): derive a short kebab-case ticket id (e.g. `comments-endpoint`), confirm it with the user if the task is ambiguous, then create the issue on the board: `python3 .claude/scripts/board.py add "<title>" --id <id> --body "<summary>"`.

   Branch: `fix/<id>` if the issue is labelled `type:fix`, otherwise `feature/<id>`.
2. Investigate context cheaply: use one `Explore` sub-agent to find the parts of the codebase the ticket touches. Do not read whole modules into the main context — you only need enough to ask informed questions.
3. Interview the user. Ask about anything that changes scope or design, typically: expected behaviour and edge cases, validation and error responses, auth requirements, out-of-scope items, and the open questions listed in the issue. Ask in one batch, not one question per turn.
4. Write `work/<id>/ticket.md`:

   ```markdown
   # <Title>                     <!-- one line -->
   Issue: #<issue> · Branch: <branch>
   ## Story
   As a ..., I want ..., so that ...
   ## Acceptance criteria
   - [ ] AC1 ... (concrete, testable, one behaviour each)
   ## Out of scope
   ## Notes
   Open questions that were answered, relevant constraints.
   ```

   Every acceptance criterion must be verifiable by a test. If you cannot phrase it as a test, refine it further.
5. Create the branch from the latest `develop`, record the state, move the card:

   ```bash
   git switch develop && git pull --ff-only
   git switch -c <branch>
   bash .claude/hooks/set-state.sh phase refined ticket <id> issue <issue> branch <branch> current_step "" last_test ""
   git add work/<id>/ticket.md && git commit -m "docs(<id>): refined ticket"
   python3 .claude/scripts/board.py status <issue> "In Progress"
   ```

   (If `develop` has no upstream yet, skip the pull.)
6. Show the user the acceptance criteria and ask for approval. On approval, tell them the next step is `plan-ticket`. Do not start planning in the same breath unless the user asks you to continue.

## Hard limits

- Do not touch any source code in this phase.
- Do not propose an implementation; that is the plan phase's job.
- Never branch a ticket off `main` or off another ticket branch.
