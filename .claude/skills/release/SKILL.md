---
name: release
description: Promote develop to main following the project's gitflow - merge main into develop with a conventional merge commit (resolving conflicts there), then open and merge a PR from develop into main. Runs after every ticket - factory-manager triggers it once a ticket PR is squash-merged into develop, and as a catch-up whenever develop has commits main lacks. The next ticket only starts once this has finished.
---

# Release develop to main

Every ticket is released on its own: once its PR is squash-merged into `develop`, this skill promotes `develop` to `main`, and no new ticket branch can be cut until it has finished (`guard-bash.sh` blocks `feature/` and `fix/` branch creation while `origin/develop` is ahead of `origin/main`).

The skill is resumable. It records its progress as `release_status` in `.claude/state/workflow.json`: `waiting-checks` (a later call resumes), `blocked` (a human must decide), or empty once finished. `factory-manager` reads that field to decide whether to resume or park.

## Preconditions

1. `git fetch origin`, then count what needs releasing: `git rev-list --count origin/main..origin/develop`.
2. Read `.claude/state/workflow.json`. The phase must be one of:
   - `done`: the ticket's PR must already be squash-merged into `develop` (close-out finished, `gh pr view <pr> --json state` is `MERGED`). Otherwise stop and point to `factory-manager`.
   - `idle`: catch-up release. If the count is `0` there is nothing to release; report that and stop without changing state.
   - `releasing`: resume an earlier run (see step 1).

   Any other phase means a ticket is in progress: stop and tell the user to finish it first.
3. `git status --porcelain` must show nothing except untracked files under `work/`.

## Steps

1. **Resume check.** `gh pr list --base main --head develop --state open --json number`. If a release PR is already open, make sure the phase is `releasing` (`bash .claude/hooks/set-state.sh phase releasing`) and go straight to step 7.
2. **Collect the ticket ids** in this release from the conventional-commit scopes of the squash commits:

   ```bash
   git log origin/main..origin/develop --no-merges --format=%s | sed -nE 's/^[a-z]+\(([^)]+)\).*/\1/p' | grep -vx release | sort -u
   ```

   One id for a normal per-ticket release; several for a catch-up release.
3. **Start the release and update `develop`:**

   ```bash
   bash .claude/hooks/set-state.sh phase releasing release_status ""
   git switch develop && git pull --ff-only
   ```

4. **Merge `main` into `develop` with a merge commit**, so conflicts are resolved on `develop` and never on `main`:

   ```bash
   git merge --no-ff origin/main -m "chore(release): merge main into develop"
   ```

   - "Already up to date": nothing to do, continue.
   - Conflicts: resolve each file, keeping `develop`'s version of feature work unless `main` carries a change `develop` lacks; explain each non-trivial resolution to the user. Then `git add <files> && git commit --no-edit` (the commit gate runs the suite).
   - If a conflict can't be resolved with confidence: `git merge --abort`, `bash .claude/hooks/set-state.sh release_status blocked`, report the conflicting files and stop.
5. **Run the full suite and lint** (`$TEST_CMD`, `$LINT_CMD` from `.claude/hooks/config.sh`). On red: `bash .claude/hooks/set-state.sh release_status blocked`, report, and stop. Do not push; the phase stays `releasing` so a human can decide (often a `fix/` ticket).
6. `git push origin develop`, then open the release PR:

   ```bash
   gh pr create --base main --head develop --title "chore(release): <yyyy-mm-dd> <ticket-ids>" --body "<ticket PRs merged into develop since the last release, one line each>"
   ```

7. **Checks.** `gh pr checks <pr>`:
   - "no checks reported": nothing can fail yet (CI arrives with ticket `ci-tests`); the local suite from step 5 was the gate. Continue.
   - Checks still running: `bash .claude/hooks/set-state.sh release_status waiting-checks`, report "waiting for checks on release PR #<pr>", and stop. Leave the PR open; a later call resumes at step 1.
   - Any check failed: `bash .claude/hooks/set-state.sh release_status blocked`, report it, and stop. Leave the PR open.

   Also `gh pr view <pr> --json mergeable`: if `CONFLICTING`, set `release_status blocked`, report, and stop.
8. **Merge with a merge commit:**

   ```bash
   gh pr merge <pr> --merge --subject "chore(release): <yyyy-mm-dd> <ticket-ids> (#<pr>)"
   ```

9. **Finish:**

   ```bash
   git fetch origin
   git rev-list --count origin/main..origin/develop   # must be 0
   bash .claude/hooks/set-state.sh phase idle ticket "" issue "" branch "" pr "" current_step "" release_status ""
   ```

   Report the release PR URL and the tickets it contains. The next ticket can now start.

## Hard limits

- Never push to `main`, never merge into `main` locally; `main` changes only through the release PR.
- Never force-push and never rewrite history on `develop` or `main`.
- Never use `gh pr merge --admin` or bypass branch protection.
- Never merge a release PR with failing checks or a red local suite.
