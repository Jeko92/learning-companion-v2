---
name: release
description: Promote develop to main following the project's gitflow - merge main into develop with a conventional merge commit (resolving conflicts there), then open and merge a PR from develop into main. Only when the user explicitly asks for a release; never triggered by factory-manager.
disable-model-invocation: true
---

# Release develop to main

## Preconditions

Read `.claude/state/workflow.json`. The phase must be `idle` or `done`. If it is `done`, the ticket's PR must already be squash-merged into `develop` (close-out finished, `gh pr view <pr> --json state` is `MERGED`); otherwise stop and point to `factory-manager`. Any other phase means a ticket is in progress: stop and tell the user to finish it first.

`git status --porcelain` must show nothing except untracked files under `work/`.

## Steps

1. Start the release and update `develop`:

   ```bash
   bash .claude/hooks/set-state.sh phase releasing
   git switch develop && git pull --ff-only && git fetch origin main
   ```

2. Merge `main` into `develop` with a merge commit, so conflicts are resolved on `develop` and never on `main`:

   ```bash
   git merge --no-ff origin/main -m "chore(release): merge main into develop"
   ```

   - "Already up to date": nothing to do, continue.
   - Conflicts: resolve each file, keeping `develop`'s version of feature work unless `main` carries a change `develop` lacks; explain each non-trivial resolution to the user. Then `git add <files> && git commit --no-edit` (the commit gate runs the suite).

3. Run the full suite and lint (`$TEST_CMD`, `$LINT_CMD` from `.claude/hooks/config.sh`). On red, stop and report; do not push. Leave the phase at `releasing` so the user can decide.
4. `git push origin develop`.
5. Open the PR and merge it with a merge commit once checks are green:

   ```bash
   gh pr create --base main --head develop --title "chore(release): <yyyy-mm-dd>" --body "<list of ticket PRs merged into develop since the last release>"
   gh pr checks <pr> --watch
   gh pr merge <pr> --merge --subject "chore(release): <yyyy-mm-dd> (#<pr>)"
   ```

   If checks fail, stop and report; leave the PR open.
6. Finish:

   ```bash
   git fetch origin
   bash .claude/hooks/set-state.sh phase idle ticket "" issue "" branch "" pr "" current_step ""
   ```

   Report the release PR URL and the tickets it contains.

## Hard limits

- Never push to `main`, never merge into `main` locally; `main` changes only through the release PR.
- Never force-push and never rewrite history on `develop` or `main`.
- Never use `gh pr merge --admin` or bypass branch protection.
