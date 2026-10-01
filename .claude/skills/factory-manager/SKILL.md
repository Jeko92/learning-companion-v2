---
name: factory-manager
description: Syncs work/backlog.md with the GitHub project board, inspects the current workflow phase, then triggers the one pipeline skill (refine-ticket, plan-ticket, tdd-implement, final-review, or release) that owns the next step. After a passed review it squash-merges the ticket PR into develop, closes the issue, and triggers the release skill to promote develop to main; only once main has the ticket does it pick the next Todo ticket from the board. Advances the pipeline by exactly one step per call and reports cleanly, so it is safe to invoke repeatedly, including from a loop. Use when the user wants the AI factory to keep moving without manually tracking phase and ticket state themselves.
---

# Manage the AI factory

Orchestrates the pipeline defined in `.claude/rules/workflow.md`, following the gitflow in `.claude/rules/git.md`. This skill never changes `phase` itself, never writes source code, and never invokes more than one phase skill per call — it only syncs the board, reads state, closes out finished tickets, decides which phase skill owns the next step, and triggers it with the `Skill` tool. All actual work and every phase transition still happens inside `refine-ticket`, `plan-ticket`, `tdd-implement`, `final-review`, and `release`.

Every ticket is released on its own (`.claude/rules/git.md`): after the ticket PR is squash-merged into `develop`, `release` promotes `develop` to `main`, and no new ticket is selected while `origin/develop` has commits `origin/main` lacks.

The board is the source of truth for tickets; `work/backlog.md` is its local mirror. All board reads and writes go through `python3 .claude/scripts/board.py` (`sync`, `next`, `status`); never edit status markers in `backlog.md` by hand.

## Preconditions

1. Read `.claude/state/workflow.json`. It may not exist yet — treat a missing file or a missing `phase` key as phase `idle`, exactly like `lib.sh:current_phase` does. Note `ticket`, `issue`, `branch`, `pr` and `release_status` the same way (missing = none).
2. `git fetch origin`, then note how far `develop` is ahead of `main`: `git rev-list --count origin/main..origin/develop` (the "release count").
3. Run `python3 .claude/scripts/board.py sync`. This rewrites `work/backlog.md` from the board (creating it if needed) and turns any new plain `- [ ] <description>` lines into issues. If it fails (gh not authenticated, board not configured), stop and report the error.

## Steps

Do exactly one of the following, then stop and report (step 6). Never chain two phase skills in one call — one call is one observable pipeline step.

1. **Waiting check.** If a line in `work/backlog.md` carries `[[parked: <skill> @ <phase>]]` and `<phase>` equals the *current* phase, the last call already triggered `<skill>` at this phase and it stopped to ask a human something (interview, ticket-id confirmation, plan approval), and nothing has moved since. Do not re-invoke it — go straight to step 6 and report that it is still waiting for the user. A parked `release` waits for a human to fix the cause (red suite, failed checks, conflict) and then run `/release`, which resumes and clears `release_status`. Remove every `[[parked: ...]]` tag whose phase no longer matches; that means progress happened since.

2. **Dispatch on phase:**

   | phase | action |
   |---|---|
   | `idle` | If the release count is greater than 0, invoke `release` (catch-up release: `develop` has work `main` lacks). Otherwise selection (step 4). |
   | `refined` | Invoke `plan-ticket`. |
   | `planned` | Invoke `tdd-implement`. |
   | `implementing` | Invoke `tdd-implement` (it resumes from the plan itself). |
   | `reviewing` | Invoke `final-review`. |
   | `done` | Close-out (step 3), then invoke `release`. Never select the next ticket in the same call. |
   | `releasing` | If `release_status` is `blocked`, do not invoke anything: park it (step 5) and report that the release needs a human. Otherwise (`waiting-checks` or empty) invoke `release`; it resumes where it stopped. |

3. **`done` — close-out.** Idempotent: skip any sub-step that is already true.
   1. Find the PR: `pr` from the state file, else `gh pr list --head <branch> --state all --json number,state`.
   2. If it is `OPEN`:
      - `gh pr checks <pr>`: if checks are still running, report "waiting for checks on PR #<pr>" and stop (a loop retries later). If any check failed, report it and stop — do not merge red; a human decides whether that becomes a `fix/` ticket.
      - `gh pr view <pr> --json mergeable`: if `CONFLICTING`, report it and stop.
      - Squash-merge into `develop`, keeping the branch: `gh pr merge <pr> --squash --subject "<type>(<ticket>): <issue title> (#<pr>)" --body "Closes #<issue>"` (`<type>` is `fix` for a `fix/` branch, otherwise `feat`).
   3. `gh issue close <issue> -R <GH_REPO> --reason completed` if it is still open, then `python3 .claude/scripts/board.py status <issue> Done`.
   4. `git status --porcelain`: if anything other than untracked files under `work/` shows up, stop and report it — final-review should have left the tree clean; don't paper over that.
   5. `git switch develop && git pull --ff-only`, so the release starts from the merged result.
   6. Invoke `release`. It merges `main` into `develop` with a merge commit, opens and merges the release PR into `main`, and sets the phase back to `idle`. The next ticket is selected by a later call, only after that.

4. **Selection.** Run `python3 .claude/scripts/board.py next`. It returns the first `Todo` ticket in board order as JSON (`{}` if none). If its body lists `Depends on: #<n>` and any of those issues is not `[x]` in `work/backlog.md`, skip it and check the next Todo line in `backlog.md` order instead — log each skip rather than guessing an order, and ask the user only if two candidates are genuinely ambiguous in priority. If no eligible Todo ticket exists, report **"Backlog is empty — nothing to do"** and stop; that's the signal for a wrapping loop to stop too.

   Invoke `refine-ticket` with `#<issue> <ticket-id>: <title>` as its argument. It reads the issue, creates the branch from `develop`, and moves the card to In Progress.

5. **Park if waiting.** After the invoked skill returns, re-read `.claude/state/workflow.json`. If the phase did not advance because the skill stopped to ask the user something, append `[[parked: <skill> @ <phase>]]` to that ticket's line in `work/backlog.md` (the candidate's line for `refine-ticket`), so the next call doesn't restart the interview or regenerate the plan.

   For `release`: if the phase is still `releasing` and `release_status` is `blocked` (red suite after the main-into-develop merge, failed checks, or a conflict that needs a human), append `[[parked: release @ releasing]]` to the line of the newest ticket in that release (`ticket` from the state file; for a catch-up release, the last ticket id in the release PR title). `waiting-checks` is not parked: a later call resumes it.

6. **Report.** One short summary: phase before → phase after, the ticket id and issue number, and what changed (artifact, PR merged, card moved, ticket picked). If the invoked skill stopped to ask the user something — ticket interview, ticket-id confirmation, plan approval — say exactly that instead of answering on its behalf; a human needs to be present for that turn, and this skill does not fabricate approval to keep a loop moving.

## Hard limits

- Never call `.claude/hooks/set-state.sh`; only the phase skill that owns a transition may change `phase` or `ticket`.
- Never invoke more than one phase skill per call.
- Never fabricate or infer the user's approval of a ticket or plan.
- Never write source code from this skill (the write-protection hook would block it outside `implementing` anyway); it only ever delegates.
- Never merge a PR with failing checks, never merge into `main`, never delete a ticket branch. Releases to `main` are the `release` skill's job; this skill only triggers it (after every close-out, and as a catch-up when `develop` is ahead of `main`), and `release` counts as the one phase skill of that call.
- Never select or refine a new ticket while the release count is greater than 0 or the phase is `releasing`.
- Never reorder or delete backlog lines; order and status live on the board. The only hand edits to `backlog.md` are adding and removing `[[parked: ...]]` tags. `backlog.md` is git-ignored, so it is never committed.
