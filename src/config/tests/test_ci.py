"""The GitHub Actions workflow and the gates that rely on its checks.

There is no YAML parser among the requirements, so the workflow is read as
text: split into its top-level keys and its jobs by indentation."""

import json
import os
import re
import subprocess

from django.conf import settings
from django.test import SimpleTestCase

ROOT = settings.BASE_DIR.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
# No step needs git auth, so the job token isn't left in .git/config for the
# later steps (the PR's own test code, the smoke script) to read.
CHECKOUT = {"uses": "actions/checkout@v7", "with": "", "persist-credentials": "false"}


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


def steps(block):
    """Each step of a job's `steps:` block as {key: value}, with the keys of
    nested mappings (`with:`) flattened in, so a step with any extra key (`if`,
    `continue-on-error`, `env`) differs from the dict a test expects."""
    found = []
    for line in block[1:]:
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

    def steps_of(self, name):
        settings = self.settings_of(name)
        self.assertIn("steps", settings, f"the {name} job has no steps")
        return steps(settings["steps"])


class WorkflowTriggerTests(WorkflowTestCase):
    """CI runs on every push and pull request with a read-only token, and a
    newer run of the same ref cancels the older one."""

    def test_the_workflow_is_named_ci(self):
        self.assertEqual(self.top["name"], ["name: CI"])

    def test_it_runs_on_every_push_and_pull_request_without_filters(self):
        self.assertEqual(self.top["on"], ["on:", "  push:", "  pull_request:"])

    def test_its_token_can_only_read_the_repository(self):
        self.assertEqual(self.top["permissions"], ["permissions:", "  contents: read"])

    def test_a_newer_run_cancels_the_older_one_except_on_protected_branches(self):
        # A cancelled required check on main or develop would read as failed.
        self.assertEqual(
            self.top["concurrency"],
            [
                "concurrency:",
                "  group: ${{ github.workflow }}-${{ github.ref }}",
                (
                    "  cancel-in-progress: ${{ github.ref != 'refs/heads/main'"
                    " && github.ref != 'refs/heads/develop' }}"
                ),
            ],
        )


# Production-like settings for check --deploy: DEBUG off (the HTTPS settings
# follow it) and a dummy key long enough for security.W009, which the job's own
# dummy is not. Values keep their YAML quotes.
DEPLOY_CHECK = {
    "name": "Deployment checks",
    "run": "python src/manage.py check --deploy --fail-level WARNING",
    "env": "",
    "DEBUG": '"False"',
    "SECRET_KEY": "ci-deploy-check-dummy-key-0123456789-abcdefghijklmnopqrstuvwxyz",
}


class QualityJobTests(WorkflowTestCase):
    """The quality job runs the hooks' and reviews' gate on Python 3.14."""

    GATE = (
        {"name": "Lint", "run": "ruff check ."},
        {"name": "Formatting", "run": "ruff format --check ."},
        {"name": "Django system checks", "run": "python src/manage.py check"},
        DEPLOY_CHECK,
        {
            "name": "Migrations match the models",
            "run": "python src/manage.py makemigrations --check --dry-run",
        },
        {"name": "Tests", "run": "python src/manage.py test src"},
    )

    def setUp(self):
        super().setUp()
        self.settings = self.settings_of("quality")
        self.steps = self.steps_of("quality")

    def test_it_runs_on_ubuntu_with_a_timeout(self):
        self.assertEqual(self.settings["runs-on"], ["runs-on: ubuntu-latest"])
        self.assertRegex(self.settings["timeout-minutes"][0], r"^timeout-minutes: \d+$")

    def test_it_checks_out_and_sets_up_python_3_14_with_a_pip_cache(self):
        self.assertEqual(self.steps[0], CHECKOUT)
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
        self.assertEqual(
            self.steps[2],
            {
                "name": "Install dependencies",
                "run": "pip install -r requirements-dev.txt",
            },
        )

    def test_each_gate_command_is_its_own_unconditional_named_step_in_order(self):
        # Exact dicts: an `if: false` or `continue-on-error: true` on a gate
        # step would let CI pass without its check.
        self.assertEqual(self.steps[3:], list(self.GATE))

    def test_the_deployment_check_key_is_long_enough_for_check_deploy(self):
        # Django's security.W009: at least 50 characters, 5 of them unique.
        key = DEPLOY_CHECK["SECRET_KEY"]
        self.assertGreaterEqual(len(key), 50)
        self.assertGreaterEqual(len(set(key)), 5)

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
            self.steps_of("docker-smoke"),
            [
                CHECKOUT,
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


class BranchProtectionScriptTests(WorkflowTestCase):
    """scripts/branch-protection.sh holds the protection of main and develop.
    `desired <branch>` prints the body `apply` sends, without the network."""

    SCRIPT = ROOT / "scripts" / "branch-protection.sh"
    GITHUB_ACTIONS_APP_ID = 15368

    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.SCRIPT.is_file(), "scripts/branch-protection.sh is missing"
        )

    def desired(self, branch):
        result = subprocess.run(
            [str(self.SCRIPT), "desired", branch],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_script_is_an_executable_bash_script_that_parses(self):
        self.assertTrue(os.access(self.SCRIPT, os.X_OK), "it is not executable")
        self.assertTrue(self.SCRIPT.read_text().startswith("#!/usr/bin/env bash\n"))
        result = subprocess.run(
            ["bash", "-n", str(self.SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_both_branches_require_the_workflow_jobs_from_github_actions(self):
        for branch in ("main", "develop"):
            with self.subTest(branch=branch):
                checks = self.desired(branch)["required_status_checks"]
                self.assertEqual(
                    checks["checks"],
                    [
                        {"context": job, "app_id": self.GITHUB_ACTIONS_APP_ID}
                        for job in self.jobs
                    ],
                )
                # A ticket PR needn't be rebased on develop before it merges.
                self.assertIs(checks["strict"], False)

    def test_main_keeps_its_pull_request_rule_and_binds_admins(self):
        main = self.desired("main")
        self.assertIs(main["enforce_admins"], True)
        self.assertEqual(
            main["required_pull_request_reviews"]["required_approving_review_count"], 0
        )

    def test_develop_lets_the_owner_push_the_release_merge_commit(self):
        # The release skill pushes "merge main into develop" directly, so
        # develop needs no PR and admins may bypass its required checks.
        develop = self.desired("develop")
        self.assertIs(develop["enforce_admins"], False)
        self.assertIsNone(develop["required_pull_request_reviews"])

    def test_neither_branch_allows_force_pushes_or_deletion(self):
        for branch in ("main", "develop"):
            for setting in ("allow_force_pushes", "allow_deletions"):
                with self.subTest(branch=branch, setting=setting):
                    self.assertIs(self.desired(branch)[setting], False)

    def test_an_unknown_branch_or_command_is_refused(self):
        for arguments in (["desired", "feature/x"], ["delete"], []):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [str(self.SCRIPT), *arguments],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("usage:", result.stderr)


CONFIG = ROOT / ".claude" / "hooks" / "config.sh"


class ReadmeBadgeTests(SimpleTestCase):
    """The README shows main's CI status at the top and says what CI runs."""

    def setUp(self):
        (repo,) = re.findall(r'^GH_REPO="(.+)"$', CONFIG.read_text(), re.MULTILINE)
        self.workflow_url = f"https://github.com/{repo}/actions/workflows/ci.yml"
        self.readme = (ROOT / "README.md").read_text().splitlines()

    def test_the_ci_badge_for_main_links_to_the_workflow_runs(self):
        badge = f"{self.workflow_url}/badge.svg?branch=main"
        self.assertIn(f"[![CI]({badge})]({self.workflow_url})", self.readme[:5])

    def test_a_ci_section_names_both_jobs(self):
        self.assertIn("## CI", self.readme)
        start = self.readme.index("## CI") + 1
        end = next(
            (i for i in range(start, len(self.readme)) if self.readme[i][:3] == "## "),
            len(self.readme),
        )
        section = "\n".join(self.readme[start:end])
        for job in ("quality", "docker-smoke"):
            with self.subTest(job=job):
                self.assertIn(f"`{job}`", section)


class FactoryGateTests(SimpleTestCase):
    """With CI in place, a release PR merges only on passing checks."""

    def test_release_prs_require_passing_checks(self):
        config = CONFIG.read_text()
        self.assertEqual(
            re.findall(r"^REQUIRE_CHECKS=.*$", config, re.MULTILINE),
            ['REQUIRE_CHECKS="true"'],
        )
