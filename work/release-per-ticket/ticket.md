# Workflow: release develop to main after every ticket
Issue: #23 · Branch: feature/release-per-ticket

## Story
As the person running the AI factory, I want `develop` promoted to `main` after every ticket is merged, with conflicts resolved through a merge commit and the next ticket starting only once `main` has the last one, so that `main` always reflects every finished feature and tickets never pile up unreleased.

## Acceptance criteria
- [x] AC1 `.claude/rules/git.md` says that after every ticket PR (`feature/` or `fix/`) is squash-merged into `develop`, the `release` skill promotes `develop` to `main`. It also says that conflicts are resolved by merging `main` into `develop` with a merge commit (`chore(release): merge main into develop`), never on `main`; that the release PR is merged with a merge commit; and that the next ticket starts only after `main` contains the merged ticket. The phrase "only when the user asks" is gone.
- [x] AC2 In `.claude/rules/workflow.md`, the phase table goes `done` → `releasing` → `idle`. `done`'s exit is "PR squash-merged, issue closed, release started". `releasing`'s exit is "release PR merged into `main`", and the "(only when asked)" wording is gone. A rule line says that no ticket is selected while `develop` has commits `main` lacks.
- [x] AC3 The `release` skill can be triggered by `factory-manager`: `disable-model-invocation` is removed and the description no longer says "only when the user explicitly asks". Its preconditions accept phase `done` (the ticket PR is merged) or `idle` (when `origin/develop` has commits that `origin/main` lacks).
- [x] AC4 The `release` skill names the release PR `chore(release): <yyyy-mm-dd> <ticket-id>` (more than one ticket id if a catch-up release covers several).
- [x] AC5 The `release` skill's check handling:
  - **No checks reported:** merge.
  - **Checks still running:** stop, report "waiting for checks on release PR #n", and leave the PR open and the phase `releasing` so a later call resumes it.
  - **A check fails, the suite or lint is red after the main-into-develop merge, or a conflict needs a human:** stop and report it, leaving the phase at `releasing`.
- [x] AC6 `factory-manager`'s dispatch:
  - **`done`:** close-out (squash-merge, close the issue, card to Done, fast-forward `develop`), then invoke `release`. It no longer goes straight to selection.
  - **`releasing`:** invoke `release` to resume.
  - **A release that needs a human** ends in `idle` with `release_status: blocked`. factory-manager then never re-invokes `release`; it reports the reason and only selects `type:fix` tickets, so a loop waits instead of retrying.
    - Amended during the review-fix round (2026-10-01): the original wording, park as `[[parked: release @ releasing]]`, was replaced by the recovery path the user approved for review finding 1 (plan step 7) and finding 2 (step 8).
  - **`idle`:** if `origin/develop` has commits that `origin/main` lacks and no release is blocked, invoke `release` (catch-up) instead of selecting a ticket.
  - Its hard limits no longer say releases happen "only when the user asks". Each call still invokes at most one phase skill, where `release` counts as one.
- [x] AC7 `.claude/hooks/guard-bash.sh` blocks creating a `feature/` or `fix/` branch (`git switch -c`, `git checkout -b`, `git branch <name>`) while `git rev-list --count origin/main..origin/develop` is greater than 0. The message points to the `release` skill. Creation is allowed when the count is 0, and switching to an existing ticket branch is never blocked.
- [x] AC8 `guard-bash.sh` still allows the release flow in phase `releasing`: the main-into-develop merge and commit on `develop`, `git push origin develop`, and `gh pr merge <n> --merge`. Everything it blocked before is still blocked.
- [x] AC9 `refine-ticket`'s preconditions say to stop and point to `factory-manager` when `origin/develop` has commits that `origin/main` lacks.
- [x] AC10 `CLAUDE.md`, `README.md` and the comment in `.claude/hooks/config.sh` describe `main` as updated after every ticket through the `release` skill. None of them still says a release happens only on request.

## Out of scope
- How ticket branches are cut, reviewed and squash-merged into `develop`.
- CI (ticket `ci-tests`). Until it exists, release PRs have no checks.
- Branch protection settings on GitHub.

## Notes
Answers from refinement (2026-10-01):
- The release PR is merged when no checks are reported. The local suite and lint, run after the main-into-develop merge, are the gate until CI exists. Running checks mean wait, and failed checks mean stop.
- A release that can't finish blocks the factory. The phase stays `releasing`, and a human decides what to do, often through a `fix/` ticket.
- "No new ticket before main is updated" is enforced by a hook (AC7) as well as by the skill instructions.
- **Verification is review-only, as the user chose.** There are no automated tests for this ticket. Final-review checks each AC by reading the changed files and running `guard-bash.sh` by hand with sample hook input, for AC7/AC8. This deliberately departs from "every AC verifiable by a test". The `tdd-implement` steps for this ticket are therefore docs/config steps without a red–green cycle.
- Bootstrapping: this ticket's own close-out runs under the new rules. Its release promotes `develop` to `main` with #1 (`setup-env-settings`) and #23 together, which matches the user's decision that #1 reaches main with the next release.
- Ticket #2 (`setup-layout-tailwind`) was paused for this ticket and resumes after it, from its existing branch (AC7 allows switching to an existing branch).
- On the board, #23 sits after #2. It was picked first at the user's request, outside board order.
