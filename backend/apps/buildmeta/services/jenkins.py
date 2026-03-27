from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib import error, parse, request
from xml.sax.saxutils import escape as xml_escape

from django.utils import timezone
from apps.buildmeta.models import JenkinsBuildUnit, JenkinsNodeSnapshot, JenkinsQueueItemSnapshot, BuildUnit
from apps.buildmeta.models import SystemSetting

from .system_settings import DEFAULT_JENKINS_TOKEN_PATH, get_jenkins_system_settings, get_system_setting


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
    settings_token = get_system_setting(SystemSetting.KEY_JENKINS_TOKEN).strip()
    file_token = ""
    if not env_token and not settings_token and DEFAULT_JENKINS_TOKEN_PATH.is_file():
        file_token = DEFAULT_JENKINS_TOKEN_PATH.read_text(encoding="utf-8").strip()
    username = env_username or "admin"
    token = env_token or settings_token or file_token
    if not server_url:
        raise JenkinsOperationError("Jenkins 서버 URL이 설정되지 않았습니다.")
    if not token:
        raise JenkinsOperationError(
            "Jenkins 토큰이 설정되지 않았습니다.",
            f"환경 변수 `JENKINS_TOKEN`, 운영 설정 토큰, 또는 `{DEFAULT_JENKINS_TOKEN_PATH}` 파일이 필요합니다.",
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


def configure_jenkins_job(job_path: str) -> dict:
    jenkins_unit = _get_jenkins_build_unit(job_path)
    if jenkins_unit is None:
        raise JenkinsOperationError("Jenkins job을 찾지 못했습니다.")

    build_unit = jenkins_unit.build_unit
    identity = _build_job_identity(jenkins_unit)
    client = _JenkinsClient(get_jenkins_client_config())
    script = _build_pipeline_script(build_unit)
    description = f"Auto managed by CI Ops Console ({build_unit.project.project_key})"
    applied = client.create_or_update_pipeline_job(identity["jobPath"], pipeline_script=script, description=description)
    return {
        **identity,
        "configured": True,
        "created": applied["created"],
        "updated": applied["updated"],
        "message": "Jenkins job 구성을 반영했습니다.",
        "detail": "created" if applied["created"] else "updated",
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


def _build_pipeline_script(build_unit: BuildUnit) -> str:
    repository = build_unit.repository
    clone_url = (repository.clone_url if repository else "").strip()
    default_branch = ((repository.default_branch if repository else "") or "main").strip() or "main"
    branch_escaped = default_branch.replace("'", "\\'")
    clone_escaped = clone_url.replace("'", "\\'")
    stage_commands = _default_pipeline_stage_commands(build_unit)

    checkout_stage = "        echo 'Repository clone URL not configured'"
    if clone_url:
        checkout_stage = f"        git branch: '{branch_escaped}', url: '{clone_escaped}'"

    dynamic_stages = [
        _pipeline_stage_shell_block(stage_name, commands)
        for stage_name, commands in stage_commands.items()
        if commands
    ]
    if not dynamic_stages:
        dynamic_stages = [_pipeline_stage_shell_block("Build", ["echo 'No build command configured'"])]

    return (
        "pipeline {\n"
        "  agent any\n"
        "  options { timestamps() }\n"
        "  stages {\n"
        "    stage('Checkout') {\n"
        "      steps {\n"
        f"{checkout_stage}\n"
        "      }\n"
        "    }\n"
        + "".join(dynamic_stages)
        + "  }\n"
        + "}\n"
    )


def _default_pipeline_stage_commands(build_unit: BuildUnit) -> dict[str, list[str]]:
    language = (build_unit.language or "").strip().lower()
    compiler = (build_unit.compiler or "").strip().lower()
    runtime_stack = (build_unit.runtime_stack or "").strip().lower()
    signal = " ".join([language, compiler, runtime_stack])

    if "maven" in signal or "java" in signal:
        return {
            "Install": ["echo 'Using Maven wrapper/config from repository'"],
            "Build": ["mvn -B -DskipTests package"],
            "Test": ["mvn -B test"],
            "Static Analysis": ["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'"],
        }
    if "gradle" in signal:
        return {
            "Install": ["echo 'Using Gradle wrapper from repository'"],
            "Build": ["./gradlew build -x test"],
            "Test": ["./gradlew test"],
            "Static Analysis": ["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'"],
        }
    if "node" in signal or "npm" in signal:
        return {
            "Install": ["npm ci || npm install"],
            "Build": ["npm run build --if-present"],
            "Test": ["npm test --if-present"],
            "Static Analysis": ["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'"],
        }
    if "dotnet" in signal or ".net" in signal:
        return {
            "Install": ["dotnet restore"],
            "Build": ["dotnet build -c Release --no-restore"],
            "Test": ["dotnet test -c Release --no-build"],
            "Static Analysis": ["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'"],
        }
    return {
        "Install": [
            "python3 -m pip install -U pip",
            "if [ -f requirements.txt ]; then pip3 install -r requirements.txt; fi",
        ],
        "Build": ["python3 -m compileall ."],
        "Test": [
            "if [ -d tests ]; then python3 -m unittest discover -s tests; else echo 'No tests directory'; fi"
        ],
        "Static Analysis": ["echo 'Static analysis stage placeholder (Coverity/Sonar integration point)'"],
    }


def _pipeline_stage_shell_block(stage_name: str, commands: list[str]) -> str:
    command_block = "\n".join(commands).strip() or "echo 'No command configured'"
    return (
        f"    stage('{stage_name}') {{\n"
        "      steps {\n"
        "        sh '''\n"
        f"{command_block}\n"
        "        '''\n"
        "      }\n"
        "    }\n"
    )


class _JenkinsClient:
    def __init__(self, config: JenkinsClientConfig) -> None:
        self._config = config
        self._crumb_field: str | None = None
        self._crumb_value: str | None = None

    def get_job(self, job_path: str, depth: int = 0) -> dict | None:
        return self._request_json("GET", f"/{_job_path_url(job_path)}/api/json?depth={depth}", allow_not_found=True)

    def get_build(self, job_path: str, build_number: str) -> dict | None:
        return self._request_json("GET", f"/{_job_path_url(job_path)}/{build_number}/api/json", allow_not_found=True)

    def build_job(self, job_path: str, parameters: dict | None = None) -> dict:
        if parameters:
            params = parse.urlencode(parameters)
            path = f"/{_job_path_url(job_path)}/buildWithParameters?{params}"
        else:
            path = f"/{_job_path_url(job_path)}/build"
        return self._request_json("POST", path, default={}, include_crumb=True)

    def create_or_update_pipeline_job(self, job_path: str, *, pipeline_script: str, description: str = "") -> dict:
        config_xml = _pipeline_job_config_xml(pipeline_script=pipeline_script, description=description)
        existing = self.get_job(job_path)
        if existing is None:
            self._ensure_folders(job_path)
            self._create_job(job_path, config_xml)
            return {"created": True, "updated": False}
        self._update_job_config(job_path, config_xml)
        return {"created": False, "updated": True}

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

    def _ensure_folders(self, job_path: str) -> None:
        parts = [part for part in job_path.split("/") if part]
        current_path = ""
        for part in parts[:-1]:
            current_path = f"{current_path}/{part}" if current_path else part
            if self.get_job(current_path) is None:
                self._create_folder(current_path)

    def _create_folder(self, folder_path: str) -> None:
        parts = [part for part in folder_path.split("/") if part]
        folder_name = parts[-1]
        parent = "/".join(parts[:-1])
        parent_prefix = f"/{_job_path_url(parent)}" if parent else ""
        params = parse.urlencode(
            {
                "name": folder_name,
                "mode": "com.cloudbees.hudson.plugins.folder.Folder",
                "from": "",
                "json": json.dumps(
                    {
                        "name": folder_name,
                        "mode": "com.cloudbees.hudson.plugins.folder.Folder",
                        "from": "",
                        "Submit": "OK",
                    }
                ),
                "Submit": "OK",
            }
        )
        self._request(
            "POST",
            f"{parent_prefix}/createItem?{params}",
            data=b"",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            include_crumb=True,
            allow_not_found=False,
            expect_json=False,
        )

    def _create_job(self, job_path: str, config_xml: str) -> None:
        parts = [part for part in job_path.split("/") if part]
        job_name = parts[-1]
        parent = "/".join(parts[:-1])
        parent_prefix = f"/{_job_path_url(parent)}" if parent else ""
        self._request(
            "POST",
            f"{parent_prefix}/createItem?name={parse.quote(job_name, safe='')}",
            data=config_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            include_crumb=True,
            allow_not_found=False,
            expect_json=False,
        )

    def _update_job_config(self, job_path: str, config_xml: str) -> None:
        self._request(
            "POST",
            f"/{_job_path_url(job_path)}/config.xml",
            data=config_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            include_crumb=True,
            allow_not_found=False,
            expect_json=False,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        allow_not_found: bool = False,
        default: dict | None = None,
        include_crumb: bool = False,
    ) -> dict | list | None:
        payload = self._request(
            method,
            path,
            include_crumb=include_crumb,
            allow_not_found=allow_not_found,
            expect_json=True,
        )
        if payload is None:
            return None
        if not payload.strip():
            return default or {}
        return json.loads(payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        include_crumb: bool = False,
        allow_not_found: bool = False,
        expect_json: bool = True,
    ) -> str | None:
        credentials = f"{self._config.username}:{self._config.token}"
        import base64
        auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"
        request_headers = {
            "Authorization": auth_header,
        }
        if expect_json:
            request_headers["Accept"] = "application/json"
        if headers:
            request_headers.update(headers)
        if include_crumb:
            request_headers.update(self._crumb_headers())
        req = request.Request(
            f"{self._config.server_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self._config.timeout_seconds) as response:
                return response.read().decode("utf-8")
        except error.HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            payload = exc.read().decode("utf-8", errors="replace")
            raise JenkinsOperationError("Jenkins API 요청이 실패했습니다.", f"{exc.code} {payload}".strip()) from exc
        except error.URLError as exc:
            raise JenkinsOperationError("Jenkins API 연결에 실패했습니다.", str(exc.reason)) from exc

    def _crumb_headers(self) -> dict[str, str]:
        if self._crumb_field and self._crumb_value:
            return {self._crumb_field: self._crumb_value}
        try:
            payload = self._request_json("GET", "/crumbIssuer/api/json", allow_not_found=True)
        except JenkinsOperationError:
            return {}
        if not isinstance(payload, dict):
            return {}
        field = str(payload.get("crumbRequestField", "")).strip()
        value = str(payload.get("crumb", "")).strip()
        if not field or not value:
            return {}
        self._crumb_field = field
        self._crumb_value = value
        return {field: value}


def _job_path_url(job_path: str) -> str:
    return "/".join(f"job/{parse.quote(part, safe='')}" for part in job_path.split("/") if part)


def _pipeline_job_config_xml(*, pipeline_script: str, description: str) -> str:
    escaped_description = xml_escape(description or "")
    escaped_script = xml_escape(pipeline_script)
    return (
        '<?xml version="1.1" encoding="UTF-8"?>\n'
        '<flow-definition plugin="workflow-job">\n'
        f"  <description>{escaped_description}</description>\n"
        "  <keepDependencies>false</keepDependencies>\n"
        '  <properties/>\n'
        '  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">\n'
        f"    <script>{escaped_script}</script>\n"
        "    <sandbox>true</sandbox>\n"
        "  </definition>\n"
        "  <triggers/>\n"
        "  <disabled>false</disabled>\n"
        "</flow-definition>\n"
    )
