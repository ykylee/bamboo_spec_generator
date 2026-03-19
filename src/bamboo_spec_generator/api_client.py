from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib import error, parse, request

from .model import BuildDefinition
from .parser import parse_build_definition_payload


class OperationsApiError(RuntimeError):
    """Raised when the operations backend API call fails."""


@dataclass(frozen=True)
class OperationsApiConfig:
    base_url: str
    token: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "OperationsApiConfig":
        return cls(
            base_url=os.environ.get("BAMBOO_API_BASE_URL", "").rstrip("/"),
            token=os.environ.get("BAMBOO_API_TOKEN", ""),
            timeout_seconds=float(os.environ.get("BAMBOO_API_TIMEOUT_SECONDS", "10")),
        )


class OperationsApiClient:
    def __init__(self, config: OperationsApiConfig) -> None:
        if not config.base_url:
            raise OperationsApiError("BAMBOO_API_BASE_URL is not configured.")
        if not config.token:
            raise OperationsApiError("BAMBOO_API_TOKEN is not configured.")
        self._config = config

    def get_active_definition(self, plan_key: str) -> dict:
        return self._request_json("GET", f"/api/v1/build-plans/{parse.quote(plan_key)}/active-definition")

    def get_prepare_context(self, plan_key: str) -> dict:
        return self._request_json("GET", f"/api/v1/build-plans/{parse.quote(plan_key)}/prepare-context")

    def list_executions(self, plan_key: str) -> list[dict]:
        payload = self._request_json("GET", f"/api/v1/build-plans/{parse.quote(plan_key)}/executions")
        if not isinstance(payload, list):
            raise OperationsApiError("Execution list response must be a JSON array.")
        return payload

    def start_execution(
        self,
        plan_key: str,
        *,
        branch_kind: str,
        commit_hash: str,
        build_number: str,
        started_at: str | None = None,
    ) -> dict:
        payload = {
            "branchKind": branch_kind,
            "commitHash": commit_hash,
            "buildNumber": build_number,
        }
        if started_at is not None:
            payload["startedAt"] = started_at
        return self._request_json("POST", f"/api/v1/build-plans/{parse.quote(plan_key)}/executions/start", body=payload)

    def finish_execution(
        self,
        execution_id: str,
        *,
        success: bool,
        result_status: str,
        summary_message: str = "",
        stage_name: str = "",
        job_name: str = "",
        task_name: str = "",
        finished_at: str | None = None,
        static_analysis_results: list[dict] | None = None,
    ) -> dict:
        payload = {
            "success": success,
            "resultStatus": result_status,
            "summaryMessage": summary_message,
            "stageName": stage_name,
            "jobName": job_name,
            "taskName": task_name,
            "staticAnalysisResults": static_analysis_results or [],
        }
        if finished_at is not None:
            payload["finishedAt"] = finished_at
        return self._request_json("POST", f"/api/v1/build-executions/{parse.quote(execution_id)}/finish", body=payload)

    def get_build_definition(self, plan_key: str) -> BuildDefinition:
        payload = self.get_active_definition(plan_key)
        return parse_build_definition_payload(payload["definition"], year=str(payload["year"]))

    def _request_json(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._config.token}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = request.Request(f"{self._config.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self._config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise OperationsApiError(f"API request failed with {exc.code}: {payload}") from exc
        except error.URLError as exc:
            raise OperationsApiError(f"API request failed: {exc.reason}") from exc
