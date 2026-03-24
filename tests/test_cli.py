from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from src.bamboo_spec_generator.api_client import OperationsApiError
from src.bamboo_spec_generator.cli import main
from src.bamboo_spec_generator.validator import ValidationError


class CliMainTest(unittest.TestCase):
    def _run_main(self, args: Namespace) -> int:
        parser = MagicMock()
        parser.parse_args.return_value = args
        with patch("src.bamboo_spec_generator.cli.build_argument_parser", return_value=parser):
            return main()

    def test_main_db_check_uses_postgres_connection_check(self) -> None:
        args = Namespace(
            input_root="build_info_json",
            output_root="bamboo-specs",
            db_check=True,
            db_init_schema=False,
            api_plan_key=None,
        )
        config = MagicMock()
        config.masked_dsn.return_value = "host=localhost port=5432"

        with patch("src.bamboo_spec_generator.cli.PostgresConfig.from_env", return_value=config) as from_env_mock, patch(
            "src.bamboo_spec_generator.cli.check_connection",
            return_value="postgres|postgres|PostgreSQL 16",
        ) as check_connection_mock, patch("src.bamboo_spec_generator.cli.apply_schema") as apply_schema_mock:
            result = self._run_main(args)

        self.assertEqual(0, result)
        from_env_mock.assert_called_once()
        config.masked_dsn.assert_called_once()
        check_connection_mock.assert_called_once_with(config)
        apply_schema_mock.assert_not_called()

    def test_main_db_init_schema_uses_postgres_schema_apply(self) -> None:
        args = Namespace(
            input_root="build_info_json",
            output_root="bamboo-specs",
            db_check=False,
            db_init_schema=True,
            api_plan_key=None,
        )
        config = MagicMock()
        config.masked_dsn.return_value = "host=localhost port=5432"

        with patch("src.bamboo_spec_generator.cli.PostgresConfig.from_env", return_value=config) as from_env_mock, patch(
            "src.bamboo_spec_generator.cli.apply_schema",
            return_value="CREATE TABLE",
        ) as apply_schema_mock, patch("src.bamboo_spec_generator.cli.check_connection") as check_connection_mock:
            result = self._run_main(args)

        self.assertEqual(0, result)
        from_env_mock.assert_called_once()
        config.masked_dsn.assert_called_once()
        apply_schema_mock.assert_called_once_with(config)
        check_connection_mock.assert_not_called()

    def test_main_api_plan_key_success_generates_specs_project(self) -> None:
        args = Namespace(
            input_root="build_info_json",
            output_root="generated-specs",
            db_check=False,
            db_init_schema=False,
            api_plan_key="SAMPAPI",
        )
        build_definition = MagicMock(name="build_definition")
        prepare_context = {"variables": {"example": "value"}}

        with patch("src.bamboo_spec_generator.cli.OperationsApiConfig.from_env", return_value=MagicMock()) as config_mock, patch(
            "src.bamboo_spec_generator.cli.OperationsApiClient",
        ) as client_cls, patch("src.bamboo_spec_generator.cli.validate_build_definitions") as validate_mock, patch(
            "src.bamboo_spec_generator.cli.write_specs_project",
            return_value=[Path("generated-specs/pom.xml"), Path("generated-specs/README.md")],
        ) as write_mock:
            client = client_cls.return_value
            client.get_build_definition.return_value = build_definition
            client.get_prepare_context.return_value = prepare_context

            result = self._run_main(args)

        self.assertEqual(0, result)
        config_mock.assert_called_once()
        client_cls.assert_called_once()
        client.get_build_definition.assert_called_once_with("SAMPAPI")
        client.get_prepare_context.assert_called_once_with("SAMPAPI")
        validate_mock.assert_called_once_with([build_definition])
        write_mock.assert_called_once_with(
            Path("generated-specs"),
            [build_definition],
            prepare_contexts={"SAMPAPI": prepare_context},
        )

    def test_main_api_plan_key_failure_returns_one(self) -> None:
        args = Namespace(
            input_root="build_info_json",
            output_root="generated-specs",
            db_check=False,
            db_init_schema=False,
            api_plan_key="SAMPAPI",
        )

        with patch("src.bamboo_spec_generator.cli.OperationsApiConfig.from_env", return_value=MagicMock()), patch(
            "src.bamboo_spec_generator.cli.OperationsApiClient",
        ) as client_cls, patch("src.bamboo_spec_generator.cli.validate_build_definitions") as validate_mock, patch(
            "src.bamboo_spec_generator.cli.write_specs_project"
        ) as write_mock:
            client = client_cls.return_value
            client.get_build_definition.side_effect = OperationsApiError("backend unavailable")

            result = self._run_main(args)

        self.assertEqual(1, result)
        client.get_build_definition.assert_called_once_with("SAMPAPI")
        client.get_prepare_context.assert_not_called()
        validate_mock.assert_not_called()
        write_mock.assert_not_called()

    def test_main_returns_one_when_input_files_are_missing(self) -> None:
        args = Namespace(
            input_root="empty-input",
            output_root="generated-specs",
            db_check=False,
            db_init_schema=False,
            api_plan_key=None,
        )

        with patch("src.bamboo_spec_generator.cli.discover_input_files", return_value=[]) as discover_mock, patch(
            "src.bamboo_spec_generator.cli.parse_build_definition"
        ) as parse_mock, patch("src.bamboo_spec_generator.cli.validate_build_definitions") as validate_mock, patch(
            "src.bamboo_spec_generator.cli.write_specs_project"
        ) as write_mock:
            result = self._run_main(args)

        self.assertEqual(1, result)
        discover_mock.assert_called_once_with(Path("empty-input"))
        parse_mock.assert_not_called()
        validate_mock.assert_not_called()
        write_mock.assert_not_called()

    def test_main_returns_one_when_validation_fails(self) -> None:
        args = Namespace(
            input_root="build_info_json",
            output_root="generated-specs",
            db_check=False,
            db_init_schema=False,
            api_plan_key=None,
        )
        build = MagicMock(name="build")

        with patch("src.bamboo_spec_generator.cli.discover_input_files", return_value=[Path("build_info_json/2026/sample.json")]) as discover_mock, patch(
            "src.bamboo_spec_generator.cli.parse_build_definition",
            return_value=build,
        ) as parse_mock, patch(
            "src.bamboo_spec_generator.cli.validate_build_definitions",
            side_effect=ValidationError("invalid build"),
        ) as validate_mock, patch("src.bamboo_spec_generator.cli.write_specs_project") as write_mock:
            result = self._run_main(args)

        self.assertEqual(1, result)
        discover_mock.assert_called_once_with(Path("build_info_json"))
        parse_mock.assert_called_once_with(Path("build_info_json/2026/sample.json"))
        validate_mock.assert_called_once_with([build])
        write_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
