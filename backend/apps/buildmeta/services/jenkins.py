from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib import error, parse, request

from django.utils import timezone
from apps.buildmeta.models import JenkinsBuildUnit, JenkinsNodeSnapshot, JenkinsQueueItemSnapshot, BuildUnit

from .system_settings import DEFAULT_JENKINS_TOKEN_PATH, get_jenkins_system_settings


class JenkinsOperationError(RuntimeError):
    def __init__(self, summary: str, detail: str = "") -> None:
        super().__init__(summary)
        self.summary = summary
        self.detail = detail


@dataclass(frozen=True)
class JenkinsClientConfig:
    server_url: str
    username: str
    token: str
    token_file_path: str | None = None
    timeout_seconds: float = 30.0


def get_jenkins_client_config() -> JenkinsClientConfig:
    settings_payload = get_jenkins_system_settings()
    server_url = str(settings_payload["serverUrl"]).rstrip("/")
    env_token = os.environ.get("JENKINS_TOKEN", "").strip()
    env_username = os.environ.get("JENKINS_USERNAME", "").strip()
    file_token = ""
    if not env_token and DEFAULT_JENKINS_TOKEN_PATH.is_file():
        file_token = DEFAULT_JENKINS_TOKEN_PATH.read_text(encoding="utf-8").strip()
    username = env_username or "admin"
    token = env_token or file_token
    if not server_url:
        raise JenkinsOperationError("Jenkins 서버 URL이 설정되지 않았습니다.")
    if not token:
        raise JenkinsOperationError(
            "Jenkins 토큰이 설정되지 않았습니다.",
            f"환경 변수 `JENKINS_TOKEN` 또는 `{DEFAULT_JENKINS_TOKEN_PATH}` 파일이 필요합니다.",
        )
    return JenkinsClientConfig(
        server_url=server_url,
        username=username,
        token=token,
        token_file_path=str(DEFAULT_JENKINS_TOKEN_PATH) if file_token else None,
    )


def get_jenkins_job_status(job_path: str) -> dict:
    jenkins_unit = _get_jenkins_build_unit(job_path)
    if jenkins_unit is None:
        return {"configured": False, "exists": False, "error": "Jenkins job not found."}

    identity = _build_job_identity(jenkins_unit)
    settings_payload = get_jenkins_system_settings()
    if not settings_payload["serverUrl"]:
        return {**identity, "configured": False, "exists": False, "message": "Jenkins 서버 URL이 아직 설정되지 않았습니다."}
    if not settings_payload["tokenConfigured"]:
        return {**identity, "configured": False, "exists": False, "message": "Jenkins 서버 토큰이 아직 설정되지 않았습니다."}

    try:
        client = _JenkinsClient(get_jenkins_client_config())
        job_payload = client.get_job(identity["jobPath"])
    except JenkinsOperationError as exc:
        return {**identity, "configured": True, "exists": False, "message": exc.summary, "detail": exc.detail}

    if job_payload is None:
        return {**identity, "configured": True, "exists": False, "message": "Jenkins에 아직 등록되지 않았습니다.", "jobUrl": _job_browse_url(identity)}

    last_build = job_payload.get("lastBuild") or {}
    last_completed = job_payload.get("lastCompletedBuild") or {}
    last_failed = job_payload.get("lastFailedBuild") or {}
    last_success = job_payload.get("lastSuccessfulBuild") or {}

    return {
        **identity,
        "configured": True,
        "exists": True,
        "message": "Jenkins에 등록되어 있습니다.",
        "jobUrl": _job_browse_url(identity),
        "displayName": job_payload.get("displayName", ""),
        "fullName": job_payload.get("fullName", ""),
        "description": job_payload.get("description", ""),
        "building": bool(last_build.get("number") and not last_completed.get("number")),
        "latestBuildNumber": str(last_build.get("number", "")),
        "lastBuildResult": _build_result_from_number(last_build),
        "lastCompletedBuildNumber": str(last_completed.get("number", "")),
        "lastCompletedBuildResult": _build_result_from_number(last_completed),
        "lastFailedBuildNumber": str(last_failed.get("number", "")),
        "lastSuccessfulBuildNumber": str(last_success.get("number", "")),
        "inQueue": bool(job_payload.get("inQueue", False)),
        "color": job_payload.get("color", ""),
    }


def get_jenkins_job_details(job_path: str) -> dict:
    jenkins_unit = _get_jenkins_build_unit(job_path)
    if jenkins_unit is None:
        raise JenkinsOperationError("Jenkins job을 찾지 못했습니다.")

    identity = _build_job_identity(jenkins_unit)
    client = _JenkinsClient(get_jenkins_client_config())
    job_payload = client.get_job(identity["jobPath"], depth=1)
    if job_payload is None:
        raise JenkinsOperationError("Jenkins에 해당 job이 등록되어 있지 않습니다.")

    return {
        **identity,
        "jobUrl": _job_browse_url(identity),
        "raw": job_payload,
        "summary": {
            "displayName": job_payload.get("displayName", ""),
            "fullName": job_payload.get("fullName", ""),
            "description": job_payload.get("description", ""),
            "building": bool(job_payload.get("inQueue", False)),
        },
        "builds": _extract_build_summaries(job_payload.get("builds", [])),
        "lastBuild": _extract_build_summary(job_payload.get("lastBuild")),
        "lastCompletedBuild": _extract_build_summary(job_payload.get("lastCompletedBuild")),
        "lastFailedBuild": _extract_build_summary(job_payload.get("lastFailedBuild")),
        "lastSuccessfulBuild": _extract_build_summary(job_payload.get("lastSuccessfulBuild")),
        "lastStableBuild": _extract_build_summary(job_payload.get("lastStableBuild")),
        "lastUnstableBuild": _extract_build_summary(job_payload.get("lastUnstableBuild")),
    }


def get_jenkins_build_details(job_path: str, build_number: str) -> dict:
    identity = {"jobPath": job_path, "jobName": job_path.split("/")[-1]}
    client = _JenkinsClient(get_jenkins_client_config())
    build_payload = client.get_build(job_path, build_number)
    if build_payload is None:
        raise JenkinsOperationError(f"Build #{build_number}을 찾지 못했습니다.")

    return {
        **identity,
        "buildNumber": build_number,
        "raw": build_payload,
        "summary": {
            "result": build_payload.get("result", ""),
            "number": build_payload.get("number"),
            "displayName": build_payload.get("displayName", ""),
            "building": build_payload.get("building", False),
            "duration": build_payload.get("duration", 0),
            "estimatedDuration": build_payload.get("estimatedDuration", 0),
            "timestamp": build_payload.get("timestamp", 0),
            "url": build_payload.get("url", ""),
        },
        "actions": _extract_actions(build_payload.get("actions", [])),
        "artifacts": build_payload.get("artifacts", []),
    }


def trigger_jenkins_job(job_path: str, parameters: dict | None = None) -> dict:
    jenkins_unit = _get_jenkins_build_unit(job_path)
    if jenkins_unit is None:
        raise JenkinsOperationError("Jenkins job을 찾지 못했습니다.")

    identity = _build_job_identity(jenkins_unit)
    client = _JenkinsClient(get_jenkins_client_config())
    queue_item = client.build_job(identity["jobPath"], parameters=parameters or {})
    queue_id = queue_item.get("number") if queue_item else None
    return {
        **identity,
        "queued": True,
        "message": "Jenkins job 실행을 요청했습니다.",
        "queueId": queue_id,
        "parameters": parameters or {},
    }


def collect_jenkins_system_status() -> dict:
    client = _JenkinsClient(get_jenkins_client_config())
    nodes = client.get_computer_list()
    queue = client.get_queue()

    node_snapshots = []
    for node in nodes:
        resource_name = node.get("displayName", "")
        labels = node.get("assignedLabels", [])
        executors = node.get("executors", [])
        busy_count = sum(1 for e in executors if e.get("currentlyExecuting", {}).get("name"))

        snapshot = JenkinsNodeSnapshot.objects.create(
            resource_name=resource_name,
            labels_json=[label.get("name", "") for label in labels],
            executor_count=len(executors),
            busy_executors=busy_count,
            offline_reason=node.get("offlineCauseReason", ""),
            captured_at=timezone.now(),
        )
        node_snapshots.append({
            "resourceName": snapshot.resource_name,
            "labels": snapshot.labels_json,
            "executorCount": snapshot.executor_count,
            "busyExecutors": snapshot.busy_executors,
            "offline": snapshot.offline_reason != "",
            "offlineReason": snapshot.offline_reason,
        })

    queue_snapshots = []
    for item in queue:
        queue_snapshots.append({
            "queueItemKey": str(item.get("id", "")),
            "jobPath": item.get("task", {}).get("name", ""),
            "status": item.get("why", ""),
            "inQueueSince": item.get("inQueueSince"),
        })

    return {
        "nodes": node_snapshots,
        "queue": queue_snapshots,
        "nodeCount": len(node_snapshots),
        "queueSize": len(queue_snapshots),
    }


def _get_jenkins_build_unit(job_path: str) -> JenkinsBuildUnit | None:
    return JenkinsBuildUnit.objects.select_related("build_unit__project").filter(job_path=job_path).first()


def _build_job_identity(jenkins_unit: JenkinsBuildUnit | BuildUnit) -> dict[str, str]:
    if isinstance(jenkins_unit, BuildUnit):
        jenkins_unit = jenkins_unit.jenkins
    return {"jobPath": jenkins_unit.job_path, "jobName": jenkins_unit.job_path.split("/")[-1]}


def _job_browse_url(identity: dict[str, str]) -> str:
    settings_payload = get_jenkins_system_settings()
    base_url = str(settings_payload["serverUrl"]).rstrip("/")
    if not base_url:
        return ""
    encoded_parts = [parse.quote(part, safe="") for part in identity["jobPath"].split("/") if part]
    if not encoded_parts:
        return base_url
    return f"{base_url}/{'/'.join(f'job/{part}' for part in encoded_parts)}"


def _build_result_from_number(build_info: dict) -> str:
    if not build_info:
        return ""
    if build_info.get("result"):
        return build_info["result"]
    if build_info.get("building"):
        return "BUILDING"
    return "UNKNOWN"


def _extract_build_summary(build_info: dict | None) -> dict | None:
    if not build_info:
        return None
    return {
        "number": build_info.get("number"),
        "url": build_info.get("url", ""),
        "result": build_info.get("result", ""),
    }


def _extract_build_summaries(builds: list) -> list[dict]:
    return [
        {
            "number": b.get("number"),
            "url": b.get("url", ""),
        }
        for b in builds[:10]
    ]


def _extract_actions(actions: list) -> list[dict]:
    result = []
    for action in actions:
        if isinstance(action, dict):
            result.append({
                "className": action.get("_class", ""),
                "cause": action.get("causes", [{}])[0].get("shortDescription", "") if action.get("causes") else "",
            })
    return result


class _JenkinsClient:
    def __init__(self, config: JenkinsClientConfig) -> None:
        self._config = config

    def get_job(self, job_path: str, depth: int = 0) -> dict | None:
        encoded_path = "/".join(parse.quote(part, safe="") for part in job_path.split("/"))
        path = f"/api/json?depth={depth}"
        return self._request_json("GET", f"/job/{encoded_path}/{path}", allow_not_found=True)

    def get_build(self, job_path: str, build_number: str) -> dict | None:
        encoded_path = "/".join(parse.quote(part, safe="") for part in job_path.split("/"))
        path = f"/{build_number}/api/json"
        return self._request_json("GET", f"/job/{encoded_path}/{path}", allow_not_found=True)

    def build_job(self, job_path: str, parameters: dict | None = None) -> dict:
        encoded_path = "/".join(parse.quote(part, safe="") for part in job_path.split("/"))
        if parameters:
            params = parse.urlencode(parameters)
            path = f"/job/{encoded_path}/buildWithParameters?{params}"
        else:
            path = f"/job/{encoded_path}/build"
        return self._request_json("POST", path, default={})

    def get_computer_list(self) -> list:
        result = self._request_json("GET", "/computer/api/json?depth=1", default={})
        if isinstance(result, dict):
            return result.get("computer", [])
        return []

    def get_queue(self) -> list:
        result = self._request_json("GET", "/queue/api/json?depth=0", default={})
        if isinstance(result, dict):
            return result.get("items", [])
        return []

    def _request_json(self, method: str, path: str, allow_not_found: bool = False, default: dict | None = None) -> dict | list | None:
        credentials = f"{self._config.username}:{self._config.token}"
        import base64
        auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"

        req = request.Request(
            f"{self._config.server_url}{path}",
            data=None,
            headers={
                "Accept": "application/json",
                "Authorization": auth_header,
            },
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self._config.timeout_seconds) as response:
                content = response.read().decode("utf-8")
                if not content.strip():
                    return default or {}
                return json.loads(content)
        except error.HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            payload = exc.read().decode("utf-8", errors="replace")
            raise JenkinsOperationError("Jenkins API 요청이 실패했습니다.", f"{exc.code} {payload}".strip()) from exc
        except error.URLError as exc:
            raise JenkinsOperationError("Jenkins API 연결에 실패했습니다.", str(exc.reason)) from exc
