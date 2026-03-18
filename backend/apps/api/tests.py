from __future__ import annotations

import os

from django.test import TestCase

from apps.buildmeta.models import BuildPlan, BuildPlanDefinition, Project, ProjectBuild, ProjectRepository


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

    def test_prepare_context_endpoint(self) -> None:
        response = self.client.get("/api/v1/build-plans/SAMPAPI/prepare-context", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("SAMPLE", payload["project"]["jiraProjectKey"])
        self.assertEqual("sample-app-api", payload["variables"]["BITBUCKET_REPO_SLUG"])
