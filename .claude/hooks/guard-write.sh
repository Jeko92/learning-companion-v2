#!/usr/bin/env bash
# PreToolUse hook for Write|Edit|MultiEdit.
# Gate: production and test code may only change during the implementing phase.
# Workflow artifacts (work/, .claude/, markdown) are always allowed, except the
# state file under .claude/state/, which only set-state.sh may change.
# Exit 2 blocks the tool call; stderr is fed back to Claude.
source "$(dirname "$0")/lib.sh"

input="$(cat)"
file="$(jq -r '.tool_input.file_path // empty' <<<"$input")"
[ -z "$file" ] && exit 0

rel="${file#"$PWD"/}"

# The workflow state only changes through set-state.sh (whose transitions guard-bash.sh checks).
case "$rel" in
  .claude/state/*)
    echo "BLOCKED by workflow: '$rel' is the workflow state; change it only with 'bash .claude/hooks/set-state.sh', exactly where a skill says so." >&2
    exit 2 ;;
esac

case "$rel" in
  work/*|.claude/*|*.md) exit 0 ;;
esac

if ! echo "$rel" | grep -qE "^($SOURCE_DIRS)/"; then
  exit 0
fi

phase="$(current_phase)"
if [ "$phase" = "implementing" ]; then
  exit 0
fi

echo "BLOCKED by workflow: '$rel' is source code and the current phase is '$phase'. Source files may only be modified in the 'implementing' phase. Run the skills in order: refine-ticket -> plan-ticket -> tdd-implement. Review findings go back through tdd-implement, they are not fixed during review." >&2
exit 2
