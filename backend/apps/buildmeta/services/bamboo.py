from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib import error, parse, request

from django.utils import timezone

from apps.buildmeta.models import BambooBuildUnit, BambooPublishExecution, BuildUnit

from .system_settings import DEFAULT_BAMBOO_TOKEN_PATH, get_bamboo_system_settings


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bamboo_spec_generator.parser import parse_build_definition_payload  # noqa: E402
from src.bamboo_spec_generator.writer import write_specs_project  # noqa: E402


class BambooOperationError(RuntimeError):
    def __init__(self, summary: str, detail: str = "") -> None:
        super().__init__(summary)
        self.summary = summary
        self.detail = detail


@dataclass(frozen=True)
class BambooClientConfig:
    server_url: str
    token: str
    token_file_path: str | None = None
    timeout_seconds: float = 15.0


def get_bamboo_client_config() -> BambooClientConfig:
    settings_payload = get_bamboo_system_settings()
    server_url = str(settings_payload["serverUrl"]).rstrip("/")
    env_declared = "BAMBOO_SERVER_TOKEN" in os.environ
    env_token = os.environ.get("BAMBOO_SERVER_TOKEN", "").strip()
    file_token = ""
    api_token = ""
    if not env_declared and DEFAULT_BAMBOO_TOKEN_PATH.is_file():
        file_token = DEFAULT_BAMBOO_TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not env_declared and not file_token:
        api_token = os.environ.get("BAMBOO_API_TOKEN", "").strip()
    token = _normalize_bamboo_token(env_token or file_token or api_token)
    if not server_url:
        raise BambooOperationError("Bamboo 서버 URL이 설정되지 않았습니다.")
    if not token:
        raise BambooOperationError(
            "Bamboo 토큰이 설정되지 않았습니다.",
            f"환경 변수 `BAMBOO_SERVER_TOKEN` 또는 `{DEFAULT_BAMBOO_TOKEN_PATH}` 파일이 필요합니다.",
        )
    return BambooClientConfig(
        server_url=server_url,
        token=token,
        token_file_path=None if env_token else str(DEFAULT_BAMBOO_TOKEN_PATH) if file_token else None,
    )


def get_bamboo_plan_status(plan_key: str) -> dict:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        return {"configured": False, "exists": False, "error": "Build plan not found."}

    identity = _build_plan_identity(bamboo_unit)
    settings_payload = get_bamboo_system_settings()
    if not settings_payload["serverUrl"]:
        return {**identity, "configured": False, "exists": False, "message": "Bamboo 서버 URL이 아직 설정되지 않았습니다."}
    if not settings_payload["tokenConfigured"]:
        return {**identity, "configured": False, "exists": False, "message": "Bamboo 서버 토큰이 아직 설정되지 않았습니다."}

    try:
        client = _BambooClient(get_bamboo_client_config())
        plan_payload = client.get_plan(identity["projectKey"], identity["planKey"])
    except BambooOperationError as exc:
        return {**identity, "configured": True, "exists": False, "message": exc.summary, "detail": exc.detail}

    if plan_payload is None:
        return {**identity, "configured": True, "exists": False, "message": "Bamboo에 아직 등록되지 않았습니다.", "planUrl": _plan_browse_url(identity)}

    result_payload = client.get_latest_result(identity["fullPlanKey"])
    latest_result = _extract_latest_result(result_payload)
    return {
        **identity,
        "configured": True,
        "exists": True,
        "message": "Bamboo에 등록되어 있습니다.",
        "planUrl": _plan_browse_url(identity),
        "enabled": bool(plan_payload.get("enabled", True)),
        "suspended": bool(plan_payload.get("isSuspended", False)),
        "building": bool(plan_payload.get("isBuilding", False)),
        "description": plan_payload.get("description", ""),
        "shortName": plan_payload.get("shortName", ""),
        "latestResultState": latest_result.get("state", ""),
        "latestBuildNumber": latest_result.get("number", ""),
        "latestResultKey": latest_result.get("key", ""),
        "latestResultUrl": latest_result.get("link", ""),
    }


def get_bamboo_plan_details(plan_key: str) -> dict:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        raise BambooOperationError("Build plan을 찾지 못했습니다.")

    identity = _build_plan_identity(bamboo_unit)
    client = _BambooClient(get_bamboo_client_config())
    plan_payload = client.get_plan(
        identity["projectKey"],
        identity["planKey"],
        expand="stages.stage.jobs.job,stages.stage.plans.plan,branches.branch,actions.action,variableContext",
    )
    if plan_payload is None:
        raise BambooOperationError("Bamboo에 해당 plan이 등록되어 있지 않습니다.")

    return {
        **identity,
        "planUrl": _plan_browse_url(identity),
        "raw": plan_payload,
        "summary": {
            "shortName": plan_payload.get("shortName", ""),
            "description": plan_payload.get("description", ""),
            "enabled": bool(plan_payload.get("enabled", True)),
            "suspended": bool(plan_payload.get("isSuspended", False)),
            "building": bool(plan_payload.get("isBuilding", False)),
        },
        "stages": _extract_stages(plan_payload),
        "branches": _extract_named_items(plan_payload.get("branches"), "branch"),
        "actions": _extract_named_items(plan_payload.get("actions"), "action"),
        "variables": _extract_variables(plan_payload.get("variableContext")),
    }


def publish_bamboo_specs(plan_key: str) -> dict:
    from apps.buildmeta.selectors.definitions import (
        get_active_definitions_by_plan_key,
        get_build_plan_export_draft,
        get_build_plan_preview,
        get_prepare_context_by_plan_key,
    )

    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        raise BambooOperationError("Build plan을 찾지 못했습니다.")

    try:
        config = get_bamboo_client_config()
    except BambooOperationError as exc:
        _record_publish_execution(build_unit=bamboo_unit, status="failed", message=exc.summary, output=exc.detail, return_code=None)
        raise

    definition_payloads = get_active_definitions_by_plan_key(plan_key)
    if not definition_payloads:
        _record_publish_execution(build_unit=bamboo_unit, status="failed", message="활성 Bamboo 정의를 찾지 못했습니다.", output="", return_code=None)
        raise BambooOperationError("활성 Bamboo 정의를 찾지 못했습니다.")

    prepare_context = get_prepare_context_by_plan_key(plan_key)
    builds = [
        parse_build_definition_payload(definition_payload["definition"], year=str(definition_payload["year"]))
        for definition_payload in definition_payloads
    ]
    preview_snapshot = get_build_plan_preview(plan_key)
    export_draft_snapshot = get_build_plan_export_draft(plan_key)

    with tempfile.TemporaryDirectory(prefix=f"bamboo-publish-{plan_key.lower()}-") as temp_dir:
        output_root = Path(temp_dir) / "bamboo-specs"
        write_specs_project(output_root, builds, prepare_contexts={plan_key: prepare_context or {}})
        token_path: Path | None = None
        created_temp_token = False
        if config.token_file_path:
            token_path = Path(config.token_file_path)
        else:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="bamboo-token-", delete=False) as token_file:
                token_file.write(config.token)
                token_path = Path(token_file.name)
                created_temp_token = True
        try:
            env = os.environ.copy()
            env["BAMBOO_URL"] = config.server_url
            env["BAMBOO_TOKEN_FILE"] = str(token_path)
            result = subprocess.run(
                ["mvn", "-q", "-DskipTests", "compile", "exec:java"],
                cwd=output_root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            _record_publish_execution(build_unit=bamboo_unit, status="failed", message="Maven publish 실행에 실패했습니다.", output=str(exc), return_code=None)
            raise BambooOperationError("Maven publish 실행에 실패했습니다.", str(exc)) from exc
        finally:
            if created_temp_token and token_path is not None and token_path.exists():
                token_path.unlink()

    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    success = result.returncode == 0
    _record_publish_execution(
        build_unit=bamboo_unit,
        status="successful" if success else "failed",
        message="Bamboo Specs publish가 완료되었습니다." if success else "Bamboo Specs publish에 실패했습니다.",
        output=output,
        snapshot_preview_json=preview_snapshot if success else None,
        snapshot_export_draft_json=export_draft_snapshot if success else None,
        return_code=result.returncode,
    )
    return {
        "success": success,
        "returnCode": result.returncode,
        "message": "Bamboo Specs publish가 완료되었습니다." if success else "Bamboo Specs publish에 실패했습니다.",
        "output": output,
        "detail": output,
    }


def queue_bamboo_plan(plan_key: str) -> dict:
    return queue_bamboo_plan_with_options(plan_key)


def queue_bamboo_plan_with_options(
    plan_key: str,
    *,
    stage: str = "",
    execute_all_stages: bool = False,
    custom_revision: str = "",
    variables: dict[str, str] | None = None,
) -> dict:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        raise BambooOperationError("Build plan을 찾지 못했습니다.")

    identity = _build_plan_identity(bamboo_unit)
    client = _BambooClient(get_bamboo_client_config())
    payload = client.queue_plan(
        identity["fullPlanKey"],
        stage=stage,
        execute_all_stages=execute_all_stages,
        custom_revision=custom_revision,
        variables=variables or {},
    )
    return {
        **identity,
        "queued": True,
        "message": "Bamboo plan 실행을 요청했습니다.",
        "stage": stage,
        "executeAllStages": execute_all_stages,
        "customRevision": custom_revision,
        "variables": variables or {},
        "detail": _format_queue_detail(stage=stage, execute_all_stages=execute_all_stages, custom_revision=custom_revision, variables=variables or {}),
        "raw": payload,
    }


def _record_publish_execution(
    *,
    build_unit: BambooBuildUnit,
    status: str,
    message: str,
    output: str,
    return_code: int | None,
    snapshot_preview_json: dict | None = None,
    snapshot_export_draft_json: dict | None = None,
) -> BambooPublishExecution:
    execution = BambooPublishExecution.objects.create(
        build_unit=build_unit.build_unit,
        status=status,
        message=message,
        output=output,
        snapshot_preview_json=snapshot_preview_json,
        snapshot_export_draft_json=snapshot_export_draft_json,
        return_code=return_code,
    )
    return execution


def _get_bamboo_build_unit(plan_key: str) -> BambooBuildUnit | None:
    return BambooBuildUnit.objects.select_related("build_unit__project").filter(plan_key=plan_key).first()


def _build_plan_identity(bamboo_unit: BambooBuildUnit | BuildUnit) -> dict[str, str]:
    if isinstance(bamboo_unit, BuildUnit):
        bamboo_unit = bamboo_unit.bamboo
    project_key = _resolve_bamboo_project_key(bamboo_unit)
    full_plan_key = f"{project_key}-{bamboo_unit.plan_key}" if project_key else bamboo_unit.plan_key
    return {"projectKey": project_key, "planKey": bamboo_unit.plan_key, "fullPlanKey": full_plan_key}


def _resolve_bamboo_project_key(bamboo_unit: BambooBuildUnit | BuildUnit) -> str:
    if isinstance(bamboo_unit, BuildUnit):
        bamboo_unit = bamboo_unit.bamboo
    active_definition = bamboo_unit.build_unit.definitions.filter(is_active=True).order_by("-created_at").first()
    if active_definition is not None and active_definition.year.strip():
        return f"Y{active_definition.year.strip()}"
    return f"Y{timezone.now().year}"


def _normalize_bamboo_token(value: str) -> str:
    normalized = (value or "").strip()
    if normalized.startswith("token="):
        return normalized.split("=", 1)[1].strip()
    return normalized


def _plan_browse_url(identity: dict[str, str]) -> str:
    settings_payload = get_bamboo_system_settings()
    base_url = str(settings_payload["serverUrl"]).rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/browse/{identity['fullPlanKey']}"


def _format_queue_detail(*, stage: str, execute_all_stages: bool, custom_revision: str, variables: dict[str, str]) -> str:
    lines = [f"stage={stage or '-'}", f"executeAllStages={'true' if execute_all_stages else 'false'}", f"customRevision={custom_revision or '-'}"]
    if variables:
        lines.append("variables=")
        for key, value in sorted(variables.items()):
            lines.append(f"  {key}={value}")
    return "\n".join(lines)


class _BambooClient:
    def __init__(self, config: BambooClientConfig) -> None:
        self._config = config

    def get_plan(self, project_key: str, plan_key: str, expand: str = "") -> dict | None:
        path = f"/rest/api/latest/plan/{parse.quote(project_key)}/{parse.quote(plan_key)}"
        if expand:
            path += f"?expand={parse.quote(expand, safe=',.')}"
        return self._request_json("GET", path, allow_not_found=True)

    def get_latest_result(self, full_plan_key: str) -> dict:
        path = f"/rest/api/latest/result/{parse.quote(full_plan_key)}?max-result=1"
        return self._request_json("GET", path, default={})

    def queue_plan(self, full_plan_key: str, *, stage: str = "", execute_all_stages: bool = False, custom_revision: str = "", variables: dict[str, str] | None = None) -> dict:
        params: list[tuple[str, str]] = []
        if stage.strip():
            params.append(("stage", stage.strip()))
        if execute_all_stages:
            params.append(("executeAllStages", "true"))
        if custom_revision.strip():
            params.append(("customRevision", custom_revision.strip()))
        for key, value in (variables or {}).items():
            normalized_key = key.strip()
            if not normalized_key:
                continue
            params.append((normalized_key, value))
        query = f"?{parse.urlencode(params)}" if params else ""
        path = f"/rest/api/latest/queue/{parse.quote(full_plan_key)}{query}"
        return self._request_json("POST", path, default={})

    def _request_json(self, method: str, path: str, allow_not_found: bool = False, default: dict | None = None) -> dict | None:
        req = request.Request(
            f"{self._config.server_url}{path}",
            data=None,
            headers={"Accept": "application/json", "Authorization": f"Bearer {self._config.token}"},
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
            raise BambooOperationError("Bamboo API 요청이 실패했습니다.", f"{exc.code} {payload}".strip()) from exc
        except error.URLError as exc:
            raise BambooOperationError("Bamboo API 연결에 실패했습니다.", str(exc.reason)) from exc


def _extract_latest_result(payload: dict) -> dict:
    result: dict = {}
    results = payload.get("results", {}) if isinstance(payload, dict) else {}
    result_items = results.get("result") if isinstance(results, dict) else None
    if isinstance(result_items, list) and result_items:
        result = result_items[0]
    elif isinstance(result_items, dict):
        result = result_items
    elif isinstance(payload, dict):
        direct_result_items = payload.get("result")
        if isinstance(direct_result_items, list) and direct_result_items:
            result = direct_result_items[0]
        elif isinstance(direct_result_items, dict):
            result = direct_result_items
        elif any(key in payload for key in ("state", "buildState", "number", "buildNumber", "key", "planResultKey")):
            result = payload
    link = ""
    link_payload = result.get("link")
    if isinstance(link_payload, dict):
        href = link_payload.get("href") or link_payload.get("url")
        if isinstance(href, str):
            link = href
    elif isinstance(link_payload, str):
        link = link_payload
    plan_result_key = result.get("planResultKey")
    normalized_result_key = plan_result_key.get("key", "") if isinstance(plan_result_key, dict) else plan_result_key or ""
    return {"state": result.get("state", "") or result.get("buildState", ""), "number": str(result.get("number", "") or result.get("buildNumber", "")), "key": result.get("key", "") or normalized_result_key, "link": link}


def _extract_stages(payload: dict) -> list[dict]:
    container = payload.get("stages")
    if isinstance(container, dict):
        stage_items = container.get("stage")
        if stage_items is None and any(key in container for key in ("name", "description", "jobs", "plans")):
            stage_items = [container]
    else:
        stage_items = container if isinstance(container, list) else []
    if isinstance(stage_items, dict):
        stage_items = [stage_items]
    stages: list[dict] = []
    for stage in stage_items or []:
        if not isinstance(stage, dict):
            continue
        jobs = _extract_stage_jobs(stage)
        stages.append({"name": stage.get("name", ""), "description": stage.get("description", ""), "jobs": [{"key": job.get("key", ""), "name": job.get("name", "")} for job in jobs or [] if isinstance(job, dict)]})
    return stages


def _extract_stage_jobs(stage: dict) -> list[dict]:
    if not isinstance(stage, dict):
        return []
    jobs_container = stage.get("jobs")
    if isinstance(jobs_container, list):
        return [item for item in jobs_container if isinstance(item, dict)]
    if isinstance(jobs_container, dict):
        job_items = jobs_container.get("job")
        if isinstance(job_items, dict):
            return [job_items]
        if isinstance(job_items, list):
            return job_items
    plans_container = stage.get("plans")
    if isinstance(plans_container, dict):
        plan_items = plans_container.get("plan", plans_container)
        if isinstance(plan_items, dict):
            return [plan_items]
        if isinstance(plan_items, list):
            return [item for item in plan_items if isinstance(item, dict)]
    return []


def _extract_named_items(container: dict | None, item_key: str) -> list[dict]:
    if isinstance(container, list):
        items = container
    elif isinstance(container, dict):
        items = container.get(item_key, container)
    else:
        return []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = {"name": item.get("name", "")}
        if "key" in item:
            payload["key"] = item.get("key", "")
        normalized.append(payload)
    return normalized


def _extract_variables(container: dict | None) -> list[dict]:
    if not isinstance(container, dict):
        return []
    variables = container.get("variable")
    if variables is None and "variables" in container:
        nested_variables = container.get("variables")
        if isinstance(nested_variables, dict):
            variables = nested_variables.get("variable", nested_variables)
        elif isinstance(nested_variables, list):
            variables = nested_variables
        else:
            return []
    if variables is None:
        items = []
        for key, value in container.items():
            if isinstance(value, dict):
                continue
            items.append({"key": key, "value": "" if value is None else str(value)})
        return sorted(items, key=lambda item: item["key"])
    if isinstance(variables, dict):
        variables = [variables]
    if not isinstance(variables, list):
        return []
    items = []
    for item in variables:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("name") or ""
        value = item.get("value")
        if value is None:
            value = item.get("valueAsString")
        items.append({"key": str(key), "value": "" if value is None else str(value)})
    return sorted(items, key=lambda item: item["key"])
