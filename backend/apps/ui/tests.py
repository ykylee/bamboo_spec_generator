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
        repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            is_representative=True,
        )
        build_plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")
        ProjectBuild.objects.create(
            project=self.project,
            repository=repository,
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
        self.assertContains(response, "프로젝트 등록")
        self.assertContains(response, 'name="jira_project_key"', html=False)
        self.assertContains(response, 'id="project-registration-panel"', html=False)
        self.assertContains(response, "hidden", html=False)
        self.assertContains(response, "jira-project-key-options")
        self.assertContains(response, "bitbucket-project-key-options")
        self.assertContains(response, "repository-slug-options")
        self.assertContains(response, "sample-app-api")

    def test_project_detail_renders_generation_panel(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Specs 생성 준비도")
        self.assertContains(response, "가능")
        self.assertContains(response, "Year 2026")
        self.assertContains(response, "Repository: sample-app-api")
        self.assertContains(response, "프로젝트 수정")
        self.assertContains(response, 'id="project-edit-panel"', html=False)
        self.assertContains(response, 'name="jira_project_key"', html=False)
        self.assertContains(response, 'value="SAMPLE"', html=False)
        self.assertContains(response, 'name="repo_slug"', html=False)
        self.assertContains(response, 'value="sample-app-api"', html=False)
        self.assertContains(response, 'id="project-edit-panel"', html=False)
        self.assertContains(response, "hidden", html=False)

    def test_project_registration_from_main_page_redirects_to_detail(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "OPS",
                "bitbucket_project_key": "OPS",
                "representative_repo_slug": "ops-api",
                "repo_slug": ["ops-api", "ops-worker"],
                "coverity_project": ["ops-api", ""],
                "coverity_stream": ["ops-api-dev", ""],
                "build_name": ["Operations API", "Worker"],
                "build_type": ["python", "python"],
                "runtime_stack": ["python3.12", "python3.12"],
                "build_id": ["ops-api", "ops-worker"],
                "plan_key": ["OPSAPI", "OPSWORK"],
                "build_repository_slug": ["ops-api", "ops-worker"],
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/OPS/", response["Location"])
        self.assertTrue(Project.objects.filter(jira_project_key="OPS").exists())
        self.assertEqual(2, ProjectRepository.objects.filter(project__jira_project_key="OPS").count())
        self.assertEqual(2, ProjectBuild.objects.filter(project__jira_project_key="OPS").count())

    def test_project_registration_from_main_page_shows_validation_error(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "SAMPLE",
                "bitbucket_project_key": "SAMPLE",
                "representative_repo_slug": "sample-app-api",
                "repo_slug": ["sample-app-api"],
                "coverity_project": [""],
                "coverity_stream": [""],
                "build_name": ["Duplicate"],
                "build_type": ["python"],
                "runtime_stack": [""],
                "build_id": ["duplicate-build"],
                "plan_key": ["DUPL"],
                "build_repository_slug": ["sample-app-api"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "already exists", html=False)
        self.assertContains(response, 'id="project-registration-panel"', html=False)
        self.assertNotContains(response, 'id="project-registration-panel" hidden', html=False)

    def test_project_registration_from_main_page_requires_build_repository_match(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "OPS",
                "bitbucket_project_key": "OPS",
                "representative_repo_slug": "ops-api",
                "repo_slug": ["ops-api"],
                "coverity_project": [""],
                "coverity_stream": [""],
                "build_name": ["Operations API"],
                "build_type": ["python"],
                "runtime_stack": ["python3.12"],
                "build_id": ["ops-api"],
                "plan_key": ["OPSAPI"],
                "build_repository_slug": ["missing-repo"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "저장소 목록에 없습니다", html=False)
        self.assertNotContains(response, 'id="project-registration-panel" hidden', html=False)

    def test_project_detail_update_replaces_existing_project_configuration(self) -> None:
        extra_repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-web",
            coverity_project="sample-app-web",
            coverity_stream="sample-app-web-dev",
            is_representative=False,
        )
        extra_plan = BuildPlan.objects.create(build_id="sample-app-web", plan_key="SAMPWEB")
        ProjectBuild.objects.create(
            project=self.project,
            repository=extra_repository,
            build_plan=extra_plan,
            build_name="Sample Web",
            build_type="node",
            runtime_stack="node20",
        )

        response = self.client.post(
            "/projects/SAMPLE/",
            data={
                "jira_project_key": "SAMPLE",
                "bitbucket_project_key": "SAMPLE-NEW",
                "representative_repo_slug": "sample-app-web",
                "repo_slug": ["sample-app-web"],
                "coverity_project": ["sample-app-web"],
                "coverity_stream": ["sample-app-web-release"],
                "build_name": ["Sample Web"],
                "build_type": ["node"],
                "runtime_stack": ["node22"],
                "build_id": ["sample-app-web"],
                "plan_key": ["SAMPWEB"],
                "build_repository_slug": ["sample-app-web"],
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/", response["Location"])
        self.project.refresh_from_db()
        self.assertEqual("SAMPLE-NEW", self.project.bitbucket_project_key)
        self.assertEqual("sample-app-web", self.project.representative_repo_slug)
        self.assertEqual(1, ProjectRepository.objects.filter(project=self.project).count())
        self.assertEqual(1, ProjectBuild.objects.filter(project=self.project).count())
        self.assertTrue(ProjectRepository.objects.filter(project=self.project, repo_slug="sample-app-web").exists())
        self.assertFalse(ProjectRepository.objects.filter(project=self.project, repo_slug="sample-app-api").exists())
        self.assertTrue(ProjectBuild.objects.filter(project=self.project, build_plan__plan_key="SAMPWEB").exists())
        self.assertFalse(ProjectBuild.objects.filter(project=self.project, build_plan__plan_key="SAMPAPI").exists())

    def test_project_detail_update_reopens_panel_on_validation_error(self) -> None:
        response = self.client.post(
            "/projects/SAMPLE/",
            data={
                "jira_project_key": "SAMPLE",
                "bitbucket_project_key": "SAMPLE",
                "representative_repo_slug": "missing-repo",
                "repo_slug": ["sample-app-api"],
                "coverity_project": ["sample-app-api"],
                "coverity_stream": ["sample-app-api-dev"],
                "build_name": ["Sample API"],
                "build_type": ["maven"],
                "runtime_stack": ["java"],
                "build_id": ["sample-app-api"],
                "plan_key": ["SAMPAPI"],
                "build_repository_slug": ["sample-app-api"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "대표 저장소는 등록한 저장소 목록 중 하나여야 합니다.", html=False)
        self.assertNotContains(response, 'id="project-edit-panel" hidden', html=False)
