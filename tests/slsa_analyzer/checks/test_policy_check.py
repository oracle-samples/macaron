# Copyright (c) 2022 - 2022, Oracle and/or its affiliates. All rights reserved.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/.

"""This modules contains tests for the policy check."""

import os
from unittest.mock import MagicMock

from macaron.code_analyzer.call_graph import BaseNode, CallGraph
from macaron.policy_engine.policy import Policy
from macaron.slsa_analyzer.analyzer import AnalyzeContext
from macaron.slsa_analyzer.checks.check_result import CheckResult, CheckResultType
from macaron.slsa_analyzer.checks.policy_check import PolicyCheck
from macaron.slsa_analyzer.ci_service.circleci import CircleCI
from macaron.slsa_analyzer.ci_service.github_actions import GitHubActions
from macaron.slsa_analyzer.ci_service.gitlab_ci import GitLabCI
from macaron.slsa_analyzer.ci_service.jenkins import Jenkins
from macaron.slsa_analyzer.ci_service.travis import Travis
from macaron.slsa_analyzer.git_service.api_client import GhAPIClient
from macaron.slsa_analyzer.provenance.loader import ProvPayloadLoader
from macaron.slsa_analyzer.specs.ci_spec import CIInfo

from ...macaron_testcase import MacaronTestCase


class MockGitHubActions(GitHubActions):
    """Mock the GitHubActions class."""

    def has_latest_run_passed(
        self, repo_full_name: str, branch_name: str, commit_sha: str, commit_date: str, workflow: str
    ) -> str:
        return "run_feedback"


class MockGhAPIClient(GhAPIClient):
    """Mock GhAPIClient class."""

    def __init__(self, profile: dict):
        super().__init__(profile)
        self.release = {
            "assets": [
                {"name": "attestation.intoto.jsonl", "url": "URL", "size": "10"},
                {"name": "artifact.txt", "url": "URL", "size": "10"},
            ]
        }

    def get_latest_release(self, full_name: str) -> dict:
        return self.release

    def get_assets(self, release: dict, name: str = "", ext: str = "") -> list[dict]:
        return [item for item in self.release["assets"] if item["name"] == name or item["name"].endswith(ext)]

    def download_asset(self, url: str, download_path: str) -> bool:
        return True


class TestPolicyCheck(MacaronTestCase):
    """Test the policy check."""

    def test_policy_check(self) -> None:
        """Test the policy check."""
        check = PolicyCheck()
        check_result = CheckResult(justification=[])  # type: ignore
        github_actions = MockGitHubActions()
        api_client = MockGhAPIClient({"headers": {}, "query": []})
        github_actions.api_client = api_client
        github_actions.load_defaults()
        jenkins = Jenkins()
        jenkins.load_defaults()
        travis = Travis()
        travis.load_defaults()
        circle_ci = CircleCI()
        circle_ci.load_defaults()
        gitlab_ci = GitLabCI()
        gitlab_ci.load_defaults()

        prov_dir = os.path.join(self.macaron_test_dir, "policy_engine", "resources", "provenances")
        policy_dir = os.path.join(self.macaron_test_dir, "policy_engine", "resources", "policies")
        ctx = AnalyzeContext("use_build_tool", os.path.abspath("./"), MagicMock())

        # Test GitHub Actions.
        ci_info = CIInfo(
            service=github_actions,
            bash_commands=[],
            callgraph=CallGraph(BaseNode(), ""),
            provenance_assets=[],
            latest_release={},
            provenances=[],
        )
        ctx.dynamic_data["ci_services"] = [ci_info]

        # Repo has inferred provenance and no policy.
        ctx.dynamic_data["is_inferred_prov"] = True
        ctx.dynamic_data["policy"] = None
        assert check.run_check(ctx, check_result) == CheckResultType.FAILED

        # Repo has a provenance, but no policy.
        ci_info["provenances"] = [
            ProvPayloadLoader.load(os.path.join(prov_dir, "slsa-verifier-linux-amd64.intoto.jsonl"))
        ]
        ctx.dynamic_data["is_inferred_prov"] = False
        ctx.dynamic_data["policy"] = None
        assert check.run_check(ctx, check_result) == CheckResultType.FAILED

        # Repo has a provenance but invalid policy.
        ctx.dynamic_data["policy"] = Policy.make_policy(os.path.join(policy_dir, "invalid.yaml"))
        assert check.run_check(ctx, check_result) == CheckResultType.FAILED

        # Repo has a provenance and valid policy.
        ctx.dynamic_data["policy"] = Policy.make_policy(os.path.join(policy_dir, "slsa_verifier.yaml"))
        assert check.run_check(ctx, check_result) == CheckResultType.PASSED

        # Test Jenkins.
        ci_info["service"] = jenkins
        assert check.run_check(ctx, check_result) == CheckResultType.PASSED

        # Test Travis.
        ci_info["service"] = travis
        assert check.run_check(ctx, check_result) == CheckResultType.PASSED

        # Test Circle CI.
        ci_info["service"] = circle_ci
        assert check.run_check(ctx, check_result) == CheckResultType.PASSED

        # Test GitLab CI.
        ci_info["service"] = gitlab_ci
        assert check.run_check(ctx, check_result) == CheckResultType.PASSED
