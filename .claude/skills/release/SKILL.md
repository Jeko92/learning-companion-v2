---
name: release
description: Promote develop to main following the project's gitflow - merge main into develop with a conventional merge commit (resolving conflicts there), then open and merge a PR from develop into main. Runs after every ticket - factory-manager triggers it once a ticket PR is squash-merged into develop, and as a catch-up whenever develop has commits main lacks. The next ticket only starts once this has finished.
---

# Release develop to main

Every ticket is released on its own: once its PR is squash-merged into `develop`, this skill promotes `develop` to `main`, and no new ticket branch can be cut until it has finished (`guard-bash.sh` blocks `feature/` and `fix/` branch creation while `origin/develop` is ahead of `origin/main`).

The skill is resumable. It records its progress as `release_status` in `.claude/state/workflow.json`: `waiting-checks` (a later call resumes), `blocked` (the release cannot finish; see "Blocked releases"), or empty once finished. `factory-manager` reads that field to decide what happens next.

## Blocked releases

Whenever a step below says **block**, do this and stop:

```bash
git merge --abort 2>/dev/null; git switch develop
bash .claude/hooks/set-state.sh phase idle ticket "" issue "" branch "" pr "" current_step "" release_status blocked release_reason "<one line: what failed>"
```

Leave an open release PR open. Report the reason and the way out:

- A **fix ticket** repairs `develop`. While `release_status` is `blocked`, `factory-manager` selects only `type:fix` issues, `refine-ticket` accepts only those, and `guard-bash.sh` allows creating `fix/` branches (never `feature/`) although `develop` is ahead of `main`. A human opens the `type:fix` issue if none exists. If the cause comes from `main`, the fix ticket may merge `origin/main` into its own branch. When the fix ticket closes out, its release runs as usual and clears the flag.
- If the cause is outside the repository (for example a CI outage), a human fixes it and runs `/release` to retry.

`develop` never receives commits beyond the main-into-develop merge, so the merge is only committed once the suite and lint are green (step 4).

## Preconditions

1. `git fetch origin`, then count what needs releasing: `git rev-list --count origin/main..origin/develop`.
2. Read `.claude/state/workflow.json`. The phase must be one of:
   - `done`: the ticket's PR must already be squash-merged into `develop` (close-out finished, `gh pr view <pr> --json state` is `MERGED`). Otherwise stop and point to `factory-manager`.
   - `idle`: catch-up release. If the count is `0` there is nothing to release; report that and stop without changing state. If `release_status` is `blocked`, only run when a human explicitly asked for a retry (`/release`); `factory-manager` never triggers it in that state.
   - `releasing`: resume an earlier run (see step 1).

   Any other phase means a ticket is in progress: stop and tell the user to finish it first.
3. `git status --porcelain` must show nothing except untracked files under `work/`.

## Steps

1. **Resume check.** `gh pr list --base main --head develop --state open --json number,title`.
   - A release PR is already open: make sure the phase is `releasing` (`bash .claude/hooks/set-state.sh phase releasing`), take the ticket ids from that PR's title (everything after the date in `chore(release): <yyyy-mm-dd> <ticket-ids>`), and go straight to step 7.
   - No open PR, the phase is `releasing` and the count is `0`: an earlier run already merged the release PR but did not finish. Go straight to step 9; do not merge `main` into `develop` again.
2. **Collect the ticket ids** in this release from the conventional-commit scopes of the squash commits, in the order they were merged (oldest first, each id once):

   ```bash
   git log --reverse origin/main..origin/develop --no-merges --format=%s | sed -nE 's/^[a-z]+\(([^)]+)\).*/\1/p' | grep -vx release | awk '!seen[$0]++'
   ```

   One id for a normal per-ticket release; several for a catch-up release.
3. **Start the release and update `develop`:**

   ```bash
   bash .claude/hooks/set-state.sh phase releasing release_status ""
   git switch develop && git pull --ff-only
   ```

4. **Merge `main` into `develop` with a merge commit**, so conflicts are resolved on `develop` and never on `main`. Stage it first, and commit only on green:

   ```bash
   git merge --no-ff --no-commit origin/main
   ```

   - "Already up to date": nothing to merge; skip to step 6.
   - Conflicts: resolve each file, keeping `develop`'s version of feature work unless `main` carries a change `develop` lacks; explain each non-trivial resolution to the user, then `git add <files>`. If a conflict can't be resolved with confidence, **block** with the conflicting files as the reason. Conflicts in files under `src/` always **block**: `guard-write.sh` keeps source write-protected outside `implementing`, so they are resolved by a fix ticket, not here.
5. **Gate, then commit.** Run the full suite and lint (`$TEST_CMD`, `$LINT_CMD` from `.claude/hooks/config.sh`) on the staged merge. On red, **block** (the merge is aborted, so `develop` stays clean). On green:

   ```bash
   git commit -m "chore(release): merge main into develop"
   ```

6. `git push origin develop`, then open the release PR:

   ```bash
   gh pr create --base main --head develop --title "chore(release): <yyyy-mm-dd> <ticket-ids>" --body "<ticket PRs merged into develop since the last release, one line each>"
   ```

7. **Checks.** `gh pr checks <pr>`. Decide by exit code and output, not by success or failure alone: exit `0` means all checks passed, exit `8` means checks are still pending, and exit `1` means either a check failed or there are no checks at all (output contains "no checks reported").
   - "no checks reported": if `REQUIRE_CHECKS` in `.claude/hooks/config.sh` is `"true"`, **block** (CI is expected but did not run). Otherwise nothing can fail yet (CI arrives with ticket `ci-tests`); the local suite and lint are the gate, and `guard-bash.sh` re-runs both right before `gh pr merge`. Continue.
   - All checks passed (exit `0`): continue.
   - Checks still running (exit `8`): `bash .claude/hooks/set-state.sh release_status waiting-checks`, report "waiting for checks on release PR #<pr>", and stop. Leave the PR open; a later call resumes at step 1.
   - Any check failed: **block** with the failed checks as the reason. The PR stays open.

   Also `gh pr view <pr> --json mergeable`: if `CONFLICTING`, **block**.
8. **Merge with a merge commit:**

   ```bash
   gh pr merge <pr> --merge --subject "chore(release): <yyyy-mm-dd> <ticket-ids> (#<pr>)"
   ```

9. **Finish:**

   ```bash
   git fetch origin
   git rev-list --count origin/main..origin/develop   # must be 0
   bash .claude/hooks/set-state.sh phase idle ticket "" issue "" branch "" pr "" current_step "" release_status "" release_reason ""
   ```

   Report the release PR URL and the tickets it contains. The next ticket can now start; a `blocked` flag from an earlier attempt is now cleared.

## Hard limits

- Never push to `main`, never merge into `main` locally; `main` changes only through the release PR.
- Never force-push and never rewrite history on `develop` or `main`.
- Never use `gh pr merge --admin` or bypass branch protection.
- Never merge a release PR with failing checks or a red local suite.
