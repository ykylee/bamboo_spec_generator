from __future__ import annotations

import json
import os

from django.test import TestCase

from apps.buildmeta.models import BuildPlan, BuildPlanDefinition, BuildVersion, Project, ProjectBuild, ProjectRepository
from apps.buildmeta.services.executions import finish_execution, start_execution


class ApiSmokeTest(TestCase):
    def setUp(self) -> None:
        os.environ["BAMBOO_API_TOKEN"] = "test-token"
        self.project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app",
            coverity_stream="sample-app-dev",
            is_representative=True,
        )
        self.plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")
        ProjectBuild.objects.create(
            project=self.project,
            build_plan=self.plan,
            build_name="backend",
            build_type="python",
        )
        definition = BuildPlanDefinition.objects.create(
            build_plan=self.plan,
            project=self.project,
            year="2026",
            source_kind=BuildPlanDefinition.SOURCE_KIND_JSON,
            definition_hash="sha256:abc123",
            is_active=True,
            definition_json={
                "year": "2026",
                "buildId": "sample-app-api",
                "name": "Sample App API",
                "planKey": "SAMPAPI",
                "description": "Sample App API build plan",
                "language": "java",
                "compiler": "maven",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-app-api",
                    "linkageMode": "linked",
                    "applicationLink": "BITBUCKET_SERVER",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {
                    "os": "linux",
                    "extraCapabilities": [],
                },
                "build": {
                    "subPath": "services/sample-app-api",
                    "prepareCommand": "mvn -B dependency:go-offline",
                    "buildCommand": "mvn -B clean package",
                    "staticAnalysis": {
                        "customTool": {
                            "commands": ["custom-tool analyze {buildCommand}"],
                        }
                    },
                    "runtimeRequirements": {
                        "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                        "envVars": ["PATH", "JAVA_HOME"],
                    },
                    "postBuildTrigger": {
                        "type": "plan",
                        "targetPlanKey": "POSTBUILD",
                    },
                },
            },
        )
        self.auth_headers = {"HTTP_AUTHORIZATION": "Bearer test-token"}

    def test_active_definition_endpoint(self) -> None:
        response = self.client.get("/api/v1/build-plans/SAMPAPI/active-definition", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("SAMPAPI", payload["planKey"])
        self.assertEqual("2026", payload["year"])
        self.assertEqual("sample-app-api", payload["definition"]["buildId"])
        self.assertEqual("BITBUCKET_SERVER", payload["definition"]["repository"]["applicationLink"])

    def test_prepare_context_endpoint(self) -> None:
        response = self.client.get("/api/v1/build-plans/SAMPAPI/prepare-context", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("SAMPLE", payload["project"]["jiraProjectKey"])
        self.assertEqual("sample-app-api", payload["variables"]["BITBUCKET_REPO_SLUG"])
        self.assertEqual("BITBUCKET_SERVER", payload["variables"]["BITBUCKET_APPLICATION_LINK"])
        self.assertEqual("BITBUCKET_SERVER", payload["currentRepository"]["applicationLink"])
        self.assertEqual("linked", payload["currentRepository"]["linkageMode"])

    def test_execution_start_and_finish_endpoints(self) -> None:
        start_response = self.client.post(
            "/api/v1/build-plans/SAMPAPI/executions/start",
            data=json.dumps(
                {
                    "branchKind": BuildVersion.BRANCH_KIND_DEV,
                    "commitHash": "abcdef123456",
                    "buildNumber": "101",
                    "startedAt": "2026-03-19T00:00:00Z",
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, start_response.status_code)
        start_payload = start_response.json()
        self.assertEqual("v0.0.1", start_payload["version"])
        self.assertFalse(start_payload["reusedExistingVersion"])

        finish_response = self.client.post(
            f"/api/v1/build-executions/{start_payload['buildExecutionId']}/finish",
            data=json.dumps(
                {
                    "success": True,
                    "resultStatus": "successful",
                    "summaryMessage": "Build passed",
                    "stageName": "Static Analysis",
                    "jobName": "Coverity Scan",
                    "taskName": "run_coverity.py",
                    "finishedAt": "2026-03-19T00:12:00Z",
                    "staticAnalysisResults": [
                        {
                            "toolName": "coverity",
                            "status": "passed",
                            "summary": "0 high impact defects",
                            "metricsJson": {"high": 0},
                        }
                    ],
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, finish_response.status_code)
        finish_payload = finish_response.json()
        self.assertTrue(finish_payload["success"])
        self.assertEqual("successful", finish_payload["resultStatus"])

    def test_execution_list_endpoint(self) -> None:
        start_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )
        finish_execution(
            execution_id=start_payload["buildExecutionId"],
            success=True,
            result_status="successful",
            summary_message="Build passed",
            static_analysis_results=[
                {
                    "toolName": "coverity",
                    "status": "passed",
                    "summary": "0 high impact defects",
                    "metricsJson": {"high": 0},
                }
            ],
        )

        response = self.client.get("/api/v1/build-plans/SAMPAPI/executions", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(1, len(payload))
        self.assertEqual("v0.0.1", payload[0]["version"])
        self.assertEqual("successful", payload[0]["resultStatus"])
        self.assertEqual("coverity", payload[0]["staticAnalysisResults"][0]["toolName"])

    def test_static_analysis_results_upsert_endpoint(self) -> None:
        start_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )

        response = self.client.post(
            f"/api/v1/build-executions/{start_payload['buildExecutionId']}/static-analysis-results",
            data=json.dumps(
                {
                    "staticAnalysisResults": [
                        {
                            "toolName": "coverity",
                            "status": "passed",
                            "summary": "0 high impact defects",
                            "metricsJson": {"high": 0},
                        }
                    ]
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(1, payload["updatedCount"])

        list_response = self.client.get("/api/v1/build-plans/SAMPAPI/executions", **self.auth_headers)
        list_payload = list_response.json()
        self.assertEqual("coverity", list_payload[0]["staticAnalysisResults"][0]["toolName"])
