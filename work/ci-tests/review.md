# Review: ci-tests
## Verdict: FAIL

One high finding (the release can block on CI that hasn't registered yet, which puts AC9's "the next release must still complete" at risk) and one medium (cancelled required checks on protected branches). The fixes are plan steps 11–14.

## Acceptance criteria
- AC1 — covered by `WorkflowTriggerTests` (4 tests) — PASS
- AC2 — covered by `QualityJobTests` (5 tests) — PASS
- AC3 — covered by `DockerSmokeJobTests` (3 tests) — PASS
- AC4 — covered by `QualityJobTests.test_it_runs_on_ubuntu_with_a_timeout`, `DockerSmokeJobTests.test_it_runs_on_ubuntu_with_a_timeout`, `WorkflowHygieneTests.test_every_action_is_pinned_to_a_major_version` — PASS
- AC5 — covered by `src/config/tests/test_ci.py` (text only, no new dependency), incl. `WorkflowHygieneTests.test_no_repository_secret_is_used` — PASS
- AC6 — by design only provable on the ticket's PR (CI can't run before the push). Checked at close-out: `factory-manager` merges only on `gh pr checks` exit 0, and `develop`'s protection requires both checks — PENDING (PR)
- AC7 — covered by `FactoryGateTests.test_release_prs_require_passing_checks` — PASS
- AC8 — `.claude/skills/factory-manager/SKILL.md` step 3.2, verified by reading (exit 0 / 8 / 1 "no checks reported" / 1 failure) — PASS
- AC9 — desired state covered by `BranchProtectionScriptTests` (6 tests); applied after the user's confirmation; read-back below — PASS for the protection itself, but see finding 1 (the next release must still complete)
- AC10 — covered by `ReadmeBadgeTests` (2 tests) — PASS
- AC11 — `CLAUDE.md` (Stack, Commands, Layout, Workflow) and `.claude/rules/git.md` (ticket PRs, releases, new "Branch protection on GitHub" section), verified by reading — PASS

Suite: 602 tests OK; `ruff check` and `ruff format --check` clean; `makemigrations --check --dry-run`: no changes.

Branch protection read-back (`scripts/branch-protection.sh show`, 2026-10-04):
```
main:
  {"allow_deletions":false,"allow_force_pushes":false,"enforce_admins":true,"required_approving_review_count":0,"required_checks":["quality (app 15368)","docker-smoke (app 15368)"],"strict":false}
develop:
  {"allow_deletions":false,"allow_force_pushes":false,"enforce_admins":false,"required_approving_review_count":null,"required_checks":["quality (app 15368)","docker-smoke (app 15368)"],"strict":false}
```

## Findings
- [high] .claude/skills/release/SKILL.md:91 — Under `REQUIRE_CHECKS="true"`, step 7 blocks on "no checks reported", which `gh pr checks` can return in the seconds after the release PR is opened (the CI run hasn't registered yet). A blocked release only lets a `type:fix` ticket start, and AC9 requires the next release to complete. The step also still says "CI arrives with ticket `ci-tests`". `factory-manager` waits on the same output. — Plan step 11: treat the first "no checks reported" like pending (`waiting-checks`, stop), block only if it persists on the resumed call, and drop the stale sentence.
- [medium] .github/workflows/ci.yml:14-16 — `cancel-in-progress: true` also cancels push runs on `develop` and `main`. A cancelled required check on a protected branch's commit reads as failed. — Plan step 12: cancel only off `main`/`develop` (`${{ github.ref != 'refs/heads/main' && github.ref != 'refs/heads/develop' }}`). That keeps AC1's intent for ticket branches and PRs. Update the test and the docs.
- [low] .github/workflows/ci.yml:27,52 — `actions/checkout` persists the job token in `.git/config`, readable by every later step (PR test code, the smoke script). It is read-only and short-lived, and `.git` is not in the image. — Plan step 13: `persist-credentials: false` on both checkouts.
- [low] src/config/tests/test_ci.py (`QualityJobTests`) — The gate steps are compared on `name`/`run` only, so `if: false` or `continue-on-error: true` on a gate step would still pass. The install step's dict isn't pinned, and a missing `steps:` silently falls back. — Plan step 14: pin each step's exact dict and assert `steps:` exists.
- [low] .github/workflows/ci.yml — Actions are pinned to major tags, not SHAs (security reviewer). — Accepted: AC4 asks for a major-version pin. The token is read-only and the workflow uses no secrets. Revisit with Dependabot (out of scope).
- [low] requirements-dev.txt — `ruff>=0.16` is unpinned, so a new ruff release can turn CI red on an unchanged tree. — Accepted for now: same as the local hooks. A red run is visible and is fixed with a `type:fix` ticket.
- [low] scripts/branch-protection.sh `show` — exits 0 when a branch is unprotected. — Accepted: `show` is for reading, `apply` fails loudly through `set -e`.
- [info] scripts/branch-protection.sh — On `develop`, admins (the owner and the factory acting with the owner's `gh` credentials) can push without CI. This is the documented design for the release merge commit; `main` still requires both checks with admins bound.

## Reviewed
commit 1fc8709, 2026-10-04 (base ddb596d)
