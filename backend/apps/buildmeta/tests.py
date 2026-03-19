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
    BuildPlanDefinition,
    StaticAnalysisResult,
    BuildVersion,
    Project,
    ProjectBuild,
    ProjectRepository,
)
from apps.buildmeta.selectors.definitions import get_active_definition_by_plan_key
from apps.buildmeta.services import create_project, load_definition_import_records, sync_definition_records, update_project
from apps.buildmeta.services.executions import finish_execution, record_static_analysis_results, start_execution


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


class DefinitionSelectorTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            representative_repo_slug="sample-app-api",
        )
        self.plan = BuildPlan.objects.create(build_id="sample-app-api", plan_key="SAMPAPI")

    def test_active_definition_uses_explicit_year_from_active_record(self) -> None:
        BuildPlanDefinition.objects.create(
            build_plan=self.plan,
            project=self.project,
            year="2026",
            source_kind=BuildPlanDefinition.SOURCE_KIND_JSON,
            definition_hash="sha256:abc123",
            is_active=True,
            definition_json={"buildId": "sample-app-api", "planKey": "SAMPAPI"},
        )

        payload = get_active_definition_by_plan_key("SAMPAPI")

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("2026", payload["year"])


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
    def test_create_project_marks_generation_not_ready_without_active_definitions(self) -> None:
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
        self.assertEqual(["활성 정의 없음 1"], payload["generation"]["generationReadinessIssues"])
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
