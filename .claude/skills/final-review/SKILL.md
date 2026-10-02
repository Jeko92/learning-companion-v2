---
name: final-review
description: Run the final quality gate - independent code and security review agents plus an acceptance-criteria check - and on PASS unlock push and open the PR. Last phase of the development workflow. Use after tdd-implement, when the phase is reviewing.
---

# Final review

## Preconditions

Read `.claude/state/workflow.json`. The phase must be `reviewing`. All plan steps in `work/<id>/plan.md` must be ticked. If not, stop and point the user back to `tdd-implement`.

## Steps

1. **Fix the review base and collect the diff under review** (paths only in the main context; the reviewers read the contents themselves). The code reviewer reviews only new code, never earlier tickets or already-reviewed steps.
   - **First review of the ticket:** base = `git merge-base origin/develop HEAD`.
   - **Re-review after a FAIL:** base = the ticket's latest `docs(<id>): review findings` commit (`git log --format=%h --grep="docs(<id>): review findings" -1`). The scope is then only the fix steps.

   Then run `git diff --stat <base>..HEAD`.

   Also write the full diff to a temporary file **outside the repo**, so it never lands in a `work/` commit: `git diff <base>..HEAD > <scratchpad>/review-<id>.diff`. **Both reviewers read that file instead of whole files.**

   Note which plan steps are in scope: the whole plan on a first review, or the fix steps on a re-review.
2. **Verification fan-out.** Spawn both reviewers in parallel, each with its own lens and a clean context. Both review only new code: their agent definitions limit them to `<base>..HEAD`.
   - **Keep the briefs short.** Give each reviewer the ticket id, the review base, the changed files, the diff file's path and the plan steps in scope. Add the few risks worth targeting, if any.
   - **Don't ask them to review the whole branch again, or to run the full suite, lint or migration checks.** This skill runs those itself, in step 3.
   - `code-reviewer` agent: correctness, plan conformance, test quality. It runs on a cheaper model and is capped at about 5 targeted mutations, on a scratch copy of `src/`. On a re-review, also tell it to confirm the previous `review.md` findings are resolved.
   - `security-reviewer` agent: OWASP Top 10, authn/authz, secrets. On a re-review, also tell it to confirm the previous `review.md` security findings are resolved.

   The reviewers are read-only by design. They report terse findings; they do not fix anything.
3. **Acceptance check** (main session): for each acceptance criterion in `work/<id>/ticket.md`, name the test that proves it and confirm the test passes. Run the full suite, lint and `makemigrations --check` once more. This is the only place they run during review.
4. Write `work/<id>/review.md`:

   ```markdown
   # Review: <id>
   ## Verdict: PASS | FAIL
   ## Acceptance criteria
   - AC1 — covered by `<test>` — PASS
   ## Findings
   - [severity] file:line — description — recommendation
   ## Reviewed
   commit <sha>, <date>
   ```

   Verdict rules: any high-severity finding, any uncovered acceptance criterion, or a red suite means FAIL. Do not soften a FAIL into a PASS-with-remarks.

## On FAIL

Append the findings as new unchecked steps to `work/<id>/plan.md`, then:

```bash
bash .claude/hooks/set-state.sh phase implementing
git add work/<id> && git commit -m "docs(<id>): review findings"
```

Tell the user to rerun `tdd-implement` for the new steps. Do not fix findings inside the review.

## On PASS

`<branch>` and `<issue>` come from the state file; `<type>` is `fix` on a `fix/` branch, otherwise `feat`.

```bash
bash .claude/hooks/set-state.sh phase done
git add work/<id> && git commit -m "docs(<id>): review passed"
git push -u origin <branch>
gh pr create --base develop --head <branch> --title "<type>(<id>): <issue title>" --body "<story, acceptance criteria, Closes #<issue>, reference to work/<id>/review.md>"
bash .claude/hooks/set-state.sh pr <pr number>
```

Report the PR URL to the user. Do not merge it here: `factory-manager` squash-merges it into `develop` once checks are green and closes out the ticket. The push gate only opens in phase `done`, so a push that gets blocked means the state transition did not happen — check, don't force.
