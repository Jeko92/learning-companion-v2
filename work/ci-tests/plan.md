# Plan: ci-tests

## Research summary
- **What the suite needs:** only `SECRET_KEY`, `OPENAI_API_KEY`, Python 3.14 and `bash`. `config/tests/test_docker.py` runs `bash -n`, and the executable bits of `scripts/docker-smoke.sh` and `docker/entrypoint.sh` are tracked as 100755. There is no network, Docker or Tailwind build, a missing `.env` is not an error, and no test reads the built CSS.
- **The smoke script** needs Docker, bash, curl, `sed` and network access (the build downloads Tailwind). GitHub's `ubuntu-latest` runners have all of them. It uses unique names and a random port, and cleans up after itself.
- **Hook and skill commands:** `TEST_CMD`/`LINT_CMD` in `.claude/hooks/config.sh` use `./.venv/bin/...`, so CI calls `python` and `ruff` directly.
- **`REQUIRE_CHECKS="false"` today.** `guard-bash.sh` gates only release PRs (phase `releasing`): it re-runs the suite and lint, and when `REQUIRE_CHECKS` isn't `"false"` it blocks unless `gh pr checks` exits 0. The `release` skill (step 7) already reads exit codes: 0 means passed, 8 means pending (`waiting-checks`), 1 with "no checks reported" means block unless `REQUIRE_CHECKS` is `"false"`, and 1 with a failure means block.
- **`factory-manager` close-out** (step 3.2) only says "if checks are still running … stop; if any check failed … stop". It can't tell "no checks reported" (exit 1) from a failed check.
- **Branch protection (read through `gh api`):**
  - `main`: required PR reviews with `required_approving_review_count: 0`, `enforce_admins: true`, no required status checks, no force pushes, no deletions, no signatures, no conversation resolution, no lock.
  - `develop`: not protected.
  - The `release` skill pushes `chore(release): merge main into develop` straight to `develop`, and the owner (admin) runs the factory.
  - `guard-bash.sh` doesn't check `gh api` calls (a known gap in its header), so the protection change is gated by the user's confirmation.
- **Tests:**
  - Repo-root files are read through `settings.BASE_DIR.parent / ...` in `SimpleTestCase`s (`config/tests/test_docker.py` is the model).
  - There is no YAML parser in the requirements, so the workflow test reads the text.
  - Names are behaviour sentences.

## Design decisions
1. **One workflow file, `.github/workflows/ci.yml`, named `CI`:**
   - Triggers: `on: push` (all branches) and `pull_request`.
   - `permissions: contents: read`.
   - `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }`.
2. **Two jobs whose ids are the check names:** `quality` and `docker-smoke`, without a `name:` key, so the status check contexts are exactly `quality` and `docker-smoke`. They don't use `needs`, so they run in parallel.
   - **`quality`** (timeout 15 min) uses `actions/checkout@v4` and `actions/setup-python@v5` (`python-version: "3.14"`, `cache: pip`, `cache-dependency-path: requirements*.txt`), runs `pip install -r requirements-dev.txt`, then one named step per command:
     - `ruff check .`
     - `ruff format --check .`
     - `python src/manage.py check`
     - `python src/manage.py makemigrations --check --dry-run`
     - `python src/manage.py test src`
     
     Job-level `env` sets `SECRET_KEY: ci-dummy-secret-key` and `OPENAI_API_KEY: sk-dummy`, never `secrets.*`.
   - **`docker-smoke`** (timeout 20 min) uses `actions/checkout@v4` and runs `scripts/docker-smoke.sh`.
3. **The workflow test parses the jobs from the text, without YAML.** `src/config/tests/test_ci.py` splits the file into its top-level keys and its job blocks by indentation, then asserts the facts per job. Exact lines are checked only where they are the contract: the commands, the action versions, the dummy keys.
4. **Branch protection is a committed, reviewable script.** `scripts/branch-protection.sh show|apply` holds the desired state, so it can be re-applied and is documented.
   - `main`: one `PUT` that keeps today's settings (PR required with 0 approvals, `enforce_admins: true`, no force pushes or deletions) and adds `required_status_checks: {strict: false, checks: [quality, docker-smoke]}`, bound to the GitHub Actions app (`app_id` 15368), so another app can't report a check under the same name.
   - `develop`: a new protection with the same required checks (`strict: false`), no required reviews and `enforce_admins: false`, so the owner's `release` push of the main-into-develop merge commit still works. Admins can therefore bypass on `develop`, which is documented. The factory still waits for the checks itself (AC7/AC8).
   - No force pushes and no deletions on either branch.
   - `show` prints the read-back (required contexts, reviews, `enforce_admins`) for `review.md`.
   - A test keeps the script's check names equal to the workflow's job ids, so renaming a job can't silently orphan the protection.
5. **The protection is applied in its plan step, after the workflow file exists, and only after the user confirms in that session.** Requiring checks that GitHub hasn't seen yet is allowed; they show as "expected". The ticket's own PR into `develop` then runs CI and has to pass, which also proves AC6.
6. **`factory-manager`'s close-out reads `gh pr checks` by exit code,** worded like the `release` skill's step 7. "No checks reported" means "not registered yet: wait", because CI now runs on every PR. This is a skill text change verified by reading; no test.
7. **`REQUIRE_CHECKS="true"`** in `.claude/hooks/config.sh`, with its comment updated. A test in `test_ci.py` reads `config.sh`, so the gate can't quietly be switched back off.

## Steps
- [x] 1. The workflow runs on every push and pull request, with read-only permissions, and cancels an older run of the same ref. — test: `src/config/tests/test_ci.py` (`WorkflowTriggerTests`: the file exists, `name: CI`, `on` has `push` and `pull_request` without branch filters, `permissions: contents: read`, a `concurrency` group on workflow + ref with `cancel-in-progress: true`) — impl: `.github/workflows/ci.yml` — covers: AC1
- [ ] 2. A `quality` job runs the full gate on Python 3.14: `actions/setup-python@v5` with `python-version: "3.14"`, pip cache keyed on `requirements*.txt`, `pip install -r requirements-dev.txt`, then five named steps running exactly the five commands in this order, with the dummy `SECRET_KEY`/`OPENAI_API_KEY` in the job's `env` and a `timeout-minutes`. — test: `src/config/tests/test_ci.py` (`QualityJobTests`) — impl: `.github/workflows/ci.yml` — covers: AC2, AC4
- [ ] 3. A `docker-smoke` job runs `scripts/docker-smoke.sh`, with no `needs` (so it runs in parallel) and a `timeout-minutes`. — test: `src/config/tests/test_ci.py` (`DockerSmokeJobTests`) — impl: `.github/workflows/ci.yml` — covers: AC3, AC4
- [ ] 4. Every `uses:` pins a major version (`@v<N>`), not a branch or `@main`. The file never references `secrets.`, and the job ids are exactly `quality` and `docker-smoke` (the check names). — test: `src/config/tests/test_ci.py` (`WorkflowHygieneTests`) — impl: `.github/workflows/ci.yml` if needed — covers: AC4, AC5
- [ ] 5. Release PRs need passing CI checks: `REQUIRE_CHECKS="true"` in `.claude/hooks/config.sh`, with the comment updated (CI exists; a release PR with no, pending or failed checks is blocked). — test: `src/config/tests/test_ci.py` (`FactoryGateTests`: `config.sh` sets `REQUIRE_CHECKS="true"`) — impl: `.claude/hooks/config.sh` — covers: AC7
- [ ] 6. `factory-manager`'s close-out step 3.2 reads `gh pr checks` by exit code:
  - `0`: merge.
  - `8`, or `1` with "no checks reported": report "waiting for checks on PR #<n>" and stop.
  - `1` with a failure: report the failed checks and stop.
  
  It is worded consistently with `release` step 7. — test: none (skill text, verified by reading in review) — impl: `.claude/skills/factory-manager/SKILL.md` — covers: AC8
- [ ] 7. `scripts/branch-protection.sh` (`show` / `apply`) holds the protection of decision 4. — test: `src/config/tests/test_ci.py` (`BranchProtectionScriptTests`: the script is executable and passes `bash -n`, requires exactly the workflow's job ids as checks, keeps `enforce_admins` true on `main` and false on `develop`, and never sets `allow_force_pushes`/`allow_deletions` to true) — impl: `scripts/branch-protection.sh` — covers: AC9 (the desired state, tested)
- [ ] 8. **Apply the protection (outward-facing; ask the user to confirm first).** Show the user `scripts/branch-protection.sh show` (before), then run `apply` only on their explicit yes in that session, then `show` again. Record both read-backs in the step's commit body. No source change. — test: the read-back (`main` and `develop` require `quality` and `docker-smoke`; `main` still has PR reviews and `enforce_admins: true`; `develop` has `enforce_admins: false` and no reviews) — impl: GitHub settings through `gh api` — covers: AC9
- [ ] 9. The README shows the CI status badge at the top: the workflow's `badge.svg?branch=main` linking to the workflow's runs. It also gains a short "CI" section: the two jobs, what each runs, the required checks on `main` and `develop`, and how to run the same gate locally. — test: `src/config/tests/test_ci.py` (`ReadmeBadgeTests`: the badge URL points at `.github/workflows/ci.yml` on `main`, near the top) — impl: `README.md` — covers: AC10
- [ ] 10. Documentation:
  - **`CLAUDE.md`:**
    - Stack: the workflow and its jobs, and the dummy keys.
    - Commands: `scripts/branch-protection.sh show|apply`, and `gh run list`/`gh pr checks` to follow CI.
    - Workflow: `REQUIRE_CHECKS="true"`, the exit-code handling, the protection, and admins bypassing on `develop` for the release push. The "Flip it to true with the ci-tests ticket" note is replaced.
    - Layout: `.github/workflows/`.
  - **`.claude/rules/git.md`:** the release section now says CI exists and `REQUIRE_CHECKS` is on, and the branch protection is described.
  
  No `src/` change. — test: none (docs) — impl: `CLAUDE.md`, `.claude/rules/git.md` — covers: AC11

## Coverage
| AC | Steps |
|---|---|
| AC1 triggers, permissions, concurrency | 1 |
| AC2 `quality` job | 2 |
| AC3 `docker-smoke` job | 3 |
| AC4 timeouts, pinned actions | 2, 3, 4 |
| AC5 workflow test, no new dependency | 1–4 (`test_ci.py`, text only) |
| AC6 first run green | proven by the ticket's own PR: `final-review` opens it, and `factory-manager`'s close-out (step 6's exit-code rules) waits for both checks before the squash-merge; `develop`'s protection (step 8) also requires them |
| AC7 `REQUIRE_CHECKS` | 5 |
| AC8 `factory-manager` exit codes | 6 |
| AC9 branch protection | 7 (desired state, tested), 8 (applied after confirmation, read-back recorded) |
| AC10 README badge and CI section | 9 |
| AC11 docs | 10 |
