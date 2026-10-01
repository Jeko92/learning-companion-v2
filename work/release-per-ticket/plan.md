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
- [ ] 4. Update `refine-ticket`'s precondition. Covers: AC9. Impl: `.claude/skills/refine-ticket/SKILL.md`. It runs `git fetch origin`. If `origin/develop` has commits `origin/main` lacks, it stops and points to `factory-manager`, which runs the release.
- [ ] 5. Update the rules. Covers: AC1, AC2. Impl: `.claude/rules/git.md` (branch descriptions, plus the Releases section rewritten for per-ticket releases, merge commits and "next ticket only after main") and `.claude/rules/workflow.md` (the `done`/`releasing` rows in the table, plus the new rule line).
- [ ] 6. Update the docs. Covers: AC10. Impl: `CLAUDE.md` (Workflow bullets), `README.md` (gitflow paragraph) and the `.claude/hooks/config.sh` comment. Verify: `grep -rn -i "only when\|when asked\|when the user asks" CLAUDE.md README.md .claude/rules .claude/skills .claude/hooks/config.sh` returns no release-related hits.

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
