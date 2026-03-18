from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.bamboo_spec_generator.api_client import OperationsApiClient, OperationsApiConfig, OperationsApiError


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class OperationsApiClientTest(unittest.TestCase):
    def test_config_reads_environment(self) -> None:
        env = {
            "BAMBOO_API_BASE_URL": "http://localhost:8000",
            "BAMBOO_API_TOKEN": "token",
            "BAMBOO_API_TIMEOUT_SECONDS": "5",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OperationsApiConfig.from_env()

        self.assertEqual("http://localhost:8000", config.base_url)
        self.assertEqual("token", config.token)
        self.assertEqual(5.0, config.timeout_seconds)

    def test_client_requires_base_url_and_token(self) -> None:
        with self.assertRaises(OperationsApiError):
            OperationsApiClient(OperationsApiConfig(base_url="", token="token"))
        with self.assertRaises(OperationsApiError):
            OperationsApiClient(OperationsApiConfig(base_url="http://localhost:8000", token=""))

    @patch("src.bamboo_spec_generator.api_client.request.urlopen")
    def test_get_build_definition_uses_active_definition_endpoint(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            {
                "planKey": "SAMPAPI",
                "buildId": "sample-app-api",
                "year": "2026",
                "definitionVersion": "sha256:abc123",
                "definition": {
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
                    "requirements": {
                        "os": "linux",
                        "extraCapabilities": [],
                    },
                    "build": {
                        "subPath": "services/sample-app-api",
                        "prepareCommand": "mvn -B dependency:go-offline",
                        "buildCommand": "mvn -B clean package",
                        "staticAnalysis": {
                            "customTool": {
                                "commands": ["custom-tool analyze {buildCommand}"],
                            }
                        },
                        "runtimeRequirements": {
                            "commands": ["mvn", "coverity", "custom-tool", "trigger-plan"],
                            "envVars": ["PATH", "JAVA_HOME"],
                        },
                        "postBuildTrigger": {
                            "type": "plan",
                            "targetPlanKey": "POSTBUILD",
                        },
                    },
                },
            }
        )
        client = OperationsApiClient(
            OperationsApiConfig(base_url="http://localhost:8000", token="token", timeout_seconds=3.0)
        )

        build = client.get_build_definition("SAMPAPI")

        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual("http://localhost:8000/api/v1/build-plans/SAMPAPI/active-definition", request_obj.full_url)
        self.assertEqual("Bearer token", request_obj.headers["Authorization"])
        self.assertEqual("sample-app-api", build.build_id)
        self.assertEqual("2026", build.year)
        self.assertEqual("services/sample-app-api", build.build.sub_path)
