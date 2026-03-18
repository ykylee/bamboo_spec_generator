from __future__ import annotations

from django.test import TestCase

from apps.buildmeta.models import BuildExecution, BuildPlan, BuildVersion, Project
from apps.buildmeta.services.executions import finish_execution, start_execution


class ExecutionServiceTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        self.plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")

    def test_start_execution_creates_version_and_execution(self) -> None:
        payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )

        self.assertEqual("v0.0.1", payload["version"])
        self.assertFalse(payload["reusedExistingVersion"])
        self.assertEqual(1, BuildVersion.objects.count())
        self.assertEqual(1, BuildExecution.objects.count())

    def test_finish_execution_updates_latest_success(self) -> None:
        start_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )

        finish_payload = finish_execution(
            execution_id=start_payload["buildExecutionId"],
            success=True,
            result_status="successful",
            summary_message="Build passed",
        )

        self.assertTrue(finish_payload["success"])
        version = BuildVersion.objects.get(pk=finish_payload["buildVersionId"])
        self.assertTrue(version.latest_success)
