#!/usr/bin/env bash
# Branch protection for main and develop: both require the CI checks, the
# job ids of .github/workflows/ci.yml, reported by GitHub Actions (app 15368,
# so no other app can report a check under the same name).
#
#   main:    PR required (0 approvals), admins bound, so it only changes
#            through the release PR once both checks have passed.
#   develop: no PR required and admins not bound, so the owner's release run
#            can still push its "merge main into develop" commit directly.
#            Ticket PRs need both checks to pass before they merge.
#   Both:    no force pushes, no deletion.
#
#   scripts/branch-protection.sh show              # the current protection
#   scripts/branch-protection.sh apply             # set it (needs repo admin)
#   scripts/branch-protection.sh desired <branch>  # the body apply sends
#
# src/config/tests/test_ci.py keeps the checks equal to the workflow's jobs.
set -euo pipefail

cd "$(dirname "$0")/.."
# GH_REPO, MAIN_BRANCH, DEVELOP_BRANCH
source .claude/hooks/config.sh

usage() {
  echo "usage: $0 show | apply | desired <$MAIN_BRANCH|$DEVELOP_BRANCH>" >&2
  exit 2
}

CHECKS='[
    {"context": "quality", "app_id": 15368},
    {"context": "docker-smoke", "app_id": 15368}
  ]'

desired() {
  case "$1" in
    "$MAIN_BRANCH")
      cat <<EOF
{
  "required_status_checks": {"strict": false, "checks": $CHECKS},
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
      ;;
    "$DEVELOP_BRANCH")
      cat <<EOF
{
  "required_status_checks": {"strict": false, "checks": $CHECKS},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
      ;;
    *) usage ;;
  esac
}

show() {
  local branch protection
  for branch in "$MAIN_BRANCH" "$DEVELOP_BRANCH"; do
    echo "$branch:"
    # On an error gh prints the response body to stdout and a one-line
    # reason ("Branch not protected (HTTP 404)") to stderr; keep the reason.
    if protection=$(gh api "repos/$GH_REPO/branches/$branch/protection" --jq '{
      required_checks: [.required_status_checks.checks[]? | "\(.context) (app \(.app_id))"],
      strict: .required_status_checks.strict,
      required_approving_review_count: .required_pull_request_reviews.required_approving_review_count,
      enforce_admins: .enforce_admins.enabled,
      allow_force_pushes: .allow_force_pushes.enabled,
      allow_deletions: .allow_deletions.enabled
    }'); then
      echo "  $protection"
    fi
  done
}

apply() {
  local branch
  for branch in "$MAIN_BRANCH" "$DEVELOP_BRANCH"; do
    desired "$branch" |
      gh api --method PUT "repos/$GH_REPO/branches/$branch/protection" --input - >/dev/null
    echo "applied $branch"
  done
  show
}

case "${1:-}" in
  show) show ;;
  apply) apply ;;
  desired) [ $# -eq 2 ] || usage; desired "$2" ;;
  *) usage ;;
esac
