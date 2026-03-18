from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

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
