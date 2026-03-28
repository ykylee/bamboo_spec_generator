from __future__ import annotations

import json
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.buildmeta.models import (
    BambooBuildInfo,
    BambooBuildUnit,
    BuildUnit,
    BuildVersion,
    ModuleAsset,
    ModuleLoadSnapshot,
    Project,
    Repository,
    SystemSetting,
)
from apps.buildmeta.services.executions import finish_execution, start_execution


class ApiSmokeTest(TestCase):
    def setUp(self) -> None:
        os.environ["BAMBOO_API_TOKEN"] = "test-token"
        self.project = Project.objects.create(
            project_key="SAMPLE",
            name="SAMPLE",
            ci_provider=Project.PROVIDER_BAMBOO,
            status=Project.STATUS_ACTIVE,
        )
        self.repository = Repository.objects.create(
            project=self.project,
            repo_type=Repository.TYPE_BITBUCKET,
            repo_key="SAMPLE",
            repo_slug="sample-app-api",
            default_branch="dev",
            is_representative=True,
            coverity_project="sample-app",
            coverity_stream="sample-app-dev",
        )
        self.project.representative_repository = self.repository
        self.project.save(update_fields=["representative_repository", "updated_at"])
        self.build_unit = BuildUnit.objects.create(
            project=self.project,
            repository=self.repository,
            ci_provider=Project.PROVIDER_BAMBOO,
            unit_type=BuildUnit.TYPE_BUILD,
            external_key="SAMPAPI",
            display_name="backend",
            language="java",
            compiler="python",
            runtime_stack="java",
            lifecycle_status=BuildUnit.STATUS_ACTIVE,
            is_enabled=True,
        )
        self.bamboo_unit = BambooBuildUnit.objects.create(
            build_unit=self.build_unit,
            bamboo_project_key="SAMPLE",
            plan_key="SAMPAPI",
            build_id="sample-app-api",
            application_link="BITBUCKET_SERVER",
            repository_linkage_mode="",
        )
        BambooBuildInfo.objects.create(
            bamboo_build_unit=self.bamboo_unit,
            build_key="api-linux",
            operating_system="linux",
            pre_process="mvn -B dependency:go-offline",
            build_command="mvn -B clean package",
            language="java",
            compiler="maven",
            build_sub_path="services/sample-app-api",
        )
        self.auth_headers = {"HTTP_AUTHORIZATION": "Bearer test-token"}

    def test_active_definition_endpoint(self) -> None:
        response = self.client.get("/api/v1/build-plans/SAMPAPI/active-definition", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("SAMPAPI", payload["planKey"])
        self.assertEqual("sample-app-api", payload["definition"]["buildId"])
        self.assertEqual("BITBUCKET_SERVER", payload["definition"]["repository"]["applicationLink"])
        self.assertEqual("services/sample-app-api", payload["definition"]["build"]["subPath"])

    def test_prepare_context_endpoint(self) -> None:
        response = self.client.get("/api/v1/build-plans/SAMPAPI/prepare-context", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("SAMPLE", payload["project"]["jiraProjectKey"])
        self.assertEqual("sample-app-api", payload["variables"]["BITBUCKET_REPO_SLUG"])
        self.assertEqual("BITBUCKET_SERVER", payload["variables"]["BITBUCKET_APPLICATION_LINK"])
        self.assertEqual("BITBUCKET_SERVER", payload["currentRepository"]["applicationLink"])
        self.assertEqual("linked", payload["currentRepository"]["linkageMode"])

    def test_prepare_context_endpoint_uses_create_if_missing_when_git_clone_template_exists(self) -> None:
        SystemSetting.objects.create(
            key=SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE,
            value="https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
        )
        SystemSetting.objects.create(
            key=SystemSetting.KEY_REPOSITORY_LINKAGE_MODE,
            value="create_if_missing",
        )

        response = self.client.get("/api/v1/build-plans/SAMPAPI/prepare-context", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("create_if_missing", payload["currentRepository"]["linkageMode"])
        self.assertEqual(
            "https://git.example.com/scm/sample/sample-app-api.git",
            payload["currentRepository"]["cloneUrl"],
        )
        self.assertEqual("create_if_missing", payload["variables"]["currentRepository.linkageMode"])

    def test_prepare_context_endpoint_keeps_linked_mode_when_only_git_clone_template_exists(self) -> None:
        SystemSetting.objects.create(
            key=SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE,
            value="https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
        )

        response = self.client.get("/api/v1/build-plans/SAMPAPI/prepare-context", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("linked", payload["currentRepository"]["linkageMode"])

    def test_execution_start_and_finish_endpoints(self) -> None:
        start_response = self.client.post(
            "/api/v1/build-plans/SAMPAPI/executions/start",
            data=json.dumps(
                {
                    "branchKind": "dev",
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
            branch_kind="dev",
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
            branch_kind="dev",
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

    def test_project_list_and_detail_include_generation_readiness(self) -> None:
        response = self.client.get("/api/v1/projects/", **self.auth_headers)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(1, len(payload))
        self.assertTrue(payload[0]["generationReady"])
        self.assertEqual(0, payload[0]["activeDefinitionCount"])

        detail_response = self.client.get("/api/v1/projects/SAMPLE", **self.auth_headers)
        self.assertEqual(200, detail_response.status_code)
        detail_payload = detail_response.json()
        self.assertTrue(detail_payload["generation"]["generationReady"])
        self.assertEqual("", detail_payload["builds"][0]["activeDefinitionYear"])

    def test_project_create_endpoint_registers_project_with_builds(self) -> None:
        response = self.client.post(
            "/api/v1/projects/",
            data=json.dumps(
                {
                    "jiraProjectKey": "NEWPROJ",
                    "bitbucketProjectKey": "NEWPROJ",
                    "representativeRepoSlug": "new-service",
                    "repositories": [
                        {
                            "repoSlug": "new-service",
                            "coverityProject": "new-service",
                            "coverityStream": "new-service-dev",
                            "isRepresentative": True,
                        }
                    ],
                    "builds": [
                        {
                            "buildName": "api",
                            "buildType": "python",
                            "runtimeStack": "python3.12",
                            "buildId": "new-service-api",
                            "planKey": "NEWSVCAPI",
                            "repositorySlug": "new-service",
                        }
                    ],
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("NEWPROJ", payload["jiraProjectKey"])
        self.assertFalse(payload["generation"]["generationReady"])
        self.assertEqual(["빌드 정보 없음 1"], payload["generation"]["generationReadinessIssues"])

    def test_coverity_system_settings_endpoints(self) -> None:
        response = self.client.put(
            "/api/v1/system-settings/coverity",
            data=json.dumps(
                {
                    "connectUrl": "https://coverity.example.com",
                    "onNewCert": "trust",
                    "commitEnabled": True,
                    "repositoryLinkageMode": "create_if_missing",
                    "gitCloneUrlTemplate": "https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("https://coverity.example.com", payload["connectUrl"])
        self.assertTrue(payload["commitEnabled"])
        self.assertEqual("create_if_missing", payload["repositoryLinkageMode"])
        self.assertEqual(
            "https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
            payload["gitCloneUrlTemplate"],
        )
        self.assertEqual("https://coverity.example.com", SystemSetting.objects.get(key="coverity.connect.url").value)

    def test_specs_draft_initialize_endpoint_creates_build_info(self) -> None:
        response = self.client.post(
            "/api/v1/system-settings/specs-drafts/initialize?resetExisting=true",
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(0, payload["initializedCount"])
        self.assertEqual(1, payload["updatedCount"])
        build_info = BambooBuildInfo.objects.get(bamboo_build_unit=self.bamboo_unit, build_key="api-linux")
        self.assertEqual("linux", build_info.operating_system)
        self.assertEqual("services/sample-app-api", build_info.build_sub_path)

    def test_specs_draft_initialize_endpoint_preserves_multiple_build_infos(self) -> None:
        BambooBuildInfo.objects.create(
            bamboo_build_unit=self.bamboo_unit,
            build_key="api-windows",
            operating_system="windows",
            pre_process="setup.bat",
            build_command="mvn -B verify -Pwindows",
            clean_command="mvn -B clean",
            analysis_excluded_files="generated/**",
            language="java",
            compiler="maven",
            coverity_stream="",
            build_sub_path="services/windows",
        )

        response = self.client.post(
            "/api/v1/system-settings/specs-drafts/initialize?resetExisting=true",
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(2, payload["updatedCount"])
        self.assertEqual(2, BambooBuildInfo.objects.filter(bamboo_build_unit=self.bamboo_unit).count())
        self.assertEqual(
            {"api-linux", "api-windows"},
            set(self.bamboo_unit.build_infos.values_list("build_key", flat=True)),
        )

    def test_specs_draft_initialize_plan_endpoint_refreshes_existing_build_info(self) -> None:
        self.build_unit.definitions.all().delete()
        BambooBuildInfo.objects.create(
            bamboo_build_unit=self.bamboo_unit,
            build_key="main",
            operating_system="",
            language="",
            compiler="",
            coverity_stream="",
            build_sub_path="",
        )

        response = self.client.post(
            f"/api/v1/system-settings/specs-drafts/initialize/{self.bamboo_unit.plan_key}",
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(2, payload["updatedCount"])
        build_info = BambooBuildInfo.objects.get(bamboo_build_unit=self.bamboo_unit, build_key="main")
        self.assertEqual(".", build_info.build_sub_path)
        self.assertEqual("sample-app-dev", build_info.coverity_stream)

    def test_project_update_endpoint_updates_metadata_and_links(self) -> None:
        response = self.client.put(
            "/api/v1/projects/SAMPLE",
            data=json.dumps(
                {
                    "bitbucketProjectKey": "SAMPLE2",
                    "representativeRepoSlug": "sample-app-api",
                    "repositories": [
                        {
                            "repoSlug": "sample-app-api",
                            "coverityProject": "sample-app",
                            "coverityStream": "sample-app-release",
                            "isRepresentative": True,
                        }
                    ],
                    "builds": [
                        {
                            "buildName": "backend-api",
                            "buildType": "java",
                            "runtimeStack": "java17",
                            "buildId": "sample-app-api",
                            "planKey": "SAMPAPI",
                            "repositorySlug": "sample-app-api",
                        }
                    ],
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("SAMPLE2", payload["bitbucketProjectKey"])
        self.assertEqual("backend-api", payload["builds"][0]["buildName"])
        self.assertEqual("sample-app-release", payload["repositories"][0]["coverityStream"])
        self.assertEqual("sample-app-api", payload["builds"][0]["repositorySlug"])
        self.build_unit.refresh_from_db()
        self.assertEqual("backend-api", self.build_unit.display_name)
        self.assertEqual("java", self.build_unit.compiler)
        self.assertEqual("java17", self.build_unit.runtime_stack)
        self.repository.refresh_from_db()
        self.assertEqual("SAMPLE2", self.repository.repo_key)
        self.assertEqual("sample-app-release", self.repository.coverity_stream)

    def test_module_registry_upload_list_and_reload_endpoints(self) -> None:
        stage_upload = SimpleUploadedFile(
            "prepare.json",
            b'{"apiVersion":"buildmod/v1alpha1","kind":"StageModule","metadata":{"id":"prepare","name":"Prepare"},"spec":{"order":10,"enabled":true,"jobs":["prepare-linux"]}}',
            content_type="application/json",
        )
        job_upload = SimpleUploadedFile(
            "prepare-linux.json",
            b'{"apiVersion":"buildmod/v1alpha1","kind":"JobModule","metadata":{"id":"prepare-linux","name":"Prepare Linux"},"spec":{"ciProvider":"bamboo","enabled":true,"tasks":["bamboo-prepare-python"]}}',
            content_type="application/json",
        )
        task_upload = SimpleUploadedFile(
            "bamboo-prepare-python.json",
            b'{"apiVersion":"buildmod/v1alpha1","kind":"BambooTaskModule","metadata":{"id":"bamboo-prepare-python","name":"Bamboo Prepare Python"},"spec":{"taskKind":"script"}}',
            content_type="application/json",
        )

        upload_response = self.client.post(
            "/api/v1/admin/modules/uploads",
            data={
                "assetKind": "stage_module",
                "providerScope": "common",
                "moduleId": "prepare",
                "activateAfterUpload": "true",
                "file": stage_upload,
            },
            **self.auth_headers,
        )

        self.assertEqual(200, upload_response.status_code)
        upload_payload = upload_response.json()
        self.assertEqual("valid", upload_payload["validationStatus"])

        self.client.post(
            "/api/v1/admin/modules/uploads",
            data={
                "assetKind": "job_module",
                "providerScope": "common",
                "moduleId": "prepare-linux",
                "activateAfterUpload": "true",
                "file": job_upload,
            },
            **self.auth_headers,
        )
        self.client.post(
            "/api/v1/admin/modules/uploads",
            data={
                "assetKind": "task_module",
                "providerScope": "bamboo",
                "moduleId": "bamboo-prepare-python",
                "activateAfterUpload": "true",
                "file": task_upload,
            },
            **self.auth_headers,
        )

        list_response = self.client.get("/api/v1/admin/modules/", **self.auth_headers)
        self.assertEqual(200, list_response.status_code)
        list_payload = list_response.json()
        self.assertEqual(3, len(list_payload))
        self.assertEqual({"prepare", "prepare-linux", "bamboo-prepare-python"}, {item["moduleId"] for item in list_payload})

        reload_response = self.client.post(
            "/api/v1/admin/modules/reload",
            data=json.dumps({}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(200, reload_response.status_code)
        reload_payload = reload_response.json()
        self.assertEqual("success", reload_payload["status"])
        self.assertEqual(3, reload_payload["loadedCount"])

        status_response = self.client.get("/api/v1/admin/modules/load-status", **self.auth_headers)
        self.assertEqual(200, status_response.status_code)
        status_payload = status_response.json()
        self.assertEqual(3, status_payload["activeAssetCount"])
        self.assertEqual(1, ModuleLoadSnapshot.objects.count())
