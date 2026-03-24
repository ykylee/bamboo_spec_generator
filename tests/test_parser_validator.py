from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.bamboo_spec_generator.parser import discover_input_files, parse_build_definition_payload
from src.bamboo_spec_generator.validator import ValidationError, validate_build_definitions


class ParserValidatorTest(unittest.TestCase):
    def test_discover_input_files_returns_sorted_json_files_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir)
            (input_root / "2026").mkdir()
            (input_root / "2024").mkdir()
            (input_root / "2026" / "b-build.json").write_text("{}", encoding="utf-8")
            (input_root / "2024" / "a-build.json").write_text("{}", encoding="utf-8")
            (input_root / "2024" / "skip.txt").write_text("ignored", encoding="utf-8")

            discovered = discover_input_files(input_root)

        self.assertEqual(
            [input_root / "2024" / "a-build.json", input_root / "2026" / "b-build.json"],
            discovered,
        )

    def test_parse_build_definition_payload_applies_default_branches_and_sub_path(self) -> None:
        build = parse_build_definition_payload(
            {
                "buildId": "sample-app-api",
                "name": "Sample App API",
                "planKey": "SAMPAPI",
                "language": "java",
                "compiler": "maven",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-app-api",
                    "linkageMode": "linked",
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "prepareCommand": "mvn -B dependency:go-offline",
                    "buildCommand": "mvn -B clean package",
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            },
            year="2026",
        )

        self.assertEqual(["dev", "release", "master"], build.repository.branches)
        self.assertEqual(".", build.build.sub_path)

    def test_validate_build_definitions_rejects_create_if_missing_without_link_target(self) -> None:
        build = parse_build_definition_payload(
            {
                "buildId": "sample-app-api",
                "name": "Sample App API",
                "planKey": "SAMPAPI",
                "language": "java",
                "compiler": "maven",
                "repository": {
                    "provider": "bitbucket",
                    "projectKey": "SAMPLE",
                    "repoSlug": "sample-app-api",
                    "linkageMode": "create_if_missing",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "subPath": ".",
                    "prepareCommand": "mvn -B dependency:go-offline",
                    "buildCommand": "mvn -B clean package",
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            },
            year="2026",
        )

        with self.assertRaises(ValidationError):
            validate_build_definitions([build])

    def test_validate_build_definitions_rejects_invalid_sub_path(self) -> None:
        for sub_path in ("/tmp/build", "../escape"):
            with self.subTest(sub_path=sub_path):
                build = parse_build_definition_payload(
                    {
                        "buildId": "sample-app-api",
                        "name": "Sample App API",
                        "planKey": "SAMPAPI",
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
                            "subPath": sub_path,
                            "prepareCommand": "mvn -B dependency:go-offline",
                            "buildCommand": "mvn -B clean package",
                            "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                            "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                            "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                        },
                    },
                    year="2026",
                )

                with self.assertRaises(ValidationError):
                    validate_build_definitions([build])

    def test_validate_build_definitions_rejects_invalid_core_fields(self) -> None:
        cases = [
            (
                "unsupported_compiler",
                {
                    "buildId": "sample-app-api",
                    "name": "Sample App API",
                    "planKey": "SAMPAPI",
                    "language": "java",
                    "compiler": "unknown",
                    "repository": {
                        "provider": "bitbucket",
                        "projectKey": "SAMPLE",
                        "repoSlug": "sample-app-api",
                        "linkageMode": "linked",
                        "branches": ["dev", "release", "master"],
                    },
                    "requirements": {"os": "linux", "extraCapabilities": []},
                    "build": {
                        "subPath": ".",
                        "prepareCommand": "mvn -B dependency:go-offline",
                        "buildCommand": "mvn -B clean package",
                        "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                        "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                        "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                    },
                },
            ),
            (
                "unsupported_os",
                {
                    "buildId": "sample-app-api",
                    "name": "Sample App API",
                    "planKey": "SAMPAPI",
                    "language": "java",
                    "compiler": "maven",
                    "repository": {
                        "provider": "bitbucket",
                        "projectKey": "SAMPLE",
                        "repoSlug": "sample-app-api",
                        "linkageMode": "linked",
                        "branches": ["dev", "release", "master"],
                    },
                    "requirements": {"os": "macos", "extraCapabilities": []},
                    "build": {
                        "subPath": ".",
                        "prepareCommand": "mvn -B dependency:go-offline",
                        "buildCommand": "mvn -B clean package",
                        "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                        "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                        "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                    },
                },
            ),
            (
                "missing_runtime_env_vars",
                {
                    "buildId": "sample-app-api",
                    "name": "Sample App API",
                    "planKey": "SAMPAPI",
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
                        "subPath": ".",
                        "prepareCommand": "mvn -B dependency:go-offline",
                        "buildCommand": "mvn -B clean package",
                        "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                        "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": []},
                        "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                    },
                },
            ),
        ]

        for case_name, raw in cases:
            with self.subTest(case_name=case_name):
                build = parse_build_definition_payload(raw, year="2026")

                with self.assertRaises(ValidationError):
                    validate_build_definitions([build])
