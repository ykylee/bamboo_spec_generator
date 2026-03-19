from __future__ import annotations

from django.test import TestCase

from apps.buildmeta.models import BuildPlan, BuildPlanDefinition, Project, ProjectBuild, ProjectRepository


class ProjectViewTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            is_representative=True,
        )
        build_plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")
        ProjectBuild.objects.create(
            project=self.project,
            build_plan=build_plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )
        BuildPlanDefinition.objects.create(
            build_plan=build_plan,
            project=self.project,
            year="2026",
            source_kind=BuildPlanDefinition.SOURCE_KIND_JSON,
            definition_json={"buildId": "sample-app-api", "planKey": "SAMPAPI"},
            definition_hash="sha256:sample",
            is_active=True,
        )

    def test_project_list_renders_generation_readiness(self) -> None:
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Specs 생성 가능")
        self.assertContains(response, "정의 1/1")
        self.assertContains(response, "SAMPLE")

    def test_project_detail_renders_generation_panel(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Specs 생성 준비도")
        self.assertContains(response, "가능")
        self.assertContains(response, "Year 2026")
