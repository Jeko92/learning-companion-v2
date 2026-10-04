"""The GitHub Actions workflow and the gates that rely on its checks.

There is no YAML parser among the requirements, so the workflow is read as
text: split into its top-level keys and its jobs by indentation."""

import re

from django.conf import settings
from django.test import SimpleTestCase

ROOT = settings.BASE_DIR.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def blocks(lines, indent):
    """{key: [lines]} for each key at exactly `indent` spaces. Each block keeps
    its own key line, without the indent; comments and blank lines are
    dropped."""
    found = {}
    current = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(rf"^ {{{indent}}}([\w-]+):", line)
        if match:
            current = found.setdefault(match.group(1), [])
        if current is not None:
            current.append(line[indent:])
    return found


class WorkflowTestCase(SimpleTestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW.is_file(), ".github/workflows/ci.yml is missing")
        self.text = WORKFLOW.read_text()
        self.top = blocks(self.text.splitlines(), 0)


class WorkflowTriggerTests(WorkflowTestCase):
    """CI runs on every push and pull request with a read-only token, and a
    newer run of the same ref cancels the older one."""

    def test_the_workflow_is_named_ci(self):
        self.assertEqual(self.top["name"], ["name: CI"])

    def test_it_runs_on_every_push_and_pull_request_without_filters(self):
        self.assertEqual(self.top["on"], ["on:", "  push:", "  pull_request:"])

    def test_its_token_can_only_read_the_repository(self):
        self.assertEqual(self.top["permissions"], ["permissions:", "  contents: read"])

    def test_a_newer_run_of_the_same_ref_cancels_the_older_one(self):
        self.assertEqual(
            self.top["concurrency"],
            [
                "concurrency:",
                "  group: ${{ github.workflow }}-${{ github.ref }}",
                "  cancel-in-progress: true",
            ],
        )
