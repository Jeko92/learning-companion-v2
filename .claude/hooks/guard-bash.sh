#!/usr/bin/env bash
# PreToolUse hook for Bash.
# Gates around git and gh, following the gitflow in .claude/rules/git.md:
# no commits or merges on protected branches (while releasing, develop only
# takes the main-into-develop merge and its push), the releasing phase can
# only be entered from done/idle, no commits with red tests, no --no-verify, no push before the
# review has passed, main only changes through a PR from develop, PR merge
# strategy per target, ticket branches are never deleted, and no new ticket
# branch is created while develop has commits that main lacks.
# Exit 2 blocks the command; stderr is fed back to Claude.
source "$(dirname "$0")/lib.sh"

input="$(cat)"
cmd="$(jq -r '.tool_input.command // empty' <<<"$input")"
[ -z "$cmd" ] && exit 0

is_git() {
  echo "$cmd" | grep -qE "(^|[;&|]\s*)git\s+$1"
}

is_gh() {
  echo "$cmd" | grep -qE "(^|[;&|]\s*)gh\s+$1"
}

block() {
  echo "BLOCKED by workflow: $1" >&2
  exit 2
}

phase="$(current_phase)"
branch="$(current_branch)"
on_protected=false
echo "$branch" | grep -qE "^($PROTECTED_BRANCHES)$" && on_protected=true
releasing_on_develop=false
[ "$phase" = "releasing" ] && [ "$branch" = "$DEVELOP_BRANCH" ] && releasing_on_develop=true

if echo "$cmd" | grep -qE "set-state\.sh(\s.*)?\sphase\s+releasing(\s|$)"; then
  case "$phase" in
    done|idle|releasing) ;;
    *) block "a release can only start after a ticket's close-out (phase 'done'), as a catch-up from 'idle', or resume from 'releasing'; current phase: $phase." ;;
  esac
fi

if is_git "commit"; then
  if echo "$cmd" | grep -qE -- "--no-verify|-n\b"; then
    block "'git commit --no-verify' is not allowed. Commit hooks are part of the quality gate."
  fi
  if $on_protected && ! $releasing_on_develop; then
    block "direct commits to '$branch' are not allowed. The refine-ticket skill creates a feature/ or fix/ branch from $DEVELOP_BRANCH; work there. Only the release skill may commit on $DEVELOP_BRANCH (the main-into-develop merge)."
  fi
  if $releasing_on_develop && ! git rev-parse -q --verify MERGE_HEAD >/dev/null; then
    block "while releasing, the only commit allowed on $DEVELOP_BRANCH is the main-into-develop merge, and no merge is in progress."
  fi
  if [ "$phase" = "idle" ]; then
    block "no ticket is in progress (phase: idle). Start with the refine-ticket skill before committing."
  fi
  if [ "$phase" = "implementing" ] || [ "$phase" = "reviewing" ] || [ "$phase" = "releasing" ]; then
    if [ -f "$TEST_GUARD_FILE" ]; then
      if ! $TEST_CMD >/dev/null 2>&1; then
        block "the test suite is red. Commits are only allowed on green. Finish the current TDD cycle first ($TEST_CMD)."
      fi
    fi
  fi
fi

if is_git "merge"; then
  if $on_protected && ! $releasing_on_develop; then
    block "merging into '$branch' locally is not allowed. Ticket branches reach $DEVELOP_BRANCH through a squash-merged PR, $DEVELOP_BRANCH reaches $MAIN_BRANCH through the release skill."
  fi
  if $releasing_on_develop \
     && ! echo "$cmd" | grep -qE "(^|[;&|]\s*)git\s+merge\s+((--no-ff|--no-commit)\s+)*origin/$MAIN_BRANCH(\s|$)|(^|[;&|]\s*)git\s+merge\s+--abort(\s|$)"; then
    block "while releasing, $DEVELOP_BRANCH only takes the merge of origin/$MAIN_BRANCH ('git merge --no-ff --no-commit origin/$MAIN_BRANCH') or 'git merge --abort'."
  fi
fi

if is_git "pull" && $on_protected; then
  if ! echo "$cmd" | grep -qE -- "--ff-only"; then
    block "pull on '$branch' must use --ff-only so no local merge commits land on a protected branch."
  fi
fi

if is_git "push"; then
  # A "+<ref>" refspec is a force push too.
  if echo "$cmd" | grep -qE -- "--force|-f\b|\s\+[^[:space:]]" \
     && { echo "$cmd" | grep -qE "($PROTECTED_BRANCHES)" || $on_protected; }; then
    block "force-pushing to a protected branch is not allowed."
  fi
  if echo "$cmd" | grep -qE -- "--delete|\s:[A-Za-z]"; then
    block "deleting remote branches is not allowed. feature/ and fix/ branches are kept so their per-step commit history stays visible."
  fi
  if echo "$cmd" | grep -qE "(\s|:|\+)(refs/heads/)?$MAIN_BRANCH(\s|$|[;&|)])" || [ "$branch" = "$MAIN_BRANCH" ]; then
    block "'$MAIN_BRANCH' only changes through a PR from $DEVELOP_BRANCH (release skill). Never push to it."
  fi
  if [ "$phase" = "releasing" ]; then
    echo "$cmd" | grep -qE "(^|[;&|]\s*)git\s+push\s+origin\s+$DEVELOP_BRANCH(\s*$|\s*[;&|])" \
      || block "while releasing, the only push allowed is 'git push origin $DEVELOP_BRANCH'."
  elif [ "$phase" != "done" ]; then
    block "pushing requires a passed final review (current phase: $phase). Run the final-review skill; it sets the phase to 'done' on a PASS verdict."
  elif $on_protected || echo "$cmd" | grep -qE "(\s|:)$DEVELOP_BRANCH(\s|$)"; then
    block "in phase 'done' only the ticket branch may be pushed. $DEVELOP_BRANCH is pushed only by the release skill."
  fi
fi

# Ticket-branch creation: switch -c/-C/--create[=], checkout -b/-B, worktree add -b/-B,
# branch [<opts>] [-c|-m <old>] <name>, each optionally after 'git -C <dir>' and with
# options before the flag. Quoted text is ignored (messages, --grep patterns), so a
# quoted branch name is not caught; heredoc bodies are not parsed either.
cmd_unquoted="$(echo "$cmd" | sed -E "s/\"[^\"]*\"//g; s/'[^']*'//g")"
opts='(-[^[:space:]]+\s+)*'
create_re="(^|[;&|]\s*)git\s+(-C\s+[^[:space:]]+\s+)?("
create_re+="switch\s+${opts}(-c|-C|--create|--force-create)(\s+|=)"
create_re+="|checkout\s+${opts}(-b|-B)\s+"
create_re+="|worktree\s+add\s+${opts}(-b|-B)\s+"
create_re+="|branch\s+((--no-track|--track(=[^[:space:]]+)?|-t|-f|--force|-q|--quiet)\s+)*((-c|-C|-m|-M|--copy|--move)\s+([^-[:space:]][^[:space:]]*\s+)?)?"
create_re+=")(feature|fix)/"
if echo "$cmd_unquoted" | grep -qE "$create_re"; then
  # Uses the remote-tracking refs from the last fetch; a missing ref counts as 0.
  ahead="$(git rev-list --count "origin/$MAIN_BRANCH..origin/$DEVELOP_BRANCH" 2>/dev/null)" || ahead=0
  # A blocked release is repaired by a fix ticket, so fix/ branches stay allowed then.
  if [ "$(get_state release_status)" = "blocked" ] \
     && echo "$cmd_unquoted" | grep -qE "[[:space:]=]fix/" && ! echo "$cmd_unquoted" | grep -qE "[[:space:]=]feature/"; then
    ahead=0
  fi
  if [ "${ahead:-0}" -gt 0 ]; then
    block "origin/$DEVELOP_BRANCH has $ahead commit(s) that origin/$MAIN_BRANCH lacks. Release first: factory-manager runs the release skill, which promotes $DEVELOP_BRANCH to $MAIN_BRANCH. The next ticket starts only once $MAIN_BRANCH has the last one."
  fi
fi

if is_git "branch" && echo "$cmd" | grep -qE -- "\s-(d|D)\b|--delete" \
   && echo "$cmd" | grep -qE "(feature|fix)/"; then
  block "feature/ and fix/ branches are kept after merging; do not delete them."
fi

if is_gh "pr\s+merge"; then
  if echo "$cmd" | grep -qE -- "--delete-branch|-d\b"; then
    block "do not delete the branch on merge; feature/ and fix/ branches are kept for their commit history."
  fi
  if echo "$cmd" | grep -qE -- "--admin"; then
    block "'gh pr merge --admin' bypasses branch protection and is not allowed."
  fi
  if [ "$phase" = "done" ]; then
    echo "$cmd" | grep -qE -- "--squash|-s\b" \
      || block "ticket PRs into $DEVELOP_BRANCH are squash-merged: use 'gh pr merge <n> --squash'."
  elif [ "$phase" = "releasing" ]; then
    echo "$cmd" | grep -qE -- "--merge|-m\b" \
      || block "the release PR from $DEVELOP_BRANCH into $MAIN_BRANCH is merged with a merge commit: use 'gh pr merge <n> --merge'."
    pr_num="$(echo "$cmd" | sed -nE 's/.*gh[[:space:]]+pr[[:space:]]+merge[[:space:]]+([0-9]+).*/\1/p')"
    [ -n "$pr_num" ] || block "while releasing, name the release PR explicitly: 'gh pr merge <n> --merge'."
    pr_refs="$(gh pr view "$pr_num" -R "$GH_REPO" --json baseRefName,headRefName --jq '.headRefName + ">" + .baseRefName' 2>/dev/null)"
    [ "$pr_refs" = "$DEVELOP_BRANCH>$MAIN_BRANCH" ] \
      || block "while releasing, only the release PR ($DEVELOP_BRANCH -> $MAIN_BRANCH) may be merged; PR #$pr_num is '${pr_refs:-unknown}'."
    # The release gate: main only gets what passes the suite and lint here.
    if [ -f "$TEST_GUARD_FILE" ]; then
      $TEST_CMD >/dev/null 2>&1 || block "the test suite is red; the release PR is not merged ($TEST_CMD)."
    fi
    $LINT_CMD >/dev/null 2>&1 || block "lint fails; the release PR is not merged ($LINT_CMD)."
    if [ "$REQUIRE_CHECKS" = "true" ] \
       && gh pr checks "$pr_num" -R "$GH_REPO" 2>&1 | grep -q "no checks reported"; then
      block "REQUIRE_CHECKS is on and release PR #$pr_num has no checks; it is not merged without CI."
    fi
  else
    block "PRs are merged only by factory-manager after a passed review (phase 'done') or by the release skill (phase 'releasing'); current phase: $phase."
  fi
fi

exit 0
