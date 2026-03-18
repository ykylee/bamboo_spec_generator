from __future__ import annotations

from pathlib import Path
import os
import subprocess
import unittest
from unittest.mock import patch

from src.bamboo_spec_generator.postgres import (
    PostgresConfig,
    PostgresError,
    apply_schema,
    build_psql_command,
    check_connection,
    load_schema_sql,
    schema_sql_path,
)


class PostgresSupportTest(unittest.TestCase):
    def test_postgres_config_uses_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = PostgresConfig.from_env()

        self.assertEqual("127.0.0.1", config.host)
        self.assertEqual(5432, config.port)
        self.assertEqual("postgres", config.user)
        self.assertEqual("", config.password)
        self.assertEqual("postgres", config.database)
        self.assertEqual("prefer", config.sslmode)

    def test_postgres_config_reads_environment(self) -> None:
        env = {
            "BAMBOO_DB_HOST": "db.local",
            "BAMBOO_DB_PORT": "5544",
            "BAMBOO_DB_USER": "builder",
            "BAMBOO_DB_PASSWORD": "secret",
            "BAMBOO_DB_NAME": "bamboo_meta",
            "BAMBOO_DB_SSLMODE": "disable",
        }
        with patch.dict(os.environ, env, clear=True):
            config = PostgresConfig.from_env()

        self.assertEqual("db.local", config.host)
        self.assertEqual(5544, config.port)
        self.assertEqual("builder", config.user)
        self.assertEqual("secret", config.password)
        self.assertEqual("bamboo_meta", config.database)
        self.assertEqual("disable", config.sslmode)

    def test_build_psql_command_for_inline_sql(self) -> None:
        config = PostgresConfig(
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="",
            database="postgres",
            sslmode="disable",
        )

        command = build_psql_command(config, sql="select 1;")

        self.assertEqual("psql", command[0])
        self.assertIn("--host", command)
        self.assertIn("--command", command)
        self.assertIn("select 1;", command)

    def test_schema_sql_path_and_content_exist(self) -> None:
        path = schema_sql_path()

        self.assertTrue(path.exists())
        self.assertTrue(path.samefile(Path("docs/designs/sql/build_metadata_schema.sql")))
        self.assertIn("create table project", load_schema_sql())
        self.assertIn("create table build_execution", load_schema_sql())

    @patch("src.bamboo_spec_generator.postgres.run_psql")
    def test_check_connection_returns_stdout(self, run_psql_mock) -> None:
        run_psql_mock.return_value = subprocess.CompletedProcess(
            args=["psql"],
            returncode=0,
            stdout="postgres|postgres|PostgreSQL 16",
            stderr="",
        )

        output = check_connection(PostgresConfig.from_env())

        self.assertEqual("postgres|postgres|PostgreSQL 16", output)
        run_psql_mock.assert_called_once()

    @patch("src.bamboo_spec_generator.postgres.run_psql")
    def test_apply_schema_uses_schema_file(self, run_psql_mock) -> None:
        run_psql_mock.return_value = subprocess.CompletedProcess(
            args=["psql"],
            returncode=0,
            stdout="CREATE TABLE",
            stderr="",
        )

        output = apply_schema(PostgresConfig.from_env())

        self.assertEqual("CREATE TABLE", output)
        _, kwargs = run_psql_mock.call_args
        self.assertEqual(schema_sql_path(), kwargs["sql_file"])

    @patch("src.bamboo_spec_generator.postgres.subprocess.run")
    def test_run_psql_wraps_called_process_error(self, subprocess_run_mock) -> None:
        from src.bamboo_spec_generator.postgres import run_psql

        subprocess_run_mock.side_effect = subprocess.CalledProcessError(
            2,
            ["psql"],
            stderr="connection failed",
        )

        with self.assertRaises(PostgresError) as context:
            run_psql(PostgresConfig.from_env(), sql="select 1;")

        self.assertIn("connection failed", str(context.exception))
