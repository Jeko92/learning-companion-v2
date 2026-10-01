# Git conventions (gitflow)

## Branches

- `main` is the release branch. It is protected and only changes through a PR from `develop`, created and merged by the `release` skill after every ticket. Never commit, merge or push to `main` directly.
- `develop` is the integration branch. It only receives squash-merged PRs from ticket branches, plus the main-into-develop merge commit made by the `release` skill. Never commit to it directly.
- Every ticket gets its own branch cut from the latest `develop`: `feature/<ticket-id>` for features, `fix/<ticket-id>` for bug tickets (issue labelled `type:fix`). The `refine-ticket` skill creates it; the branch name is recorded as `branch` in the state file. A new ticket branch can only be cut once `main` contains the previous ticket (`origin/develop` has no commits that `origin/main` lacks).
- A paused ticket keeps its branch. When `refine-ticket` resumes it, it switches to that branch and merges the latest `develop` into it (`chore(<ticket-id>): merge develop into paused ticket branch`); it never recreates or rebases the branch.
- Ticket branches are never deleted, locally or on GitHub. `develop` only gets one squash commit per ticket, so the ticket branch is where its per-step commit history stays visible.

All of the above is enforced by `.claude/hooks/guard-bash.sh`, as a guardrail against mistakes while following the skills. It matches command text, so it is not a sandbox; its header lists the known gaps. The real control against bypassing the gitflow is GitHub branch protection on `main` and `develop`, which is configured on GitHub, outside this repository.

## Commits

- Conventional Commits, with the ticket id as scope (see `.conventionalcommit.json`):
  - `feat(<ticket-id>): <what the step delivers>` for plan steps on a feature ticket, `fix(<ticket-id>): ...` on a fix ticket,
  - `docs(<ticket-id>): ...` for workflow artifacts,
  - `refactor(<ticket-id>): ...` for pure refactoring commits,
  - `chore(release): ...` for release merges.
- Commit after every green TDD cycle. Small commits are the audit trail of the workflow; do not batch several steps into one commit.
- Commits require a green test suite and `--no-verify` is forbidden.

## Ticket PRs (ticket branch -> develop)

- Pushing the ticket branch is only possible once the final review has passed (phase `done`).
- `final-review` opens the PR with `gh pr create --base develop`, title `<type>(<ticket-id>): <issue title>`, body with the story, the acceptance criteria, `Closes #<issue>` and a reference to `work/<ticket-id>/review.md`.
- `factory-manager` squash-merges it (`gh pr merge <n> --squash`, never `--delete-branch`) once checks are green, closes the issue, moves the card to Done, then fast-forwards local `develop` (`git pull --ff-only`) and starts the release.

## Releases (develop -> main), after every ticket

Every ticket is released on its own. Once a ticket PR (`feature/` or `fix/`) is squash-merged into `develop`, `factory-manager` triggers the `release` skill, which promotes `develop` to `main`:

1. On `develop`, merge `origin/main` into it with a merge commit, `chore(release): merge main into develop`. All conflicts between `develop` and `main` are resolved there, in that merge commit, never on `main`. The merge is staged first and only committed once the suite and lint are green; then push `develop`.
2. Open a PR `develop -> main` titled `chore(release): <yyyy-mm-dd> <ticket-id>` and merge it with a merge commit (`gh pr merge <n> --merge`). Without CI, no checks are reported and the local suite and lint are the gate (`guard-bash.sh` re-runs both right before `gh pr merge`, and only lets the `develop -> main` PR be merged while releasing); running checks are waited for, failed checks stop the release. Once CI exists (ticket `ci-tests`), set `REQUIRE_CHECKS="true"` in `.claude/hooks/config.sh` so a release PR without checks is blocked instead of merged. Only squash commits of ticket PRs merged into `develop` are released; anything else on `develop` blocks the release.

The next ticket only starts once `main` contains the merged ticket. `factory-manager` selects nothing while `origin/develop` has commits `origin/main` lacks (it runs a catch-up release instead), and `guard-bash.sh` blocks creating a new `feature/` or `fix/` branch in that state. A release that cannot finish (red suite, failed checks, a conflict that needs a human) is **blocked**: the merge is aborted so `develop` stays clean, the phase goes back to `idle`, and the state keeps `release_status: blocked` with a `release_reason`. While blocked, only a fix ticket may start: `factory-manager` selects only `type:fix` issues (a human opens one if needed), `refine-ticket` accepts only those, and `guard-bash.sh` allows creating `fix/` branches but not `feature/` ones. The fix ticket's own release clears the flag. If the cause lies outside the repository, a human fixes it and retries with `/release`. `develop` never gets direct commits to work around a blocked release.

Never rewrite history on `main` or `develop`.
