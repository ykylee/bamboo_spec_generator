from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest.mock import Mock, patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from apps.buildmeta.models import (
    BuildDefinitionHistory,
    BuildExecution,
    BuildPlan,
    BuildPlanBuildInfo,
    BuildPlanDefinition,
    BuildVersion,
    Project,
    ProjectBuild,
    ProjectRepository,
    StaticAnalysisResult,
    SystemSetting,
)
from apps.buildmeta.selectors.definitions import (
    get_active_definition_by_plan_key,
    get_build_plan_export_draft,
    get_build_plan_preview,
)
from apps.buildmeta.services import (
    build_git_clone_url,
    create_project,
    get_coverity_system_settings,
    get_system_setting,
    initialize_specs_draft_data,
    initialize_specs_draft_for_plan,
    load_definition_import_records,
    set_system_setting,
    sync_definition_records,
    update_project,
)
from apps.buildmeta.services.executions import finish_execution, record_static_analysis_results, start_execution
from src.bamboo_spec_generator.parser import parse_build_definition_payload
from src.bamboo_spec_generator.validator import ValidationError, is_no_build_language, validate_build_definitions


class ExecutionServiceTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        self.plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")
        self.build_info = BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-linux",
            language="java",
            compiler="maven",
        )

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

    def test_same_commit_on_different_branches_reuses_single_version(self) -> None:
        dev_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )
        release_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_RELEASE,
            commit_hash="abcdef123456",
            build_number="102",
        )

        self.assertEqual("v0.0.1", dev_payload["version"])
        self.assertEqual("v0.0.1", release_payload["version"])
        self.assertTrue(release_payload["reusedExistingVersion"])
        self.assertEqual(1, BuildVersion.objects.count())

    def test_same_build_number_reuses_existing_execution(self) -> None:
        first_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )
        second_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )

        self.assertEqual(first_payload["buildExecutionId"], second_payload["buildExecutionId"])
        self.assertEqual(1, BuildExecution.objects.count())
        self.assertTrue(second_payload["reusedExistingVersion"])

    def test_rebuilding_older_version_does_not_move_latest_pointer_backwards(self) -> None:
        first_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="commit-a",
            build_number="101",
        )
        second_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="commit-b",
            build_number="102",
        )

        finish_execution(
            execution_id=second_payload["buildExecutionId"],
            success=True,
            result_status="successful",
        )
        finish_execution(
            execution_id=first_payload["buildExecutionId"],
            success=True,
            result_status="successful",
        )

        self.plan.refresh_from_db()
        self.assertEqual("v0.0.2", self.plan.latest_version.version_text)

    def test_finish_execution_does_not_overwrite_failure_with_success(self) -> None:
        start_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )

        finish_execution(
            execution_id=start_payload["buildExecutionId"],
            success=False,
            result_status="failed",
            summary_message="Coverity failed",
            stage_name="Static Analysis",
            job_name="Coverity Scan",
            task_name="run_coverity.py",
        )
        finish_payload = finish_execution(
            execution_id=start_payload["buildExecutionId"],
            success=True,
            result_status="successful",
            summary_message="Follow-up succeeded",
            stage_name="Trigger Follow-up",
            job_name="Follow-up Trigger",
            task_name="trigger_follow_up.py",
        )

        execution = BuildExecution.objects.get(pk=start_payload["buildExecutionId"])
        self.assertFalse(execution.success)
        self.assertEqual("failed", execution.result_status)
        self.assertEqual("run_coverity.py", execution.task_name)
        self.assertFalse(finish_payload["success"])

    def test_record_static_analysis_results_upserts_by_tool_name(self) -> None:
        start_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
        )

        record_static_analysis_results(
            execution_id=start_payload["buildExecutionId"],
            static_analysis_results=[
                {"toolName": "coverity", "status": "passed", "summary": "initial", "metricsJson": {"high": 0}},
            ],
        )
        record_static_analysis_results(
            execution_id=start_payload["buildExecutionId"],
            static_analysis_results=[
                {"toolName": "coverity", "status": "failed", "summary": "updated", "metricsJson": {"high": 1}},
            ],
        )

        result = StaticAnalysisResult.objects.get(build_execution_id=start_payload["buildExecutionId"], tool_name="coverity")
        self.assertEqual("failed", result.status)
        self.assertEqual("updated", result.summary)
        self.assertEqual({"high": 1}, result.metrics_json)

    def test_same_build_number_allows_multiple_build_infos(self) -> None:
        second_build_info = BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-windows",
            language="java",
            compiler="maven",
        )

        first_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
            build_key=self.build_info.build_key,
        )
        second_payload = start_execution(
            plan_key="SAMPAPI",
            branch_kind=BuildVersion.BRANCH_KIND_DEV,
            commit_hash="abcdef123456",
            build_number="101",
            build_key=second_build_info.build_key,
        )

        self.assertNotEqual(first_payload["buildExecutionId"], second_payload["buildExecutionId"])
        self.assertEqual(2, BuildExecution.objects.count())
        self.assertEqual("api-linux", first_payload["buildKey"])
        self.assertEqual("api-windows", second_payload["buildKey"])


class DefinitionSelectorTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        self.plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")

    def test_active_definition_endpoint_synthesizes_definition_from_registered_metadata(self) -> None:
        repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            is_representative=True,
        )
        ProjectBuild.objects.create(
            project=self.project,
            repository=repository,
            build_plan=self.plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-linux",
            operating_system="linux",
            pre_process="mvn -B dependency:go-offline",
            build_command="mvn -B clean package",
            language="java",
            compiler="maven",
            build_sub_path="services/sample-app-api",
        )

        payload = get_active_definition_by_plan_key("SAMPAPI")

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("sample-app-api", payload["definition"]["buildId"])
        self.assertEqual("BITBUCKET_SERVER", payload["definition"]["repository"]["applicationLink"])
        self.assertEqual("services/sample-app-api", payload["definition"]["build"]["subPath"])

    def test_active_definition_uses_create_if_missing_when_git_clone_template_exists(self) -> None:
        repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            is_representative=True,
        )
        ProjectBuild.objects.create(
            project=self.project,
            repository=repository,
            build_plan=self.plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-linux",
            operating_system="linux",
            language="java",
            compiler="maven",
        )
        set_system_setting(
            key=SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE,
            value="https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
        )

        payload = get_active_definition_by_plan_key("SAMPAPI")

        assert payload is not None
        self.assertEqual("create_if_missing", payload["definition"]["repository"]["linkageMode"])
        self.assertEqual(
            "https://git.example.com/scm/sample/sample-app-api.git",
            payload["definition"]["repository"]["cloneUrl"],
        )


    def test_build_plan_preview_maps_build_infos_to_jobs(self) -> None:
        repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            is_representative=True,
        )
        ProjectBuild.objects.create(
            project=self.project,
            repository=repository,
            build_plan=self.plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-linux",
            operating_system="linux",
            pre_process="source env.sh",
            build_command="mvn -B verify",
            clean_command="mvn -B clean",
            language="java17",
            compiler="maven3.9",
            analysis_excluded_files="generated/**",
            coverity_stream="sample-api-dev",
            build_sub_path="services/api",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-windows",
            operating_system="windows",
            language="java",
            compiler="maven",
            coverity_stream="sample-api-win",
            build_sub_path="services/sample-app-api",
        )

        payload = get_build_plan_preview("SAMPAPI")

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("SAMPAPI", payload["plan"]["planKey"])
        self.assertEqual(4, len(payload["jobs"]))
        self.assertEqual(
            ["Prepare", "Build", "Analysis", "Post Process"],
            [stage["name"] for stage in payload["stages"]],
        )
        self.assertEqual("plan-prepare", payload["jobs"][0]["jobId"])
        self.assertEqual("api-linux", payload["jobs"][1]["buildKey"])
        self.assertEqual("linux", payload["jobs"][1]["operatingSystem"])
        self.assertEqual("mvn -B verify", payload["jobs"][1]["buildCommand"])
        self.assertEqual("services/sample-app-api", payload["jobs"][2]["buildSubPath"])
        self.assertEqual("plan-trigger", payload["jobs"][3]["jobId"])
        self.assertEqual("Register Build Start", payload["jobs"][0]["taskGroups"][0]["tasks"][0]["name"])
        self.assertEqual("Publish Report", payload["jobs"][1]["taskGroups"][1]["tasks"][3]["name"])

    def test_build_plan_export_draft_renders_job_files(self) -> None:
        repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-api",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            is_representative=True,
        )
        ProjectBuild.objects.create(
            project=self.project,
            repository=repository,
            build_plan=self.plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="api-linux",
            operating_system="linux",
            pre_process="source env.sh",
            build_command="mvn -B verify",
            clean_command="mvn -B clean",
            language="java",
            compiler="maven",
            coverity_stream="sample-api-dev",
            build_sub_path="services/api",
        )

        payload = get_build_plan_export_draft("SAMPAPI")

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("SAMPAPI", payload["summary"]["planKey"])
        self.assertTrue(any(file["path"].endswith("coverity.yaml") for file in payload["files"]))
        self.assertTrue(any(file["path"].endswith("prepare_build.py") for file in payload["files"]))
        self.assertTrue(any(file["path"].endswith("run_coverity.py") for file in payload["files"]))
        self.assertTrue(any(file["path"].endswith("run_custom_analysis.py") for file in payload["files"]))
        self.assertTrue(any(file["path"].endswith("trigger_follow_up.py") for file in payload["files"]))
        self.assertFalse(any(file["path"].endswith("manifest.json") for file in payload["files"]))
        self.assertTrue(any("mvn -B verify" in file["content"] for file in payload["files"]))
        self.assertTrue(any(file["path"].endswith("run_build.sh") for file in payload["files"]))

    def test_build_plan_preview_omits_build_stage_for_python_without_build_commands(self) -> None:
        repository = ProjectRepository.objects.create(
            project=self.project,
            repo_slug="sample-app-script",
            coverity_project="sample-app-script",
            coverity_stream="sample-script-dev",
            is_representative=True,
        )
        ProjectBuild.objects.create(
            project=self.project,
            repository=repository,
            build_plan=self.plan,
            build_name="Sample Script",
            build_type="python",
            runtime_stack="python3.12",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=self.plan,
            build_key="script-linux",
            operating_system="linux",
            language="python",
            compiler="python",
            build_command="",
            clean_command="",
        )

        payload = get_build_plan_preview("SAMPAPI")

        assert payload is not None
        build_stage = next(stage for stage in payload["stages"] if stage["id"] == "build")
        prepare_stage = next(stage for stage in payload["stages"] if stage["id"] == "prepare")
        self.assertEqual(1, prepare_stage["jobCount"])
        self.assertEqual(0, build_stage["jobCount"])
        self.assertEqual([], build_stage["jobs"])
        script_job = next(job for job in payload["jobs"] if job["jobId"] == "script-linux")
        self.assertFalse(script_job["hasBuildStage"])

        export_payload = get_build_plan_export_draft("SAMPAPI")
        assert export_payload is not None
        self.assertFalse(any(file["path"].endswith("run_build.py") for file in export_payload["files"]))


class SystemSettingServiceTest(TestCase):
    def test_get_system_setting_returns_default_when_missing(self) -> None:
        self.assertEqual("", get_system_setting("missing"))
        self.assertEqual("fallback", get_system_setting("missing", default="fallback"))

    def test_set_system_setting_upserts_value(self) -> None:
        set_system_setting(key="coverity.connect.url", value="https://coverity.example.com", description="Coverity URL")
        set_system_setting(key="coverity.connect.url", value="https://coverity.internal", description="Updated")

        self.assertEqual(1, SystemSetting.objects.count())
        setting = SystemSetting.objects.get(key="coverity.connect.url")
        self.assertEqual("https://coverity.internal", setting.value)
        self.assertEqual("Updated", setting.description)

    def test_get_coverity_system_settings_reads_known_keys(self) -> None:
        set_system_setting(key=SystemSetting.KEY_COVERITY_CONNECT_URL, value="https://coverity.example.com")
        set_system_setting(key=SystemSetting.KEY_COVERITY_ON_NEW_CERT, value="trust")
        set_system_setting(key=SystemSetting.KEY_COVERITY_COMMIT_ENABLED, value="true")
        set_system_setting(
            key=SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE,
            value="https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
        )

        payload = get_coverity_system_settings()

        self.assertEqual("https://coverity.example.com", payload["connectUrl"])
        self.assertEqual("trust", payload["onNewCert"])
        self.assertTrue(payload["commitEnabled"])
        self.assertEqual(
            "https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
            payload["gitCloneUrlTemplate"],
        )

    def test_build_git_clone_url_uses_template_placeholders(self) -> None:
        set_system_setting(
            key=SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE,
            value="https://git.example.com/scm/{project_key_lower}/{repo_slug}.git",
        )

        payload = build_git_clone_url(project_key="CCC", repo_slug="cccrepo")

        self.assertEqual("https://git.example.com/scm/ccc/cccrepo.git", payload)


class SpecsDraftInitializationServiceTest(TestCase):
    def test_initialize_specs_draft_data_creates_build_info_from_registered_metadata(self) -> None:
        project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        repository = ProjectRepository.objects.create(
            project=project,
            repo_slug="sample-app-api",
            is_representative=True,
        )
        plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")
        ProjectBuild.objects.create(
            project=project,
            repository=repository,
            build_plan=plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )

        summary = initialize_specs_draft_data(reset_existing=True)

        self.assertEqual(1, summary["initializedCount"])
        build_info = BuildPlanBuildInfo.objects.get(build_plan=plan)
        self.assertEqual("linux", build_info.operating_system)
        self.assertEqual("java", build_info.language)
        self.assertEqual("maven", build_info.compiler)
        self.assertEqual(".", build_info.build_sub_path)

    def test_initialize_specs_draft_for_plan_normalizes_existing_build_info_without_definition(self) -> None:
        project = Project.objects.create(
            jira_project_key="CCC",
            bitbucket_project_key="CCC",
            representative_repo_slug="ccc-build",
        )
        repository = ProjectRepository.objects.create(
            project=project,
            repo_slug="ccc-build",
            coverity_stream="ccc",
            is_representative=True,
        )
        plan = BuildPlan.objects.create(build_id="ccc-build", plan_key="CCCBUILD")
        ProjectBuild.objects.create(
            project=project,
            repository=repository,
            build_plan=plan,
            build_name="CCC Build",
            build_type="python",
            runtime_stack="python3.12",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=plan,
            build_key="main",
            operating_system="",
            language="",
            compiler="",
            coverity_stream="",
            build_sub_path="",
        )

        summary = initialize_specs_draft_for_plan(plan_key="CCCBUILD", reset_existing=False)

        self.assertEqual(1, summary["updatedCount"])
        build_info = BuildPlanBuildInfo.objects.get(build_plan=plan, build_key="main")
        self.assertEqual("linux", build_info.operating_system)
        self.assertEqual("python", build_info.language)
        self.assertEqual("python", build_info.compiler)
        self.assertEqual("ccc", build_info.coverity_stream)
        self.assertEqual(".", build_info.build_sub_path)

    def test_initialize_specs_draft_data_reset_existing_preserves_multiple_build_infos(self) -> None:
        project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        repository = ProjectRepository.objects.create(
            project=project,
            repo_slug="sample-app-api",
            coverity_stream="sample-app-dev",
            is_representative=True,
        )
        plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")
        ProjectBuild.objects.create(
            project=project,
            repository=repository,
            build_plan=plan,
            build_name="Sample API",
            build_type="maven",
            runtime_stack="java",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=plan,
            build_key="api-linux",
            operating_system="",
            pre_process="source env.sh",
            build_command="mvn -B verify",
            clean_command="mvn -B clean",
            analysis_excluded_files="generated/**",
            language="",
            compiler="",
            coverity_stream="",
            build_sub_path="",
        )
        BuildPlanBuildInfo.objects.create(
            build_plan=plan,
            build_key="api-windows",
            operating_system="windows",
            pre_process="setup.bat",
            build_command="mvn -B verify -Pwindows",
            clean_command="mvn -B clean",
            analysis_excluded_files="generated-win/**",
            language="java",
            compiler="maven",
            coverity_stream="",
            build_sub_path="services/api",
        )

        summary = initialize_specs_draft_data(reset_existing=True)

        self.assertEqual(0, summary["removedCount"])
        self.assertEqual(2, BuildPlanBuildInfo.objects.filter(build_plan=plan).count())
        self.assertEqual({"api-linux", "api-windows"}, set(plan.build_infos.values_list("build_key", flat=True)))
        for build_info in plan.build_infos.order_by("build_key"):
            self.assertEqual("sample-app-dev", build_info.coverity_stream)
            self.assertEqual("", build_info.pre_process)
            self.assertEqual("", build_info.build_command)
            self.assertEqual("", build_info.clean_command)
            self.assertEqual("", build_info.analysis_excluded_files)


class ValidatorExceptionTest(SimpleTestCase):
    def test_no_build_languages_are_identified(self) -> None:
        self.assertTrue(is_no_build_language(language="python", compiler="python"))
        self.assertFalse(is_no_build_language(language="javascript", compiler="node.js"))
        self.assertFalse(is_no_build_language(language="typescript", compiler="node.js"))
        self.assertFalse(is_no_build_language(language="java", compiler="maven"))

    def test_python_definition_allows_blank_prepare_and_build_command(self) -> None:
        build = parse_build_definition_payload(
            {
                "buildId": "sample-script",
                "name": "Sample Script",
                "planKey": "SCRIPTS",
                "language": "python",
                "compiler": "python",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-script",
                    "linkageMode": "linked",
                    "applicationLink": "BITBUCKET_SERVER",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "subPath": ".",
                    "prepareCommand": "",
                    "buildCommand": "",
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {"commands": ["python", "coverity"], "envVars": ["PYTHONPATH"]},
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            },
            year="2026",
        )

        validate_build_definitions([build])

    def test_java_definition_still_requires_build_command(self) -> None:
        build = parse_build_definition_payload(
            {
                "buildId": "sample-api",
                "name": "Sample API",
                "planKey": "SAMPAPI",
                "language": "java",
                "compiler": "maven",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-api",
                    "linkageMode": "linked",
                    "applicationLink": "BITBUCKET_SERVER",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "subPath": ".",
                    "prepareCommand": "mvn -B dependency:go-offline",
                    "buildCommand": "",
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            },
            year="2026",
        )

        with self.assertRaises(ValidationError):
            validate_build_definitions([build])


class ImportBuildDefinitionsCommandTest(TestCase):
    def test_import_build_definitions_creates_active_definition_graph(self) -> None:
        with TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "build_info_json"
            year_root = input_root / "2026"
            year_root.mkdir(parents=True, exist_ok=True)
            definition_path = year_root / "sample-app-api.json"
            definition_path.write_text(
                dedent(
                    """
                    {
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
                        "linkageMode": "create_if_missing",
                        "applicationLink": "BITBUCKET_DC",
                        "branches": ["dev", "release", "master"]
                      },
                      "requirements": {
                        "os": "linux",
                        "extraCapabilities": []
                      },
                      "build": {
                        "subPath": "services/sample-app-api",
                        "prepareCommand": "mvn -B dependency:go-offline",
                        "buildCommand": "mvn -B clean package",
                        "staticAnalysis": {
                          "customTool": {
                            "commands": ["custom-tool analyze {buildCommand}"]
                          }
                        },
                        "runtimeRequirements": {
                          "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                          "envVars": ["PATH", "JAVA_HOME"]
                        },
                        "postBuildTrigger": {
                          "type": "plan",
                          "targetPlanKey": "POSTBUILD"
                        }
                      }
                    }
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            call_command("import_build_definitions", input_root=str(input_root), verbosity=0)

        self.assertEqual(1, Project.objects.count())
        self.assertEqual(1, ProjectRepository.objects.count())
        self.assertEqual(1, BuildPlan.objects.count())
        self.assertEqual(1, ProjectBuild.objects.count())
        self.assertEqual(1, BuildPlanDefinition.objects.count())

        definition = BuildPlanDefinition.objects.get()
        self.assertTrue(definition.is_active)
        self.assertEqual("2026", definition.year)
        self.assertEqual("create_if_missing", definition.definition_json["repository"]["linkageMode"])
        self.assertEqual("BITBUCKET_DC", definition.definition_json["repository"]["applicationLink"])

        project = Project.objects.get()
        self.assertEqual("SAMPLE", project.jira_project_key)
        self.assertEqual("sample-app-api", project.representative_repo_slug)

    def test_reimport_build_definitions_creates_new_active_snapshot(self) -> None:
        with TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "build_info_json"
            year_root = input_root / "2026"
            year_root.mkdir(parents=True, exist_ok=True)
            definition_path = year_root / "sample-app-api.json"

            definition_path.write_text(
                json.dumps(
                    {
                        "buildId": "sample-app-api",
                        "name": "Sample App API",
                        "planKey": "SAMPAPI",
                        "description": "v1",
                        "language": "java",
                        "compiler": "maven",
                        "repository": {
                            "provider": "bitbucket",
                            "projectKey": "SAMPLE",
                            "repoSlug": "sample-app-api",
                            "linkageMode": "linked",
                            "branches": ["dev", "release", "master"],
                        },
                        "requirements": {"os": "linux", "extraCapabilities": []},
                        "build": {
                            "subPath": "services/sample-app-api",
                            "prepareCommand": "mvn -B dependency:go-offline",
                            "buildCommand": "mvn -B clean package",
                            "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                            "runtimeRequirements": {
                                "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                                "envVars": ["PATH", "JAVA_HOME"],
                            },
                            "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            call_command("import_build_definitions", input_root=str(input_root), verbosity=0)

            definition_path.write_text(
                json.dumps(
                    {
                        "buildId": "sample-app-api",
                        "name": "Sample App API",
                        "planKey": "SAMPAPI",
                        "description": "v2",
                        "language": "java",
                        "compiler": "maven",
                        "repository": {
                            "provider": "bitbucket",
                            "projectKey": "SAMPLE",
                            "repoSlug": "sample-app-api",
                            "linkageMode": "linked",
                            "branches": ["dev", "release", "master"],
                        },
                        "requirements": {"os": "linux", "extraCapabilities": []},
                        "build": {
                            "subPath": "services/sample-app-api",
                            "prepareCommand": "mvn -B -U dependency:go-offline",
                            "buildCommand": "mvn -B clean package",
                            "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                            "runtimeRequirements": {
                                "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                                "envVars": ["PATH", "JAVA_HOME"],
                            },
                            "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            call_command("import_build_definitions", input_root=str(input_root), verbosity=0)

        self.assertEqual(2, BuildPlanDefinition.objects.count())
        self.assertEqual(1, BuildPlanDefinition.objects.filter(is_active=True).count())
        self.assertEqual(2, BuildDefinitionHistory.objects.count())
        active_definition = BuildPlanDefinition.objects.get(is_active=True)
        self.assertEqual("mvn -B -U dependency:go-offline", active_definition.definition_json["build"]["prepareCommand"])

    def test_sync_definition_records_keeps_identical_active_snapshot_without_history_churn(self) -> None:
        with TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "build_info_json"
            year_root = input_root / "2026"
            year_root.mkdir(parents=True, exist_ok=True)
            definition_path = year_root / "sample-app-api.json"
            definition_path.write_text(
                json.dumps(
                    {
                        "buildId": "sample-app-api",
                        "name": "Sample App API",
                        "planKey": "SAMPAPI",
                        "description": "v1",
                        "language": "java",
                        "compiler": "maven",
                        "repository": {
                            "provider": "bitbucket",
                            "projectKey": "SAMPLE",
                            "repoSlug": "sample-app-api",
                            "linkageMode": "linked",
                            "branches": ["dev", "release", "master"],
                        },
                        "requirements": {"os": "linux", "extraCapabilities": []},
                        "build": {
                            "subPath": "services/sample-app-api",
                            "prepareCommand": "mvn -B dependency:go-offline",
                            "buildCommand": "mvn -B clean package",
                            "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                            "runtimeRequirements": {
                                "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                                "envVars": ["PATH", "JAVA_HOME"],
                            },
                            "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            summary1 = sync_definition_records(load_definition_import_records(input_root))
            summary2 = sync_definition_records(load_definition_import_records(input_root))

        self.assertEqual({"importedCount": 1, "activatedCount": 1, "unchangedCount": 0, "deactivatedCount": 0}, summary1)
        self.assertEqual({"importedCount": 1, "activatedCount": 0, "unchangedCount": 1, "deactivatedCount": 0}, summary2)
        self.assertEqual(1, BuildPlanDefinition.objects.count())
        self.assertEqual(1, BuildPlanDefinition.objects.filter(is_active=True).count())
        self.assertEqual(1, BuildDefinitionHistory.objects.filter(change_type="sync").count())

    def test_sync_build_definitions_command_deactivates_missing_plans(self) -> None:
        with TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir) / "build_info_json"
            year_root = input_root / "2026"
            year_root.mkdir(parents=True, exist_ok=True)

            api_definition = {
                "buildId": "sample-app-api",
                "name": "Sample App API",
                "planKey": "SAMPAPI",
                "description": "API",
                "language": "java",
                "compiler": "maven",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-app-api",
                    "linkageMode": "linked",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "subPath": "services/sample-app-api",
                    "prepareCommand": "mvn -B dependency:go-offline",
                    "buildCommand": "mvn -B clean package",
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {
                        "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                        "envVars": ["PATH", "JAVA_HOME"],
                    },
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            }
            web_definition = {
                "buildId": "sample-app-web",
                "name": "Sample App Web",
                "planKey": "SAMPWEB",
                "description": "WEB",
                "language": "node.js",
                "compiler": "node.js",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-app-web",
                    "linkageMode": "linked",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "subPath": "services/sample-app-web",
                    "prepareCommand": "npm ci",
                    "buildCommand": "npm run build",
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {
                        "commands": ["npm", "coverity", "custom-tool", "trigger-plan"],
                        "envVars": ["PATH", "NODE_HOME"],
                    },
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            }

            (year_root / "sample-app-api.json").write_text(
                json.dumps(api_definition, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (year_root / "sample-app-web.json").write_text(
                json.dumps(web_definition, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            call_command("sync_build_definitions", input_root=str(input_root), verbosity=0)
            (year_root / "sample-app-web.json").unlink()
            call_command("sync_build_definitions", input_root=str(input_root), verbosity=0, deactivate_missing=True)

        self.assertEqual(2, BuildPlan.objects.count())
        self.assertEqual(2, BuildPlanDefinition.objects.count())
        self.assertEqual(1, BuildPlanDefinition.objects.filter(is_active=True).count())
        self.assertTrue(BuildPlanDefinition.objects.get(build_plan__plan_key="SAMPAPI").is_active)
        self.assertFalse(BuildPlanDefinition.objects.get(build_plan__plan_key="SAMPWEB").is_active)
        self.assertEqual(1, BuildDefinitionHistory.objects.filter(change_type="deactivate").count())


class InitDevDbCommandTest(SimpleTestCase):
    @patch("apps.buildmeta.management.commands.init_dev_db.call_command")
    @patch("apps.buildmeta.management.commands.init_dev_db.connections")
    def test_init_dev_db_rejects_non_sqlite_engine(self, connections_mock, call_command_mock) -> None:
        connection_mock = Mock()
        connection_mock.settings_dict = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "bamboo_meta",
        }
        connections_mock.__getitem__.return_value = connection_mock

        with self.assertRaises(CommandError):
            call_command("init_dev_db", verbosity=0)

        call_command_mock.assert_not_called()

    @patch("apps.buildmeta.management.commands.init_dev_db.call_command")
    @patch("apps.buildmeta.management.commands.init_dev_db.connections")
    def test_init_dev_db_recreates_sqlite_database(self, connections_mock, call_command_mock) -> None:
        with TemporaryDirectory() as temp_dir:
            sqlite_path = Path(temp_dir) / "dev.sqlite3"
            sqlite_path.write_text("placeholder", encoding="utf-8")
            connection_mock = Mock()
            connection_mock.settings_dict = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(sqlite_path),
            }
            connections_mock.__getitem__.return_value = connection_mock

            call_command("init_dev_db", verbosity=0)

            self.assertFalse(sqlite_path.exists())
            connection_mock.close.assert_called_once()
            call_command_mock.assert_called_once_with("migrate", database="default", interactive=False, verbosity=0)


class InitPostgresDbCommandTest(SimpleTestCase):
    @patch("apps.buildmeta.management.commands.init_postgres_db.call_command")
    @patch("apps.buildmeta.management.commands.init_postgres_db.connections")
    def test_init_postgres_db_rejects_non_postgresql_engine(self, connections_mock, call_command_mock) -> None:
        connection_mock = Mock()
        connection_mock.settings_dict = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "db.sqlite3",
        }
        connections_mock.__getitem__.return_value = connection_mock

        with self.assertRaises(CommandError):
            call_command("init_postgres_db", verbosity=0, force=True)

        call_command_mock.assert_not_called()

    @patch("apps.buildmeta.management.commands.init_postgres_db.call_command")
    @patch("apps.buildmeta.management.commands.init_postgres_db.connections")
    def test_init_postgres_db_requires_force(self, connections_mock, call_command_mock) -> None:
        connection_mock = Mock()
        connection_mock.settings_dict = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "bamboo_meta",
        }
        connections_mock.__getitem__.return_value = connection_mock

        with self.assertRaises(CommandError):
            call_command("init_postgres_db", verbosity=0)

        call_command_mock.assert_not_called()

    @patch("apps.buildmeta.management.commands.init_postgres_db.call_command")
    @patch("apps.buildmeta.management.commands.init_postgres_db.connections")
    def test_init_postgres_db_recreates_schema_and_runs_migrate(self, connections_mock, call_command_mock) -> None:
        cursor_mock = Mock()
        cursor_context_mock = Mock()
        cursor_context_mock.__enter__ = Mock(return_value=cursor_mock)
        cursor_context_mock.__exit__ = Mock(return_value=None)

        connection_mock = Mock()
        connection_mock.settings_dict = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "bamboo_meta",
        }
        connection_mock.cursor.return_value = cursor_context_mock
        connections_mock.__getitem__.return_value = connection_mock

        call_command("init_postgres_db", verbosity=0, force=True)

        cursor_mock.execute.assert_any_call('DROP SCHEMA IF EXISTS "public" CASCADE')
        cursor_mock.execute.assert_any_call('CREATE SCHEMA "public"')
        connection_mock.close.assert_called_once()
        call_command_mock.assert_called_once_with("migrate", database="default", interactive=False, verbosity=0)


class ProjectServiceTest(TestCase):
    def test_create_project_marks_generation_not_ready_without_build_infos(self) -> None:
        payload = create_project(
            {
                "jiraProjectKey": "OPS",
                "bitbucketProjectKey": "OPS",
                "representativeRepoSlug": "ops-api",
                "repositories": [
                    {
                        "repoSlug": "ops-api",
                        "coverityProject": "ops-api",
                        "coverityStream": "ops-api-dev",
                        "isRepresentative": True,
                    }
                ],
                "builds": [
                    {
                        "buildName": "API",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "ops-api",
                        "planKey": "OPSAPI",
                        "repositorySlug": "ops-api",
                    }
                ],
            }
        )

        self.assertEqual("OPS", payload["jiraProjectKey"])
        self.assertFalse(payload["generation"]["generationReady"])
        self.assertEqual(["빌드 정보 없음 1"], payload["generation"]["generationReadinessIssues"])
        self.assertEqual(0, payload["generation"]["activeDefinitionCount"])
        self.assertEqual(1, Project.objects.count())
        self.assertEqual(1, BuildPlan.objects.count())
        self.assertEqual(1, ProjectBuild.objects.count())
        self.assertEqual("ops-api", ProjectBuild.objects.get().repository.repo_slug)

    def test_create_project_rejects_duplicate_representative_repositories(self) -> None:
        with self.assertRaisesMessage(ValueError, "Only one representative repository can be provided per request."):
            create_project(
                {
                    "jiraProjectKey": "OPS",
                    "bitbucketProjectKey": "OPS",
                    "repositories": [
                        {"repoSlug": "ops-api", "isRepresentative": True},
                        {"repoSlug": "ops-web", "isRepresentative": True},
                    ],
                    "builds": [],
                }
            )

    def test_update_project_keeps_existing_representative_repo_when_not_explicitly_changed(self) -> None:
        project = Project.objects.create(
            jira_project_key="OPS",
            bitbucket_project_key="OPS",
            representative_repo_slug="ops-api",
        )
        ProjectRepository.objects.create(
            project=project,
            repo_slug="ops-api",
            is_representative=True,
        )

        payload = update_project(
            "OPS",
            {
                "bitbucketProjectKey": "OPS-NEW",
                "representativeRepoSlug": "",
                "repositories": [
                    {
                        "repoSlug": "ops-api",
                        "coverityProject": "ops-api",
                        "coverityStream": "ops-api-release",
                        "isRepresentative": False,
                    }
                ],
                "builds": [],
            },
        )

        assert payload is not None
        self.assertEqual("OPS-NEW", payload["bitbucketProjectKey"])
        self.assertEqual("ops-api", payload["representativeRepoSlug"])

    def test_update_project_removes_omitted_repositories_and_builds(self) -> None:
        project = Project.objects.create(
            jira_project_key="OPS",
            bitbucket_project_key="OPS",
            representative_repo_slug="ops-api",
        )
        api_repository = ProjectRepository.objects.create(
            project=project,
            repo_slug="ops-api",
            is_representative=True,
        )
        web_repository = ProjectRepository.objects.create(
            project=project,
            repo_slug="ops-web",
            is_representative=False,
        )
        api_plan = BuildPlan.objects.create(build_id="ops-api", plan_key="OPSAPI")
        web_plan = BuildPlan.objects.create(build_id="ops-web", plan_key="OPSWEB")
        ProjectBuild.objects.create(
            project=project,
            repository=api_repository,
            build_plan=api_plan,
            build_name="API",
            build_type="python",
            runtime_stack="python3.12",
        )
        ProjectBuild.objects.create(
            project=project,
            repository=web_repository,
            build_plan=web_plan,
            build_name="Web",
            build_type="node",
            runtime_stack="node20",
        )

        payload = update_project(
            "OPS",
            {
                "bitbucketProjectKey": "OPS",
                "representativeRepoSlug": "ops-api",
                "repositories": [
                    {
                        "repoSlug": "ops-api",
                        "coverityProject": "ops-api",
                        "coverityStream": "ops-api-release",
                        "isRepresentative": True,
                    }
                ],
                "builds": [
                    {
                        "buildName": "API",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "ops-api",
                        "planKey": "OPSAPI",
                        "repositorySlug": "ops-api",
                    }
                ],
            },
        )

        assert payload is not None
        self.assertEqual(["ops-api"], [repository["repoSlug"] for repository in payload["repositories"]])
        self.assertEqual(["OPSAPI"], [build["planKey"] for build in payload["builds"]])
        self.assertEqual(1, ProjectRepository.objects.filter(project=project).count())
        self.assertEqual(1, ProjectBuild.objects.filter(project=project).count())
        self.assertFalse(ProjectRepository.objects.filter(project=project, repo_slug="ops-web").exists())
        self.assertFalse(ProjectBuild.objects.filter(project=project, build_plan__plan_key="OPSWEB").exists())

    def test_update_project_clears_representative_repo_when_removed_from_payload(self) -> None:
        project = Project.objects.create(
            jira_project_key="OPS",
            bitbucket_project_key="OPS",
            representative_repo_slug="ops-api",
        )
        ProjectRepository.objects.create(
            project=project,
            repo_slug="ops-api",
            is_representative=True,
        )
        ProjectRepository.objects.create(
            project=project,
            repo_slug="ops-worker",
            is_representative=False,
        )

        payload = update_project(
            "OPS",
            {
                "bitbucketProjectKey": "OPS",
                "representativeRepoSlug": "",
                "repositories": [
                    {
                        "repoSlug": "ops-worker",
                        "coverityProject": "",
                        "coverityStream": "",
                        "isRepresentative": False,
                    }
                ],
                "builds": [],
            },
        )

        assert payload is not None
        self.assertEqual("", payload["representativeRepoSlug"])

    def test_update_project_returns_none_for_missing_project(self) -> None:
        payload = update_project(
            "MISSING",
            {
                "bitbucketProjectKey": "MISS",
                "representativeRepoSlug": "",
                "repositories": [],
                "builds": [],
            },
        )

        self.assertIsNone(payload)

    def test_create_project_rejects_build_repository_not_in_repository_list(self) -> None:
        with self.assertRaisesMessage(ValueError, "Build repositorySlug 'ops-web' is not registered in repositories."):
            create_project(
                {
                    "jiraProjectKey": "OPS",
                    "bitbucketProjectKey": "OPS",
                    "representativeRepoSlug": "ops-api",
                    "repositories": [
                        {
                            "repoSlug": "ops-api",
                            "coverityProject": "",
                            "coverityStream": "",
                            "isRepresentative": True,
                        }
                    ],
                    "builds": [
                        {
                            "buildName": "API",
                            "buildType": "python",
                            "runtimeStack": "",
                            "buildId": "ops-api",
                            "planKey": "OPSAPI",
                            "repositorySlug": "ops-web",
                        }
                    ],
                }
            )

    def test_create_project_reuses_existing_unlinked_build_plan(self) -> None:
        BuildPlan.objects.create(build_id="ops-api", plan_key="OPSAPI")

        payload = create_project(
            {
                "jiraProjectKey": "OPS",
                "bitbucketProjectKey": "OPS",
                "representativeRepoSlug": "ops-api",
                "repositories": [
                    {
                        "repoSlug": "ops-api",
                        "coverityProject": "",
                        "coverityStream": "",
                        "isRepresentative": True,
                    }
                ],
                "builds": [
                    {
                        "buildName": "API",
                        "buildType": "python",
                        "runtimeStack": "python3.12",
                        "buildId": "ops-api",
                        "planKey": "OPSAPI",
                        "repositorySlug": "ops-api",
                    }
                ],
            }
        )

        self.assertEqual("OPS", payload["jiraProjectKey"])
        self.assertEqual(1, BuildPlan.objects.count())
        self.assertEqual(1, ProjectBuild.objects.count())

    def test_create_project_rejects_existing_build_id_with_different_plan_key(self) -> None:
        BuildPlan.objects.create(build_id="ops-api", plan_key="OPSAPI")

        with self.assertRaisesMessage(ValueError, "Build buildId 'ops-api' already exists with a different planKey."):
            create_project(
                {
                    "jiraProjectKey": "OPS",
                    "bitbucketProjectKey": "OPS",
                    "representativeRepoSlug": "ops-api",
                    "repositories": [
                        {
                            "repoSlug": "ops-api",
                            "coverityProject": "",
                            "coverityStream": "",
                            "isRepresentative": True,
                        }
                    ],
                    "builds": [
                        {
                            "buildName": "API",
                            "buildType": "python",
                            "runtimeStack": "python3.12",
                            "buildId": "ops-api",
                            "planKey": "DIFFKEY",
                            "repositorySlug": "ops-api",
                        }
                    ],
                }
            )
