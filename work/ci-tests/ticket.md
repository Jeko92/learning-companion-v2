# DevOps: GitHub Actions runs lint and tests on every push
Issue: #21 · Branch: feature/ci-tests

## Story
As the person running this AI factory, I want every push and pull request checked by CI (lint, Django checks, migrations, tests and the Docker image), with the result shown on the PR and in the README, so that nothing reaches `develop` or `main` without the same quality gate the reviews use locally, and releases wait for that proof.

## Acceptance criteria

### Workflow
- [ ] AC1 A workflow in `.github/workflows/` runs on every `push` (any branch) and every `pull_request`. It cancels an older run of the same workflow and ref still in progress (`concurrency`), and its token is read-only (`permissions: contents: read`).
- [ ] AC2 A `quality` job on `ubuntu-latest` with Python 3.14 (`actions/setup-python`, pip cache keyed on the requirements files) installs `requirements-dev.txt`, then runs, each as its own named step:
  - `ruff check .`
  - `ruff format --check .`
  - `manage.py check`
  - `manage.py makemigrations --check --dry-run`
  - `manage.py test src`

  The two required keys are dummy values set in the workflow's `env`, never repository secrets: the tests never call the API. No `.env` file is created.
- [ ] AC3 A separate `docker-smoke` job runs `scripts/docker-smoke.sh` on every push and PR, in parallel with `quality`, and fails the workflow if any smoke check fails.
- [ ] AC4 Each job has a timeout, and actions are pinned to a major version (e.g. `@v7`), not a branch.
- [ ] AC5 A Django test pins these facts by reading the workflow file: the triggers, the read-only permissions, Python 3.14, the five `quality` commands, the smoke job's script and the dummy keys (no `secrets.` reference). It uses no new dependency.
- [ ] AC6 The workflow's first run on the ticket's PR is green for both jobs. `final-review` opens the PR, and `factory-manager` confirms the run with `gh pr checks` before the squash-merge.

### Factory and gates
- [ ] AC7 `REQUIRE_CHECKS` in `.claude/hooks/config.sh` is `"true"`, so a release PR (develop → main) with no, pending or failed checks is not merged (`guard-bash.sh` and the `release` skill already handle `"true"`). Ticket PRs keep today's rule: the user chose release PRs only for the hook.
- [ ] AC8 `factory-manager`'s close-out reads `gh pr checks` by exit code:
  - `0`: merge.
  - `8` (pending), or `1` with "no checks reported" (the run hasn't registered yet): wait and stop, so a later call retries.
  - `1` with a failed check: report and stop.

  This is a skill text change, verified by reading.
- [ ] AC9 GitHub branch protection requires the two CI checks (`quality` and `docker-smoke`):
  - On `main`, they are added to the existing protection, and its PR-review and admin-enforcement settings are kept.
  - On `develop`, a protection is created that requires the two checks on PRs, but still lets the `release` skill push its `chore(release): merge main into develop` commit directly. That means no required PR reviews, and checks enforced in a way that lets the owner push that commit (exact setting chosen in the plan).

  It is applied with `gh api` only after the user confirms in that session. A `gh api` read-back afterwards is recorded in `review.md`. The next release must still complete.

### Docs
- [ ] AC10 `README.md` shows a CI status badge for the workflow (on `main`) at the top, and a short "CI" section listing what runs.
- [ ] AC11 `CLAUDE.md` (Stack/Commands/Workflow) and `.claude/rules/git.md` describe:
  - the workflow and its two jobs;
  - `REQUIRE_CHECKS="true"`;
  - the `gh pr checks` exit-code handling;
  - the branch protection on `main` and `develop`, and how to change it.

  The old "flip it with the `ci-tests` ticket" notes are updated.

## Out of scope
- Deployment and publishing the Docker image
- Requiring checks for ticket PRs in `guard-bash.sh` (the user chose release PRs only). `develop`'s branch protection may still make GitHub wait for checks on ticket PRs (AC9).
- Required PR reviews on `develop`, and any other change to `main`'s existing review rules
- Dependabot, CodeQL, coverage reports, test matrices over several Python versions

## Notes
- Decisions made with the user in refinement (2026-10-04):
  - **Checks:** the full quality gate (`ruff check`, `ruff format --check`, `manage.py check`, `makemigrations --check`, tests), chosen over the issue's shorter list and over tests only.
  - **Docker:** a separate Docker smoke job on every push.
  - **Gating:** `REQUIRE_CHECKS` gates release PRs only.
  - **Branch protection:** included in this ticket, applied with `gh api` after the user confirms.
- Open questions from the issue:
  - `ruff format --check`: yes.
  - pip cache: yes (`actions/setup-python` `cache: pip`).
- Context found:
  - The suite needs only `SECRET_KEY`, `OPENAI_API_KEY`, Python 3.14 and `bash` (`test_docker.py` runs `bash -n`). There is no network, no Docker and no Tailwind build, and a missing `.env` is not an error.
  - `TEST_CMD`/`LINT_CMD` use `./.venv/bin/...`, so CI calls `python`/`ruff` directly.
  - `guard-bash.sh` gates only release PRs on checks.
  - Branch protection today:
    - `main` requires PR reviews (`enforce_admins: true`), has no required status checks, and disallows force pushes and deletions.
    - `develop` is not protected.
  - The release skill pushes its merge commit to `develop` directly, which a careless protection on `develop` would block (AC9).
- There is no YAML parser in the requirements, so the workflow test reads the file as text (AC5).
- CI can't run before the branch is pushed, and pushing is only allowed once `final-review` passes. So the first real run is on the ticket's PR (AC6). A red run stops `factory-manager` before the merge, and a human decides on a fix.
- Status check names come from the job names (`quality`, `docker-smoke`), which branch protection refers to. Renaming a job means updating the protection.
- Handout: `instructions/challenge.md` → "Containerize and add CI": "Add a CI workflow (GitHub Actions or similar) that installs dependencies and runs the framework's test runner on every push."
- **Approval:** the user approved the acceptance criteria (AC1–AC11) on 2026-10-04, including AC8 (the `factory-manager` exit-code handling).
