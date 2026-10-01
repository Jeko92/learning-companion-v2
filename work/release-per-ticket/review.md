# Review: release-per-ticket

## Verdict: FAIL

All 10 acceptance criteria are met as written. Verification was review-only, at the user's choice. The hook was also exercised by hand: 10 gate cases and 18 regression cases, all as expected. The suite is green (21 tests) and lint is clean.

The FAIL comes from a high-severity design gap: a blocked release can't be recovered through the documented route. There are also several medium gaps in the resume logic and in how tightly the hooks hold the now-automatic release flow.

## Acceptance criteria
- AC1: `.claude/rules/git.md:5,7,26,28-35`. PASS.
- AC2: `.claude/rules/workflow.md:9,14-15,22`. PASS.
- AC3: `.claude/skills/release/SKILL.md:1-3,15-18`. PASS.
- AC4: `release/SKILL.md:53`. PASS.
- AC5: `release/SKILL.md:48-49,56-61`. PASS.
- AC6: `factory-manager/SKILL.md:30,35-36,46-47,55,65`. PASS.
- AC7: `guard-bash.sh:86-92`, checked by hand with `gate-check.sh`. PASS. The forms it misses are finding 11.
- AC8: checked by hand with `regress-check.sh` (10 blocked, 8 allowed, as before). PASS.
- AC9: `refine-ticket/SKILL.md:16`. PASS.
- AC10: `CLAUDE.md:43-47`, `README.md:50-56`, `config.sh:15-18`, and the "only when asked" grep is clean. PASS.

## Findings
1. **[high]** `release/SKILL.md:49`, `git.md:35`. The recovery route for a blocked release ("often a `fix/` ticket") can't be taken. While the phase is `releasing` with the count above 0, `refine-ticket` refuses (it needs a phase of `idle`/`done`, and the count must be 0), and `guard-bash.sh` blocks `git switch -c fix/...`. The only escapes are a manual state reset or committing straight onto `develop`, which the hook allows in `releasing` but `git.md:6` forbids. Recommendation: define an explicit recovery path that the skills, rules and hook all agree on.
2. **[medium]** `factory-manager/SKILL.md:24,36`. A `[[parked: release @ releasing]]` tag stays put as long as the phase is `releasing`. If a human then runs `/release` and it stops at `waiting-checks`, every later call reports "waiting" and never resumes. Recommendation: keep the tag on a release only while `release_status` is `blocked`.
3. **[medium]** `release/SKILL.md:18,25,68-73`. If the release PR is merged but the finish step fails, the phase stays `releasing` with an empty status and a count of 0. On resume, no PR is open, so steps 2–8 run again: `merge --no-ff origin/main` creates a new merge commit and a spurious, empty release follows. Recommendation: in `releasing`, with no open PR and a count of 0, go straight to the finish step.
4. **[medium]** Resuming the paused ticket #2 isn't defined anywhere. #2 is in Todo, so selection hands it to `refine-ticket`, which re-interviews and then `git switch -c feature/setup-layout-tailwind` fails because the branch exists. The branch also predates #23 and the release merge. Recommendation: `refine-ticket` should detect a paused ticket (existing branch plus `ticket.md` with recorded approval), switch to the branch, bring it up to date with `develop`, and continue at `plan-ticket` without re-interviewing.
5. **[medium]** `guard-bash.sh:34,56,77-78`, security. In phase `releasing` the hook allows any merge into `develop`, any commit on it, and any push except to `main`. `set-state.sh` is auto-approved in `.claude/settings.json`, so the phase can be set to `releasing` from anywhere, and now that `release` can be triggered automatically, unreviewed code could reach `develop` and then `main` without a human. Recommendation:
   - In `releasing`, allow only `git merge [--no-ff] origin/main` and `git push origin develop`.
   - Block `set-state.sh phase releasing` unless the current phase is `done`, `idle` or `releasing`.
   - Only allow `gh pr merge` in `releasing` for a PR from `develop` into `main`.
   - Settings are left unchanged: changing permissions is the user's call, not a review fix.
6. **[medium]** `guard-bash.sh:68,74`, security, pre-existing but now reachable. The check for pushes to `main` misses `develop:refs/heads/main` and `…:main;`, and the force-push check misses `+` refspecs. Recommendation: match `refs/heads/main` and `main` before shell metacharacters, and treat `+<ref>:` as a force push.
7. **[medium]** `release/SKILL.md:49,57,62`, security. The only gate before `main` is the suite plus lint in step 5. That's written in the skill but not enforced by any hook, and the "no checks reported" fallback has no end date. Recommendation:
   - In `releasing`, `guard-bash.sh` runs `$TEST_CMD` and `$LINT_CMD` before allowing `gh pr merge`.
   - Add `REQUIRE_CHECKS=false` to `config.sh`. When it is `true` (after `ci-tests`), a release PR with no checks reported is blocked instead of merged.
8. **[medium]** `factory-manager/SKILL.md:30`, `release/SKILL.md:17`, security. A catch-up release promotes whatever is on `origin/develop`, including commits that never went through final-review, such as merges made in the GitHub UI or pushes by someone else. Recommendation: before releasing, check that every non-merge commit in `origin/main..origin/develop` is the squash commit of a PR merged into `develop`, with a subject ending in `(#n)` and `gh pr view n` showing `MERGED` into `develop`. Otherwise set `blocked`.
9. **[low]** `release/SKILL.md`, several small issues:
   - On resume, step 8's `--subject` has no ticket ids. Take them from the open PR's title.
   - The ids are `sort -u`-ed, so "last id in the title" isn't the newest ticket. Keep `git log` order and de-duplicate.
   - `gh pr checks` exits 1 both when no checks exist and when one fails, and 8 when checks are pending. Branch on the output text or the exit code, not on success or failure.
10. **[low]** `guard-write.sh:23`, pre-existing. Edits under `src/` are blocked in `releasing`, so release conflicts in `src/` can't be resolved with the Edit tool. Recommendation: the release skill treats conflicts in `src/` as `blocked`, which leads to the recovery path from finding 1.
11. **[low]** `guard-bash.sh:86`. The gate regex misses forms with options or variants: `switch --create=feature/a`, `switch -q -c feature/a`, `checkout -q -b fix/a`, `branch --no-track feature/a`, `worktree add -b feature/a`. It also matches quoted text, for example `git log --grep "x; git branch feature/x"`. Recommendation: allow options before the flag and the name, cover `--create=` and `worktree add -b`, and document the limits that remain (`git -C`, quoted names).

Not adopted. These are recorded, and follow-up tickets can pick them up:
- **[low]** `gh api` can merge PRs or update refs without going through any check. That's pre-existing. GitHub branch protection on `main` and `develop` is the real control there, and it's out of scope (ticket Out of scope).
- **[low]** The gate uses tracking refs from the last fetch and fails open when refs are missing. Both are accepted by design (plan Design decisions). `refine-ticket` already fetches first.
- Changing the `set-state.sh` auto-approval in `.claude/settings.json` is the user's decision about permissions. It's mentioned in finding 5 and not changed here.

## Reviewed
commit aa295ed, 2026-10-01. Reviewers: `code-reviewer` (1 high, 3 medium, 6 low) and `security-reviewer` (0 high, 4 medium, 2 low). The security reviewer had no shell and read the current files instead of the diff. Main session: suite and lint, and a re-run of `gate-check.sh` and `regress-check.sh` on HEAD.
