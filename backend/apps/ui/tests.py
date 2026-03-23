from __future__ import annotations

from django.test import TestCase

from apps.buildmeta.models import (
    BuildExecution,
    BuildPlan,
    BuildPlanBuildInfo,
    BuildPlanDefinition,
    BuildVersion,
    Project,
    ProjectBuild,
    ProjectRepository,
)


class ProjectViewTest(TestCase):
    def setUp(self) -> None:
        self.project = self._create_project_with_build(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            repo_slug="sample-app-api",
            build_name="Sample API",
            build_id="sample-app-api",
            plan_key="SAMPAPI",
            build_type="maven",
            runtime_stack="java",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            with_active_definition=True,
        )["project"]

    def _create_project_with_build(
        self,
        *,
        jira_project_key: str,
        bitbucket_project_key: str,
        repo_slug: str,
        build_name: str,
        build_id: str,
        plan_key: str,
        build_type: str = "python",
        runtime_stack: str = "python3.12",
        representative_repo_slug: str | None = None,
        coverity_project: str = "",
        coverity_stream: str = "",
        build_plan_coverity_project: str = "",
        static_analysis_tool_version: str = "",
        with_active_definition: bool = False,
        definition_year: str = "2026",
        latest_success: bool | None = None,
        build_number: str = "1",
        result_status: str = "",
        summary_message: str = "",
    ) -> dict:
        project = Project.objects.create(
            jira_project_key=jira_project_key,
            bitbucket_project_key=bitbucket_project_key,
            representative_repo_slug=representative_repo_slug if representative_repo_slug is not None else repo_slug,
        )
        repository = ProjectRepository.objects.create(
            project=project,
            repo_slug=repo_slug,
            coverity_project=coverity_project,
            coverity_stream=coverity_stream,
            is_representative=project.representative_repo_slug == repo_slug,
        )
        build_plan = BuildPlan.objects.create(
            build_id=build_id,
            plan_key=plan_key,
            static_analysis_tool_version=static_analysis_tool_version,
            coverity_project=build_plan_coverity_project,
        )
        project_build = ProjectBuild.objects.create(
            project=project,
            repository=repository,
            build_plan=build_plan,
            build_name=build_name,
            build_type=build_type,
            runtime_stack=runtime_stack,
        )
        if with_active_definition:
            BuildPlanDefinition.objects.create(
                build_plan=build_plan,
                project=project,
                year=definition_year,
                source_kind=BuildPlanDefinition.SOURCE_KIND_JSON,
                definition_json={"buildId": build_id, "planKey": plan_key},
                definition_hash=f"sha256:{plan_key.lower()}",
                is_active=True,
            )
        if latest_success is not None:
            version = BuildVersion.objects.create(
                build_plan=build_plan,
                version_text="v1.0.0",
                major=1,
                minor=0,
                patch=0,
                branch_kind=BuildVersion.BRANCH_KIND_DEV,
                commit_hash=f"commit-{plan_key.lower()}",
                is_latest=True,
                latest_success=latest_success,
            )
            execution = BuildExecution.objects.create(
                build_plan=build_plan,
                build_version=version,
                build_number=build_number,
                commit_hash=version.commit_hash,
                success=latest_success,
                result_status=result_status,
                summary_message=summary_message,
            )
            version.latest_execution = execution
            version.save(update_fields=["latest_execution"])
            build_plan.latest_version = version
            build_plan.save(update_fields=["latest_version"])
        return {
            "project": project,
            "repository": repository,
            "build_plan": build_plan,
            "project_build": project_build,
        }

    def test_project_list_renders_generation_readiness(self) -> None:
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "운영 준비")
        self.assertContains(response, "SAMPLE")
        self.assertContains(response, "프로젝트 등록")
        self.assertContains(response, "주의가 필요한 프로젝트를 먼저 보여줍니다.")
        self.assertContains(response, "프로젝트 리스트")
        self.assertContains(response, "최근 실패 빌드")
        self.assertContains(response, "<th>저장소</th>", html=False)
        self.assertContains(response, 'data-open-dialog="repo-dialog-SAMPLE"', html=False)
        self.assertContains(response, 'data-open-dialog="representative-dialog-SAMPLE"', html=False)
        self.assertContains(response, ">sample-app-api<", html=False)
        self.assertContains(response, 'class="status-light status-light--success"', html=False)
        self.assertContains(response, "Needs Attention")
        self.assertContains(response, 'class="project-compact-list"', html=False)
        self.assertContains(response, 'id="project-nav-search"', html=False)
        self.assertNotContains(response, 'name="q"', html=False)
        self.assertNotContains(response, "Representative Repo Missing")
        self.assertNotContains(response, "Specs Ready")
        self.assertContains(response, 'name="jira_project_key"', html=False)
        self.assertContains(response, 'id="project-registration-panel"', html=False)
        self.assertContains(response, "hidden", html=False)
        self.assertContains(response, "jira-project-key-options")
        self.assertContains(response, "bitbucket-project-key-options")
        self.assertContains(response, "repository-slug-options")
        self.assertContains(response, "sample-app-api")

    def test_project_list_renders_empty_state_without_projects(self) -> None:
        ProjectBuild.objects.all().delete()
        ProjectRepository.objects.all().delete()
        BuildPlanDefinition.objects.all().delete()
        BuildPlan.objects.all().delete()
        Project.objects.all().delete()

        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "주의가 필요한 프로젝트를 먼저 보여줍니다.")
        self.assertContains(response, "등록된 프로젝트가 없습니다.")
        self.assertContains(response, "실패 상태 빌드가 없습니다.")

    def test_project_detail_does_not_render_list_search_filter(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'id="project-nav-search"', html=False)
        self.assertNotContains(response, 'name="q"', html=False)

    def test_build_plan_list_renders_global_index(self) -> None:
        build_plan = BuildPlan.objects.get(plan_key="SAMPAPI")
        build_plan.static_analysis_tool_version = "coverity-2024.12"
        build_plan.coverity_project = "sample-api-coverity"
        build_plan.save(
            update_fields=["static_analysis_tool_version", "coverity_project", "updated_at"]
        )

        response = self.client.get("/build-plans/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "빌드 플랜 인덱스")
        self.assertContains(response, "빌드 플랜 리스트")
        self.assertContains(response, "SAMPAPI")
        self.assertContains(response, "coverity-2024.12")
        self.assertContains(response, "sample-api-coverity")
        self.assertContains(response, "/projects/SAMPLE/builds/SAMPAPI/")
        self.assertContains(response, "최근 실패 빌드")

    def test_build_plan_list_filters_by_query_and_status(self) -> None:
        self._create_project_with_build(
            jira_project_key="FAIL",
            bitbucket_project_key="FAIL",
            repo_slug="fail-api",
            build_name="Fail API",
            build_id="fail-api",
            plan_key="FAILAPI",
            with_active_definition=False,
            latest_success=False,
            result_status="FAILED",
            summary_message="unit test failure",
        )

        query_response = self.client.get("/build-plans/", {"q": "fail"})
        failed_response = self.client.get("/build-plans/", {"status": "failed"})

        self.assertEqual(["Fail API"], [plan["buildName"] for plan in query_response.context["plans"]])
        self.assertEqual(["Fail API"], [plan["buildName"] for plan in failed_response.context["plans"]])

    def test_project_list_filters_by_query_across_project_keys_and_repo_slug(self) -> None:
        self._create_project_with_build(
            jira_project_key="OPS",
            bitbucket_project_key="OPSBB",
            repo_slug="ops-api",
            build_name="Operations API",
            build_id="ops-api",
            plan_key="OPSAPI",
            with_active_definition=True,
        )
        self._create_project_with_build(
            jira_project_key="WEB",
            bitbucket_project_key="WEBBB",
            repo_slug="web-portal",
            build_name="Web Portal",
            build_id="web-portal",
            plan_key="WEBPORTAL",
            with_active_definition=True,
        )

        jira_response = self.client.get("/", {"q": "OPS"})
        repo_response = self.client.get("/", {"q": "web-portal"})
        bitbucket_response = self.client.get("/", {"q": "sample"})

        self.assertEqual(["OPS"], [project["jiraProjectKey"] for project in jira_response.context["projects"]])
        self.assertEqual(["WEB"], [project["jiraProjectKey"] for project in repo_response.context["projects"]])
        self.assertEqual(["SAMPLE"], [project["jiraProjectKey"] for project in bitbucket_response.context["projects"]])

    def test_project_list_filters_attention_status(self) -> None:
        self._create_project_with_build(
            jira_project_key="ATTN",
            bitbucket_project_key="ATTN",
            repo_slug="attn-api",
            build_name="Attention API",
            build_id="attn-api",
            plan_key="ATTNAPI",
            representative_repo_slug="missing-repo",
            with_active_definition=False,
        )

        response = self.client.get("/", {"status": "attention"})

        self.assertEqual(["ATTN"], [project["jiraProjectKey"] for project in response.context["projects"]])
        self.assertContains(response, "연결 점검 필요")

    def test_project_list_filters_healthy_status(self) -> None:
        self._create_project_with_build(
            jira_project_key="ATTN",
            bitbucket_project_key="ATTN",
            repo_slug="attn-api",
            build_name="Attention API",
            build_id="attn-api",
            plan_key="ATTNAPI",
            representative_repo_slug="missing-repo",
            with_active_definition=False,
        )

        response = self.client.get("/", {"status": "healthy"})

        self.assertEqual(["SAMPLE"], [project["jiraProjectKey"] for project in response.context["projects"]])
        self.assertContains(response, "운영 준비")

    def test_project_list_paginates_ten_projects_and_preserves_query_parameters(self) -> None:
        for index in range(11):
            self._create_project_with_build(
                jira_project_key=f"PAG{index:02d}",
                bitbucket_project_key="PAGE",
                repo_slug=f"page-repo-{index:02d}",
                build_name=f"Page Build {index:02d}",
                build_id=f"page-build-{index:02d}",
                plan_key=f"PAGE{index:02d}",
                with_active_definition=True,
            )

        response = self.client.get("/", {"q": "PAG", "page": "2"})

        self.assertEqual(200, response.status_code)
        projects = list(response.context["projects"])
        self.assertEqual(1, len(projects))
        self.assertEqual("PAG10", projects[0]["jiraProjectKey"])
        self.assertEqual("q=PAG&", response.context["paginationBaseQuery"])
        self.assertContains(response, "?q=PAG&amp;page=1")

    def test_project_list_partial_request_returns_only_list_panel(self) -> None:
        for index in range(11):
            self._create_project_with_build(
                jira_project_key=f"AJX{index:02d}",
                bitbucket_project_key="AJAX",
                repo_slug=f"ajax-repo-{index:02d}",
                build_name=f"Ajax Build {index:02d}",
                build_id=f"ajax-build-{index:02d}",
                plan_key=f"AJAX{index:02d}",
                with_active_definition=True,
            )

        response = self.client.get(
            "/",
            {"page": "2", "partial": "project-list"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'data-project-list-container', html=False)
        self.assertContains(response, "AJX10")
        self.assertNotContains(response, "<!doctype html>", html=False)
        self.assertNotContains(response, "Operations Radar")

    def test_project_list_shows_latest_failed_build_panel(self) -> None:
        self._create_project_with_build(
            jira_project_key="FAIL",
            bitbucket_project_key="FAIL",
            repo_slug="fail-api",
            build_name="Fail API",
            build_id="fail-api",
            plan_key="FAILAPI",
            with_active_definition=True,
            latest_success=False,
            build_number="42",
            result_status="failed",
            summary_message="Compilation failed",
        )

        response = self.client.get("/")

        self.assertContains(response, "최근 실패 빌드")
        self.assertContains(response, "Fail API")
        self.assertContains(response, "FAIL / FAILAPI")
        self.assertContains(response, "Version v1.0.0")
        self.assertContains(response, "Build #42")
        self.assertContains(response, "Compilation failed")

    def test_project_list_shows_generation_warning_tags_for_attention_projects(self) -> None:
        self._create_project_with_build(
            jira_project_key="WARN",
            bitbucket_project_key="WARN",
            repo_slug="warn-api",
            build_name="Warn API",
            build_id="warn-api",
            plan_key="WARNAPI",
            representative_repo_slug="missing-repo",
            coverity_project="",
            coverity_stream="",
            with_active_definition=False,
        )

        response = self.client.get("/")

        self.assertContains(response, "대표 저장소 메타데이터 불일치")
        self.assertContains(response, "Coverity 미지정 1")

    def test_project_detail_renders_generation_panel(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "프로젝트 상태")
        self.assertContains(response, "정상")
        self.assertContains(response, "프로젝트 수정")
        self.assertContains(response, "저장소 추가")
        self.assertContains(response, "빌드 추가")
        self.assertContains(response, 'id="project-edit-panel"', html=False)
        self.assertContains(response, 'name="jira_project_key"', html=False)
        self.assertContains(response, 'value="SAMPLE"', html=False)
        self.assertContains(response, "hidden", html=False)

    def test_project_detail_renders_metadata_sections(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "저장소 목록")
        self.assertContains(response, "빌드 목록")
        self.assertContains(response, "sample-app-api")
        self.assertContains(response, "Sample API")
        self.assertContains(response, "/projects/SAMPLE/repositories/sample-app-api/")
        self.assertContains(response, "/projects/SAMPLE/builds/SAMPAPI/")

    def test_project_detail_renders_generation_issues_for_unready_project(self) -> None:
        payload = self._create_project_with_build(
            jira_project_key="UNREADY",
            bitbucket_project_key="UNREADY",
            repo_slug="unready-api",
            build_name="Unready API",
            build_id="unready-api",
            plan_key="UNREADYAPI",
            representative_repo_slug="missing-repo",
            with_active_definition=False,
        )

        response = self.client.get("/projects/UNREADY/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "연결 점검 필요")
        self.assertContains(response, "점검 필요")
        self.assertContains(response, "대표 저장소 메타데이터 불일치")
        self.assertContains(response, "unready-api")

    def test_project_detail_returns_empty_state_for_missing_project(self) -> None:
        response = self.client.get("/projects/MISSING/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "프로젝트를 찾을 수 없습니다.")
        self.assertContains(response, "프로젝트 목록으로 돌아가기")

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

    def test_project_registration_from_main_page_requires_at_least_one_repository(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "OPS",
                "bitbucket_project_key": "OPS",
                "representative_repo_slug": "ops-api",
                "repo_slug": [""],
                "coverity_project": [""],
                "coverity_stream": [""],
                "build_name": ["Operations API"],
                "build_type": ["python"],
                "runtime_stack": ["python3.12"],
                "build_id": ["ops-api"],
                "plan_key": ["OPSAPI"],
                "build_repository_slug": ["ops-api"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "최소 1개 저장소를 입력해 주세요.", html=False)
        self.assertNotContains(response, 'id="project-registration-panel" hidden', html=False)

    def test_project_registration_from_main_page_requires_at_least_one_build(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "OPS",
                "bitbucket_project_key": "OPS",
                "representative_repo_slug": "ops-api",
                "repo_slug": ["ops-api"],
                "coverity_project": [""],
                "coverity_stream": [""],
                "build_name": [""],
                "build_type": [""],
                "runtime_stack": [""],
                "build_id": [""],
                "plan_key": [""],
                "build_repository_slug": [""],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "최소 1개 빌드를 입력해 주세요.", html=False)
        self.assertNotContains(response, 'id="project-registration-panel" hidden', html=False)

    def test_project_registration_from_main_page_rejects_duplicate_repository_slug_in_request(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "OPS",
                "bitbucket_project_key": "OPS",
                "representative_repo_slug": "ops-api",
                "repo_slug": ["ops-api", "ops-api"],
                "coverity_project": ["", ""],
                "coverity_stream": ["", ""],
                "build_name": ["Operations API"],
                "build_type": ["python"],
                "runtime_stack": ["python3.12"],
                "build_id": ["ops-api"],
                "plan_key": ["OPSAPI"],
                "build_repository_slug": ["ops-api"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Repository")
        self.assertContains(response, "ops-api")
        self.assertContains(response, "duplicated in the request.")
        self.assertNotContains(response, 'id="project-registration-panel" hidden', html=False)

    def test_project_registration_from_main_page_rejects_duplicate_build_identity_in_request(self) -> None:
        response = self.client.post(
            "/",
            data={
                "jira_project_key": "OPS",
                "bitbucket_project_key": "OPS",
                "representative_repo_slug": "ops-api",
                "repo_slug": ["ops-api"],
                "coverity_project": [""],
                "coverity_stream": [""],
                "build_name": ["Operations API", "Operations API Clone"],
                "build_type": ["python", "python"],
                "runtime_stack": ["python3.12", "python3.12"],
                "build_id": ["ops-api", "ops-api"],
                "plan_key": ["OPSAPI", "OPSAPI2"],
                "build_repository_slug": ["ops-api", "ops-api"],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Build buildId")
        self.assertContains(response, "ops-api")
        self.assertContains(response, "duplicated in the request.")
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
        self.assertEqual(
            "Build repositorySlug 'missing-repo' is not registered in repositories.",
            response.context["registrationError"],
        )
        self.assertNotContains(response, 'id="project-registration-panel" hidden', html=False)

    def test_project_detail_update_changes_only_project_metadata(self) -> None:
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
                "form_kind": "project",
                "bitbucket_project_key": "SAMPLE-NEW",
                "representative_repo_slug": "sample-app-web",
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/", response["Location"])
        self.project.refresh_from_db()
        self.assertEqual("SAMPLE-NEW", self.project.bitbucket_project_key)
        self.assertEqual("sample-app-web", self.project.representative_repo_slug)
        self.assertEqual(2, ProjectRepository.objects.filter(project=self.project).count())
        self.assertEqual(2, ProjectBuild.objects.filter(project=self.project).count())
        self.assertTrue(ProjectRepository.objects.filter(project=self.project, repo_slug="sample-app-web").exists())
        self.assertTrue(ProjectRepository.objects.filter(project=self.project, repo_slug="sample-app-api").exists())
        self.assertTrue(ProjectBuild.objects.filter(project=self.project, build_plan__plan_key="SAMPWEB").exists())
        self.assertTrue(ProjectBuild.objects.filter(project=self.project, build_plan__plan_key="SAMPAPI").exists())

    def test_project_detail_update_reopens_panel_on_validation_error(self) -> None:
        response = self.client.post(
            "/projects/SAMPLE/",
            data={
                "form_kind": "project",
                "bitbucket_project_key": "SAMPLE",
                "representative_repo_slug": "missing-repo",
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "대표 저장소는 등록한 저장소 목록 중 하나여야 합니다.", html=False)
        self.assertNotContains(response, 'id="project-edit-panel" hidden', html=False)

    def test_project_detail_update_renders_prefilled_metadata(self) -> None:
        response = self.client.get("/projects/SAMPLE/?edit=1")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'value="SAMPLE"', html=False)
        self.assertContains(response, 'value="sample-app-api"', html=False)
        self.assertContains(response, 'value="SAMPLE"', html=False)
        self.assertNotContains(response, 'id="project-edit-panel" hidden', html=False)

    def test_project_registration_form_lists_existing_metadata_as_suggestions(self) -> None:
        self._create_project_with_build(
            jira_project_key="OPS",
            bitbucket_project_key="OPS",
            repo_slug="ops-api",
            build_name="Operations API",
            build_id="ops-api",
            plan_key="OPSAPI",
            with_active_definition=True,
            coverity_project="ops-coverity",
            coverity_stream="ops-main",
        )

        response = self.client.get("/")

        self.assertContains(response, '<option value="SAMPLE"></option>', html=False)
        self.assertContains(response, '<option value="OPS"></option>', html=False)
        self.assertContains(response, '<option value="sample-app-api"></option>', html=False)
        self.assertContains(response, '<option value="ops-api"></option>', html=False)
        self.assertContains(response, '<option value="ops-coverity"></option>', html=False)
        self.assertContains(response, '<option value="ops-main"></option>', html=False)

    def test_project_detail_renders_repository_index(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "저장소 목록")
        self.assertContains(response, "저장소 추가")
        self.assertContains(response, "sample-app-api")
        self.assertContains(response, "/projects/SAMPLE/repositories/sample-app-api/")

    def test_project_detail_adds_repository(self) -> None:
        response = self.client.post(
            "/projects/SAMPLE/",
            data={
                "form_kind": "repository",
                "repo_slug": "sample-app-web",
                "coverity_project": "sample-app-web",
                "coverity_stream": "sample-app-web-dev",
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/repositories/sample-app-web/", response["Location"])
        self.assertTrue(ProjectRepository.objects.filter(project=self.project, repo_slug="sample-app-web").exists())

    def test_project_repository_detail_renders_linked_builds(self) -> None:
        response = self.client.get("/projects/SAMPLE/repositories/sample-app-api/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "저장소 메타데이터")
        self.assertContains(response, "연결된 빌드")
        self.assertContains(response, "Sample API")

    def test_project_detail_renders_build_index(self) -> None:
        response = self.client.get("/projects/SAMPLE/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "빌드 목록")
        self.assertContains(response, "빌드 추가")
        self.assertContains(response, "Sample API")
        self.assertContains(response, "/projects/SAMPLE/builds/SAMPAPI/")

    def test_project_detail_adds_build(self) -> None:
        ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-web",
            coverity_project="sample-app-web",
            coverity_stream="sample-app-web-dev",
            is_representative=False,
        )

        response = self.client.post(
            "/projects/SAMPLE/",
            data={
                "form_kind": "build",
                "build_name": "Sample Web",
                "build_type": "node",
                "runtime_stack": "node20",
                "build_id": "sample-app-web",
                "plan_key": "SAMPWEB",
                "build_repository_slug": "sample-app-web",
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/builds/SAMPWEB/", response["Location"])
        self.assertTrue(ProjectBuild.objects.filter(project=self.project, build_plan__plan_key="SAMPWEB").exists())

    def test_project_build_detail_renders_build_metadata(self) -> None:
        BuildPlanBuildInfo.objects.create(
            build_plan=BuildPlan.objects.get(plan_key="SAMPAPI"),
            build_key="api-linux",
            language="java",
            compiler="maven",
            coverity_stream="sample-api-dev",
        )
        response = self.client.get("/projects/SAMPLE/builds/SAMPAPI/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "빌드 플랜 메타데이터")
        self.assertContains(response, "빌드 플랜 수정")
        self.assertContains(response, "빌드 정보")
        self.assertContains(response, 'id="build-plan-metadata-panel"', html=False)
        self.assertContains(response, 'id="build-plan-metadata-panel" hidden', html=False)
        self.assertContains(response, "api-linux")
        self.assertContains(response, "연결 정보")
        self.assertContains(response, "sample-app-api")

    def test_project_build_detail_updates_build_plan_metadata(self) -> None:
        response = self.client.post(
            "/projects/SAMPLE/builds/SAMPAPI/",
            data={
                "form_kind": "build_plan_metadata",
                "static_analysis_tool_version": "coverity-2024.12",
                "coverity_project": "sample-api-coverity",
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/builds/SAMPAPI/", response["Location"])
        build_plan = BuildPlan.objects.get(plan_key="SAMPAPI")
        self.assertEqual("coverity-2024.12", build_plan.static_analysis_tool_version)
        self.assertEqual("sample-api-coverity", build_plan.coverity_project)

    def test_project_build_detail_registers_build_info(self) -> None:
        response = self.client.post(
            "/projects/SAMPLE/builds/SAMPAPI/",
            data={
                "form_kind": "build_info",
                "build_key": "api-linux",
                "pre_process": "source env.sh",
                "build_command": "mvn -B clean package",
                "clean_command": "mvn -B clean",
                "language": "java",
                "compiler": "maven",
                "analysis_excluded_files": "generated/**",
                "coverity_stream": "sample-api-dev",
                "build_sub_path": "services/api",
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/builds/SAMPAPI/", response["Location"])
        build_info = BuildPlanBuildInfo.objects.get(build_plan__plan_key="SAMPAPI", build_key="api-linux")
        self.assertEqual("java", build_info.language)
        self.assertEqual("services/api", build_info.build_sub_path)

    def test_project_build_info_list_redirects_to_build_detail_panel(self) -> None:
        response = self.client.get("/projects/SAMPLE/builds/SAMPAPI/infos/")

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/builds/SAMPAPI/?add_build_info=open", response["Location"])

    def test_project_build_info_detail_updates_build_info(self) -> None:
        BuildPlanBuildInfo.objects.create(
            build_plan=BuildPlan.objects.get(plan_key="SAMPAPI"),
            build_key="api-linux",
            language="java",
            compiler="maven",
            coverity_stream="sample-api-dev",
        )

        response = self.client.post(
            "/projects/SAMPLE/builds/SAMPAPI/infos/api-linux/",
            data={
                "build_key": "api-linux",
                "pre_process": "source env.sh",
                "build_command": "mvn -B verify",
                "clean_command": "mvn -B clean",
                "language": "java17",
                "compiler": "maven3.9",
                "analysis_excluded_files": "generated/**",
                "coverity_stream": "sample-api-release",
                "build_sub_path": "services/api",
            },
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/projects/SAMPLE/builds/SAMPAPI/infos/api-linux/", response["Location"])
        build_info = BuildPlanBuildInfo.objects.get(build_plan__plan_key="SAMPAPI", build_key="api-linux")
        self.assertEqual("java17", build_info.language)
        self.assertEqual("sample-api-release", build_info.coverity_stream)
