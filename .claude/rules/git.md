# Git conventions (gitflow)

## Branches

- `main` is the release branch. It is protected and only changes through a PR from `develop`, created and merged by the `release` skill. Never commit, merge or push to `main` directly.
- `develop` is the integration branch. It only receives squash-merged PRs from ticket branches, plus the main-into-develop merge commit made by the `release` skill. Never commit to it directly.
- Every ticket gets its own branch cut from the latest `develop`: `feature/<ticket-id>` for features, `fix/<ticket-id>` for bug tickets (issue labelled `type:fix`). The `refine-ticket` skill creates it; the branch name is recorded as `branch` in the state file.
- Ticket branches are never deleted, locally or on GitHub. `develop` only gets one squash commit per ticket, so the ticket branch is where its per-step commit history stays visible.

All of the above is enforced by `.claude/hooks/guard-bash.sh`.

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
- `factory-manager` squash-merges it (`gh pr merge <n> --squash`, never `--delete-branch`) once checks are green, closes the issue, moves the card to Done, then fast-forwards local `develop` (`git pull --ff-only`). The next ticket branch is cut from that updated `develop`.

## Releases (develop -> main)

Run by the `release` skill, only when the user asks for a release:

1. On `develop`, merge `origin/main` into it with a merge commit, `chore(release): merge main into develop`. Resolve conflicts there, run the suite, push `develop`.
2. Open a PR `develop -> main` titled `chore(release): <yyyy-mm-dd>` and merge it with a merge commit (`gh pr merge <n> --merge`).

Never rewrite history on `main` or `develop`.
