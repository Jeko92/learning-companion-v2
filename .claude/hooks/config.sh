# Project-specific configuration for the workflow hooks.
# Adapt these to your project. Everything else should work unchanged.

TEST_CMD="./.venv/bin/python src/manage.py test src --verbosity 0"
LINT_CMD="./.venv/bin/ruff check ."

# The test gates only run when this file exists (i.e. the project is set up).
TEST_GUARD_FILE="src/manage.py"

# Run the test suite after every source/test file write (records red/green
# for the TDD cycle). Set to "false" if your suite is too slow for that;
# tests are then only enforced at commit time.
RUN_TESTS_ON_WRITE="true"

# Gitflow branches (see .claude/rules/git.md). Ticket branches are cut from
# DEVELOP_BRANCH and squash-merged back into it; MAIN_BRANCH only receives
# PRs from DEVELOP_BRANCH via the release skill.
MAIN_BRANCH="main"
DEVELOP_BRANCH="develop"

# Branches that may never receive direct commits or force-pushes.
PROTECTED_BRANCHES="main|master|develop"

# Directories that count as production/test code (used by the write guard).
SOURCE_DIRS="src|app|lib|test|tests|__tests__"

# GitHub repo and project board that factory-manager syncs with
# (.claude/scripts/board.py). GH_PROJECT_NUMBER is the board's number
# under GH_OWNER, as shown by 'gh project list'.
GH_OWNER="Jeko92"
GH_REPO="Jeko92/learning-companion-v2"
GH_PROJECT_NUMBER="6"
