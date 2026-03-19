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
                        "applicationLink": "BITBUCKET_SERVER",
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
        self.assertEqual("BITBUCKET_SERVER", build.repository.application_link)

    @patch("src.bamboo_spec_generator.api_client.request.urlopen")
    def test_get_prepare_context_uses_prepare_context_endpoint(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            {
                "planKey": "SAMPAPI",
                "variables": {
                    "BITBUCKET_APPLICATION_LINK": "BITBUCKET_SERVER",
                    "currentRepository.linkageMode": "linked",
                },
            }
        )
        client = OperationsApiClient(
            OperationsApiConfig(base_url="http://localhost:8000", token="token", timeout_seconds=3.0)
        )

        payload = client.get_prepare_context("SAMPAPI")

        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual("http://localhost:8000/api/v1/build-plans/SAMPAPI/prepare-context", request_obj.full_url)
        self.assertEqual("Bearer token", request_obj.headers["Authorization"])
        self.assertEqual("BITBUCKET_SERVER", payload["variables"]["BITBUCKET_APPLICATION_LINK"])

    @patch("src.bamboo_spec_generator.api_client.request.urlopen")
    def test_start_execution_posts_payload(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            {
                "buildVersionId": "version-1",
                "buildExecutionId": "execution-1",
                "version": "v0.0.1",
                "reusedExistingVersion": False,
            }
        )
        client = OperationsApiClient(
            OperationsApiConfig(base_url="http://localhost:8000", token="token", timeout_seconds=3.0)
        )

        payload = client.start_execution(
            "SAMPAPI",
            branch_kind="dev",
            commit_hash="abcdef123456",
            build_number="101",
            started_at="2026-03-19T00:00:00Z",
        )

        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual("http://localhost:8000/api/v1/build-plans/SAMPAPI/executions/start", request_obj.full_url)
        self.assertEqual("POST", request_obj.get_method())
        self.assertEqual(
            {
                "branchKind": "dev",
                "commitHash": "abcdef123456",
                "buildNumber": "101",
                "startedAt": "2026-03-19T00:00:00Z",
            },
            json.loads(request_obj.data.decode("utf-8")),
        )
        self.assertEqual("execution-1", payload["buildExecutionId"])

    @patch("src.bamboo_spec_generator.api_client.request.urlopen")
    def test_finish_execution_posts_static_analysis_results(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            {
                "buildExecutionId": "execution-1",
                "buildVersionId": "version-1",
                "resultStatus": "failed",
                "success": False,
            }
        )
        client = OperationsApiClient(
            OperationsApiConfig(base_url="http://localhost:8000", token="token", timeout_seconds=3.0)
        )

        payload = client.finish_execution(
            "execution-1",
            success=False,
            result_status="failed",
            summary_message="Unit test stage failed",
            stage_name="Build",
            job_name="Backend Test",
            task_name="pytest",
            finished_at="2026-03-19T00:12:00Z",
            static_analysis_results=[
                {
                    "toolName": "coverity",
                    "status": "passed",
                    "summary": "0 high impact defects",
                }
            ],
        )

        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual("http://localhost:8000/api/v1/build-executions/execution-1/finish", request_obj.full_url)
        self.assertEqual("POST", request_obj.get_method())
        self.assertEqual(
            {
                "success": False,
                "resultStatus": "failed",
                "summaryMessage": "Unit test stage failed",
                "stageName": "Build",
                "jobName": "Backend Test",
                "taskName": "pytest",
                "finishedAt": "2026-03-19T00:12:00Z",
                "staticAnalysisResults": [
                    {
                        "toolName": "coverity",
                        "status": "passed",
                        "summary": "0 high impact defects",
                    }
                ],
            },
            json.loads(request_obj.data.decode("utf-8")),
        )
        self.assertFalse(payload["success"])

    @patch("src.bamboo_spec_generator.api_client.request.urlopen")
    def test_list_executions_uses_execution_list_endpoint(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            [
                {
                    "buildExecutionId": "execution-1",
                    "buildVersionId": "version-1",
                    "version": "v0.0.1",
                    "buildNumber": "101",
                    "commitHash": "abcdef123456",
                    "success": True,
                    "resultStatus": "successful",
                    "summaryMessage": "",
                    "stageName": "",
                    "jobName": "",
                    "taskName": "",
                    "startedAt": "2026-03-19T00:00:00Z",
                    "finishedAt": "2026-03-19T00:10:00Z",
                    "createdAt": "2026-03-19T00:00:00Z",
                    "staticAnalysisResults": [],
                }
            ]
        )
        client = OperationsApiClient(
            OperationsApiConfig(base_url="http://localhost:8000", token="token", timeout_seconds=3.0)
        )

        payload = client.list_executions("SAMPAPI")

        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual("http://localhost:8000/api/v1/build-plans/SAMPAPI/executions", request_obj.full_url)
        self.assertEqual("GET", request_obj.get_method())
        self.assertEqual("execution-1", payload[0]["buildExecutionId"])
