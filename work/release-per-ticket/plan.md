# Plan: release-per-ticket

## Research summary
- **`guard-bash.sh`:** a PreToolUse hook (matcher `Bash`, `bash .claude/hooks/guard-bash.sh`, relative path, so cwd is the repo root).
  - It reads stdin JSON, takes `cmd` from `.tool_input.command`, and blocks with `block "<msg>"`, which prints `BLOCKED by workflow: ...` to stderr and exits 2.
  - `is_git "<sub>"` matches `(^|[;&|]\s*)git\s+<sub>` anywhere in the command, so it also matches chained commands. It has no end anchor.
  - Check order: commit (L35-52), merge on protected branch (L54-58), pull `--ff-only` (L60-64), push (L66-83), deleting feature/fix branches (L85-88), `gh pr merge` (L90-106), then `exit 0`.
  - Nothing currently checks branch creation.
  - The `--no-verify` check runs `-n\b` against the whole command, which is why a chained `grep -n` got blocked earlier. That's a known false positive and out of scope here.
- **`lib.sh` and `config.sh`:** `lib.sh` has `get_state`, `current_phase` (default `idle`), `current_ticket` and `current_branch`. `config.sh` sets `MAIN_BRANCH=main` and `DEVELOP_BRANCH=develop`. No hook uses `git -C`; they all rely on cwd.
- **Manual hook test** (from the repo root): `echo '{"tool_input":{"command":"<cmd>"}}' | bash .claude/hooks/guard-bash.sh; echo "exit=$?"`. Exit 0 means allowed. Exit 2 plus a stderr message means blocked.
- **Current state:** `git rev-list --count origin/main..origin/develop` is `1` (ticket #1), so the new gate blocks ticket-branch creation as soon as it lands. That's intended. This ticket creates no branches, and #23's own release (which takes #1 and #23 to `main`) clears it.
- **`release` skill today:** it has `disable-model-invocation: true` and runs "only when the user explicitly asks". Its precondition is phase `idle`/`done` with a clean tree. Its steps are: `releasing` → merge `origin/main` into `develop` with `--no-ff` (`chore(release): merge main into develop`) → suite and lint → push `develop` → `gh pr create --base main --head develop` → `gh pr checks --watch` → `gh pr merge --merge` → fetch → `idle`, with everything cleared. Its hard limits: no push to `main`, no force-push, no `--admin`.
- **`guard-bash.sh` already allows the release flow:** in phase `releasing` on `develop` it allows commit, merge and pull, it allows `git push origin develop`, and it requires `--merge` for `gh pr merge`.
- **Files to change:**
  - `.claude/rules/git.md` (L5-6, L28-33)
  - `.claude/rules/workflow.md` (table L8-15, rules list)
  - `.claude/skills/{release,factory-manager,refine-ticket}/SKILL.md`
  - `CLAUDE.md` L47
  - `README.md` around L52
  - `.claude/hooks/config.sh` L16-17

## Design decisions
- **Gate on remote-tracking refs, no fetch inside the hook.** It counts `origin/$MAIN_BRANCH..origin/$DEVELOP_BRANCH`, which keeps the hook fast and offline. `refine-ticket` runs `git fetch origin` in its precondition and `release` fetches at the end, so the refs are current when it matters. If the count fails (a ref is missing), the gate allows creation rather than blocking setups with no remote.
- **The gate only matches ticket-branch creation:**
  - `git switch -c|-C|--create (feature|fix)/…`
  - `git checkout -b|-B (feature|fix)/…`
  - `git branch (feature|fix)/…`, with the name as the first non-option argument
  - Plain `git switch feature/x`, `git branch --show-current` and `-d`/listing are never matched by this check.
- **Machine-readable release status.** `release` records `release_status` in the state file through `set-state.sh`: `waiting-checks` (resumable), `blocked` (needs a human), or empty when it finishes. `factory-manager` reads it instead of parsing report text, so it knows whether to resume or park. It's an extra state key; `set-state.sh` already accepts arbitrary keys, for example `pr`.
- **Resumable `release`.** If a `develop` → `main` PR is already open, it skips straight to the checks-and-merge step. Each step can safely be run again: a merge that's already done reports "Already up to date", and the push is a no-op.
- **Ticket ids in the release title** come from the scopes of the squash commits in `git log origin/main..origin/develop --no-merges --format=%s`, for example `feat(setup-env-settings): …`. That way a catch-up release lists every ticket it covers.
- **Parking a blocked release:** factory-manager tags the backlog line of the newest ticket in the release with `[[parked: release @ releasing]]`. With a ticket in state, that's the ticket; for a catch-up release, it's the last id in the title.
- **Commit types:** the hook change is `feat(release-per-ticket)` and the markdown changes are `docs(release-per-ticket)`. Each step is one commit. Per the ticket notes, there are no automated tests and no red–green cycle; each step's verification is listed below and repeated in final-review.

## Steps
- [x] 1. Add the branch-creation gate to `guard-bash.sh`, between the push checks and the branch-deletion check. Covers: AC7, AC8. Impl: `.claude/hooks/guard-bash.sh`, plus its header comment.
  - Verify by running the manual hook test for each case:
    - `git switch -c feature/x`, `git checkout -b fix/y`, `git branch feature/z` and `git switch develop && git switch -c feature/x` are **blocked** while the count is above 0.
    - `git switch feature/setup-layout-tailwind`, `git branch --show-current` and `git switch -c scratch` are **allowed**.
    - Point `origin/main` at a temporary fake ref equal to `origin/develop` (`git update-ref refs/remotes/origin/main origin/develop`, then restore it afterwards with `git fetch origin`) to show that creation is allowed when the count is 0.
  - Regression checks (AC8), using the same manual test:
    - `git commit --no-verify` and `git push origin main` are still blocked.
    - `gh pr merge 1 --squash` in phase `done` is still allowed.
  - Record the outputs in this step's notes.
  - Results (2026-10-01):
    - **Count 1 (real refs):** blocked `switch -c`, `switch -C`, `switch --create`, `checkout -b`, `branch feature/…` and the chained `switch develop && switch -c feature/x`. Allowed `git switch feature/setup-layout-tailwind`, `git branch --show-current`, `git switch -c scratch` and `git branch -a`.
    - **Count 0** (`origin/main` temporarily pointed at `origin/develop`, then restored to `eba71a4` and fetched): all 10 cases allowed.
    - **No origin refs** (a throwaway repo): `git switch -c feature/new` allowed.
    - **Regression** (throwaway repo with a fake state file):
      - Still blocked: `commit --no-verify`, `push origin main`, `push origin develop` in `done`, pushing in `implementing`, `pr merge --merge` in `done`, `pr merge --squash` in `releasing`, `pr merge` in `implementing`, `--delete-branch`, `branch -D feature/…`, and committing on `develop` in `idle`.
      - Still allowed: pushing the ticket branch and `pr merge --squash` in `done`; and in `releasing` on `develop`, `merge --no-ff origin/main`, `pull --ff-only`, `push origin develop`, `pr merge --merge` and `commit --no-edit`.
    - The scripts are in the session scratchpad (`gate-check.sh`, `regress-check.sh`).
- [x] 2. Update the `release` skill. Covers: AC3, AC4, AC5. Impl: `.claude/skills/release/SKILL.md`.
  - Remove `disable-model-invocation` and change the description.
  - Preconditions: `done` with the ticket PR merged, or `idle` with the count above 0. Run `git fetch origin` first.
  - Add a resume step for an open release PR.
  - Title: `chore(release): <yyyy-mm-dd> <ticket-ids>`.
  - Check handling: none means merge. Running means record `release_status waiting-checks`, report, stop. Failed, red, or a conflict needing a human means `release_status blocked`, report, stop. Success clears `release_status`.
  - Keep the hard limits.
  - Verify: read it against AC3–AC5.
- [x] 3. Update `factory-manager`. Covers: AC6. Impl: `.claude/skills/factory-manager/SKILL.md`.
  - Dispatch table:
    - `done`: close-out, then invoke `release`.
    - `releasing`: if `release_status` is `blocked`, park and report. Otherwise invoke `release`.
    - `idle`: if the count is above 0, invoke `release` (catch-up). Otherwise selection.
  - Close-out step 5 now hands off to `release`.
  - The park rule covers `release`.
  - Hard limits: remove "only when the user asks". Releases come only from `release`, and still at most one phase skill per call.
  - Verify: read it against AC6.
- [x] 4. Update `refine-ticket`'s precondition. Covers: AC9. Impl: `.claude/skills/refine-ticket/SKILL.md`. It runs `git fetch origin`. If `origin/develop` has commits `origin/main` lacks, it stops and points to `factory-manager`, which runs the release.
- [x] 5. Update the rules. Covers: AC1, AC2. Impl: `.claude/rules/git.md` (branch descriptions, plus the Releases section rewritten for per-ticket releases, merge commits and "next ticket only after main") and `.claude/rules/workflow.md` (the `done`/`releasing` rows in the table, plus the new rule line).
- [x] 6. Update the docs. Covers: AC10. Impl: `CLAUDE.md` (Workflow bullets), `README.md` (gitflow paragraph) and the `.claude/hooks/config.sh` comment. Verify: `grep -rn -i "only when\|when asked\|when the user asks" CLAUDE.md README.md .claude/rules .claude/skills .claude/hooks/config.sh` returns no release-related hits.

## Coverage
| AC | Steps |
|---|---|
| AC1 | 5 |
| AC2 | 5 |
| AC3 | 2 |
| AC4 | 2 |
| AC5 | 2 |
| AC6 | 3 |
| AC7 | 1 |
| AC8 | 1 |
| AC9 | 4 |
| AC10 | 6 |

## Review findings (review.md, 2026-10-01)
Verification for these steps is review-only too, plus re-running `gate-check.sh` and `regress-check.sh` (extended with the new cases) after each hook change.

- [x] 7. Recovery path for a blocked release (finding 1, high). When a release ends in `blocked`, it stops with phase `idle` (ticket fields cleared) and keeps `release_status: blocked`. While that flag is set, only a fix ticket may start:
  - `factory-manager` selects only issues labelled `type:fix`. If none exists, it reports that a human must open one.
  - `refine-ticket` accepts only `type:fix` issues.
  - `guard-bash.sh` allows creating `fix/` branches (not `feature/`) even though the count is above 0.

  The fix ticket's close-out runs `release` as usual, and a successful release clears the flag. A human can also fix the cause outside the repo (for example CI) and run `/release` to retry.

  Impl: `release/SKILL.md`, `factory-manager/SKILL.md`, `refine-ticket/SKILL.md`, `guard-bash.sh`, `git.md`, `workflow.md`. Commits on `develop` stay limited to the main-into-develop merge.
- [x] 8. Parked release tags (finding 2). The waiting check keeps a `[[parked: release @ ...]]` tag only while `release_status` is `blocked`. Otherwise it removes the tag and resumes. With step 7, a blocked release leaves the phase `idle`, so the tag is matched on the flag rather than the phase. Impl: `factory-manager/SKILL.md`.
- [x] 9. `release` resume and robustness (findings 3, 9, 10). Impl: `release/SKILL.md`.
  - In phase `releasing`, with no open release PR and a count of 0, go straight to the finish step.
  - On resume, take the ticket ids from the open PR's title.
  - Keep the ids in `git log` order, de-duplicated without sorting, so the newest is last.
  - Branch on `gh pr checks` output or exit code: no checks reported, 8 (pending), and other failures.
  - Treat merge conflicts in `src/` as `blocked`, because `guard-write.sh` prevents editing them in `releasing`.
- [x] 10. Resume a paused ticket (finding 4). `refine-ticket` detects a paused ticket: the `feature/<id>` or `fix/<id>` branch already exists, and its `work/<id>/ticket.md` records approval. In that case it:
  - switches to the branch,
  - merges `develop` into it (a normal merge on the ticket branch, so its history stays intact),
  - sets the phase to `refined` with the ticket fields,
  - moves the card to In Progress,
  - reports that the next step is `plan-ticket`, without re-interviewing.

  The gate allows this, because it's a switch and not a creation. Impl: `refine-ticket/SKILL.md`, plus a note in `git.md`.
- [x] 11. Tighten the hook for `releasing` (finding 5). In `releasing`:
  - `git merge` on `develop` is allowed only for `origin/main` (with or without `--no-ff`).
  - `git push` is allowed only as `git push origin develop`.
  - `gh pr merge <n>` is allowed only when `gh pr view <n> --json baseRefName,headRefName` shows `develop` → `main`.

  `set-state.sh phase releasing` is blocked unless the current phase is `done`, `idle` or `releasing`. Impl: `guard-bash.sh`. Verify: extended `regress-check.sh`. Note for the user: the `set-state.sh` auto-approval in `.claude/settings.json` is left unchanged.
- [x] 12. Push refspec checks (finding 6). The push-to-`main` check also matches `:refs/heads/main` and `main` before `;`, `&`, `|` or `)`. A `+<ref>:` refspec counts as a force push. Impl: `guard-bash.sh`. Verify: extended `regress-check.sh` with pushes to `develop:refs/heads/main`, `develop:main;true` and `+HEAD:develop`, all blocked.
- [x] 13. Enforce the release gate in the hook (finding 7). In `releasing`, before allowing `gh pr merge`, `guard-bash.sh` runs `$TEST_CMD` and `$LINT_CMD` and blocks on failure. `config.sh` gets `REQUIRE_CHECKS=false`, with a comment to flip it when `ci-tests` lands. The `release` skill treats "no checks reported" as `blocked` when `REQUIRE_CHECKS=true`. Impl: `guard-bash.sh`, `config.sh`, `release/SKILL.md`.
- [x] 14. Catch-up releases only promote reviewed work (finding 8). Before any release, `release` checks every non-merge commit in `origin/main..origin/develop`: its subject must end in `(#n)`, and `gh pr view n --json state,baseRefName` must show `MERGED` into `develop`. Otherwise it sets `release_status: blocked` and reports the offending commits. Impl: `release/SKILL.md`.
- [x] 15. Gate regex forms (finding 11). It matches options before the flag and the name (`switch -q -c`, `checkout -q -b`, `branch --no-track`), `--create=` forms, and `worktree add -b`. It doesn't match inside quoted strings (for example a commit message or a `--grep` pattern mentioning a branch command), and the remaining limits (`git -C`, quoted branch names) are documented in the hook's comment. Impl: `guard-bash.sh`. Verify: extended `gate-check.sh` with each form and the quoted-text case. This was hit for real during review: a heredoc that appended this plan was blocked because its text contained a branch command.
- Verification results after steps 7–16 (2026-10-01, all in the session scratchpad):
  - `gate-check.sh`: 23 cases, 14 blocked (every creation form, including option forms, `--create=`, `worktree add -b` and `git -C`) and 9 allowed (switching to existing branches, non-ticket names, and ticket-branch text inside quotes).
  - `blocked-check.sh`: 9 cases. While `release_status` is `blocked`, `fix/` creation is allowed (3 forms) and `feature/` creation is blocked. Without the flag, both are blocked.
  - `regress-check.sh`: 49 cases, 0 mismatches. That covers the unchanged blocks and allows, the narrowed `releasing` phase (step 11), the release gate (step 13) and the refspec pushes (step 12).
  - Deviation: step 8 dropped park tags for `release` entirely rather than keeping them while blocked. With step 7 a blocked release is `idle`, and its state flag is the waiting signal. AC6 was amended to match.
- [x] 16. Docs. `CLAUDE.md`, `README.md`, `git.md` and `workflow.md` describe the blocked-release recovery (fix tickets only), resuming a paused ticket, and `REQUIRE_CHECKS`. Impl: those files.
