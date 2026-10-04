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


def steps(job):
    """Each step of a job as {key: value}, with the keys of nested mappings
    (`with:`) flattened in."""
    found = []
    for line in blocks(job[1:], 2).get("steps", ["steps:"])[1:]:
        line = line.strip()
        if line.startswith("- "):
            found.append({})
            line = line[2:]
        key, _, value = line.partition(":")
        found[-1][key] = value.strip()
    return found


class WorkflowTestCase(SimpleTestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW.is_file(), ".github/workflows/ci.yml is missing")
        self.text = WORKFLOW.read_text()
        self.top = blocks(self.text.splitlines(), 0)
        self.jobs = blocks(self.top.get("jobs", ["jobs:"])[1:], 2)

    def job(self, name):
        self.assertIn(name, list(self.jobs), f"there is no {name} job")
        return self.jobs[name]

    def settings_of(self, name):
        """The job's own keys, each as its block of lines."""
        return blocks(self.job(name)[1:], 2)


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


class QualityJobTests(WorkflowTestCase):
    """The quality job runs the hooks' and reviews' gate on Python 3.14."""

    COMMANDS = (
        "ruff check .",
        "ruff format --check .",
        "python src/manage.py check",
        "python src/manage.py makemigrations --check --dry-run",
        "python src/manage.py test src",
    )

    def setUp(self):
        super().setUp()
        self.settings = self.settings_of("quality")
        self.steps = steps(self.job("quality"))

    def test_it_runs_on_ubuntu_with_a_timeout(self):
        self.assertEqual(self.settings["runs-on"], ["runs-on: ubuntu-latest"])
        self.assertRegex(self.settings["timeout-minutes"][0], r"^timeout-minutes: \d+$")

    def test_it_checks_out_and_sets_up_python_3_14_with_a_pip_cache(self):
        self.assertEqual(self.steps[0], {"uses": "actions/checkout@v7"})
        self.assertEqual(
            self.steps[1],
            {
                "uses": "actions/setup-python@v7",
                "with": "",
                "python-version": '"3.14"',
                "cache": "pip",
                "cache-dependency-path": "requirements*.txt",
            },
        )

    def test_it_installs_the_dev_requirements_before_the_checks(self):
        self.assertEqual(self.steps[2]["run"], "pip install -r requirements-dev.txt")

    def test_each_gate_command_is_its_own_named_step_in_order(self):
        gate = self.steps[3:]
        self.assertEqual([step["run"] for step in gate], list(self.COMMANDS))
        for step in gate:
            with self.subTest(run=step["run"]):
                self.assertTrue(step.get("name"), "the step has no name")

    def test_the_keys_are_dummies_in_the_job_env(self):
        # The tests never call the API, so no repository secret is needed.
        self.assertEqual(
            self.settings["env"],
            [
                "env:",
                "  SECRET_KEY: ci-dummy-secret-key",
                "  OPENAI_API_KEY: sk-dummy",
            ],
        )


class DockerSmokeJobTests(WorkflowTestCase):
    """The docker-smoke job builds and checks the image, alongside quality."""

    def setUp(self):
        super().setUp()
        self.settings = self.settings_of("docker-smoke")

    def test_it_runs_on_ubuntu_with_a_timeout(self):
        self.assertEqual(self.settings["runs-on"], ["runs-on: ubuntu-latest"])
        self.assertRegex(self.settings["timeout-minutes"][0], r"^timeout-minutes: \d+$")

    def test_it_checks_out_and_runs_the_smoke_script(self):
        self.assertEqual(
            steps(self.job("docker-smoke")),
            [
                {"uses": "actions/checkout@v7"},
                {"name": "Build and check the image", "run": "scripts/docker-smoke.sh"},
            ],
        )

    def test_it_runs_in_parallel_with_the_quality_job(self):
        self.assertNotIn("needs", self.settings)


class WorkflowHygieneTests(WorkflowTestCase):
    """Pinned actions, no secrets, and job ids that branch protection can rely
    on as check names."""

    def test_every_action_is_pinned_to_a_major_version(self):
        uses = re.findall(r"^\s*(?:- )?uses: (.+)$", self.text, re.MULTILINE)
        self.assertTrue(uses)
        for action in uses:
            with self.subTest(action=action):
                self.assertRegex(action, r"^[\w-]+/[\w-]+@v\d+$")

    def test_no_repository_secret_is_used(self):
        self.assertNotIn("secrets.", self.text)

    def test_the_job_ids_are_the_check_names(self):
        # Without a name: key, a job's id is its status check's name.
        self.assertEqual(list(self.jobs), ["quality", "docker-smoke"])
        for job in self.jobs:
            with self.subTest(job=job):
                self.assertNotIn("name", self.settings_of(job))


class FactoryGateTests(SimpleTestCase):
    """With CI in place, a release PR merges only on passing checks."""

    def test_release_prs_require_passing_checks(self):
        config = (ROOT / ".claude" / "hooks" / "config.sh").read_text()
        self.assertEqual(
            re.findall(r"^REQUIRE_CHECKS=.*$", config, re.MULTILINE),
            ['REQUIRE_CHECKS="true"'],
        )
