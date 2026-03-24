from __future__ import annotations

import unittest

from src.bamboo_spec_generator.coverity import coverity_language, generate_coverity_yaml
from src.bamboo_spec_generator.parser import parse_build_definition_payload


class CoveritySupportTest(unittest.TestCase):
    def test_coverity_language_maps_known_languages_and_normalizes_unknown_values(self) -> None:
        self.assertEqual("javascript", coverity_language("node.js"))
        self.assertEqual("javascript", coverity_language("NodeJS"))
        self.assertEqual("python", coverity_language("python"))
        self.assertEqual("custom", coverity_language("Custom"))

    def test_generate_coverity_yaml_escapes_commands_and_replaces_placeholders(self) -> None:
        build = parse_build_definition_payload(
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
                    "linkageMode": "linked",
                    "branches": ["dev", "release", "master"],
                },
                "requirements": {"os": "linux", "extraCapabilities": []},
                "build": {
                    "subPath": ".",
                    "prepareCommand": "mvn -B dependency:go-offline",
                    "buildCommand": 'mvn -B clean package "quoted"',
                    "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                    "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                    "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                },
            },
            year="2026",
        )

        rendered = generate_coverity_yaml(
            build,
            clean_command="mvn -B clean \\ path",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            exclude_files_regex="generated/**",
            connect_url="https://coverity.example.com",
            on_new_cert="trust",
            commit_enabled=True,
        )

        self.assertNotIn("<fill-build-command>", rendered)
        self.assertIn('build-command: "mvn -B clean package \\"quoted\\""', rendered)
        self.assertIn('clean-command: "mvn -B clean \\\\ path"', rendered)
        self.assertIn('project: "sample-app-api"', rendered)
        self.assertIn('stream: "sample-app-api-dev"', rendered)
        self.assertIn("enabled: true", rendered)
