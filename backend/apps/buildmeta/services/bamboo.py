from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib import error, parse, request

from apps.buildmeta.models import BuildPlan

from .system_settings import get_bamboo_system_settings


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bamboo_spec_generator.parser import parse_build_definition_payload  # noqa: E402
from src.bamboo_spec_generator.writer import write_specs_project  # noqa: E402


class BambooOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BambooClientConfig:
    server_url: str
    token: str
    timeout_seconds: float = 15.0


def get_bamboo_client_config() -> BambooClientConfig:
    settings_payload = get_bamboo_system_settings()
    server_url = str(settings_payload["serverUrl"]).rstrip("/")
    token = os.environ.get("BAMBOO_SERVER_TOKEN", "").strip()
    if not server_url:
        raise BambooOperationError("Bamboo 서버 URL이 설정되지 않았습니다.")
    if not token:
        raise BambooOperationError("BAMBOO_SERVER_TOKEN 환경 변수가 설정되지 않았습니다.")
    return BambooClientConfig(server_url=server_url, token=token)


def get_bamboo_plan_status(plan_key: str) -> dict:
    plan = _get_build_plan(plan_key)
    if plan is None:
        return {"configured": False, "exists": False, "error": "Build plan not found."}

    identity = _build_plan_identity(plan)
    settings_payload = get_bamboo_system_settings()
    if not settings_payload["serverUrl"]:
        return {
            **identity,
            "configured": False,
            "exists": False,
            "message": "Bamboo 서버 URL이 아직 설정되지 않았습니다.",
        }
    if not settings_payload["tokenConfigured"]:
        return {
            **identity,
            "configured": False,
            "exists": False,
            "message": "Bamboo 서버 토큰이 아직 설정되지 않았습니다.",
        }

    try:
        client = _BambooClient(get_bamboo_client_config())
        plan_payload = client.get_plan(identity["projectKey"], identity["planKey"])
    except BambooOperationError as exc:
        return {
            **identity,
            "configured": True,
            "exists": False,
            "message": str(exc),
        }

    if plan_payload is None:
        return {
            **identity,
            "configured": True,
            "exists": False,
            "message": "Bamboo에 아직 등록되지 않았습니다.",
            "planUrl": _plan_browse_url(identity),
        }

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
    plan = _get_build_plan(plan_key)
    if plan is None:
        raise BambooOperationError("Build plan not found.")

    identity = _build_plan_identity(plan)
    client = _BambooClient(get_bamboo_client_config())
    plan_payload = client.get_plan(
        identity["projectKey"],
        identity["planKey"],
        expand="stages.stage.jobs.job,branches.branch,actions.action,variableContext",
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
    from apps.buildmeta.selectors.definitions import get_active_definition_by_plan_key, get_prepare_context_by_plan_key

    config = get_bamboo_client_config()
    definition_payload = get_active_definition_by_plan_key(plan_key)
    if definition_payload is None:
        raise BambooOperationError("활성 Bamboo 정의를 찾지 못했습니다.")

    prepare_context = get_prepare_context_by_plan_key(plan_key)
    build = parse_build_definition_payload(
        definition_payload["definition"],
        year=str(definition_payload["year"]),
    )

    with tempfile.TemporaryDirectory(prefix=f"bamboo-publish-{plan_key.lower()}-") as temp_dir:
        output_root = Path(temp_dir) / "bamboo-specs"
        write_specs_project(output_root, [build], prepare_contexts={plan_key: prepare_context or {}})
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="bamboo-token-", delete=False) as token_file:
            token_file.write(config.token)
            token_path = Path(token_file.name)

        try:
            env = os.environ.copy()
            env["BAMBOO_URL"] = config.server_url
            env["BAMBOO_TOKEN_FILE"] = str(token_path)
            result = subprocess.run(
                ["mvn", "-q", "exec:java"],
                cwd=output_root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise BambooOperationError(f"Maven publish 실행에 실패했습니다: {exc}") from exc
        finally:
            if token_path.exists():
                token_path.unlink()

    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    return {
        "success": result.returncode == 0,
        "returnCode": result.returncode,
        "message": "Bamboo Specs publish가 완료되었습니다." if result.returncode == 0 else "Bamboo Specs publish에 실패했습니다.",
        "output": output,
    }


def queue_bamboo_plan(plan_key: str) -> dict:
    plan = _get_build_plan(plan_key)
    if plan is None:
        raise BambooOperationError("Build plan not found.")

    identity = _build_plan_identity(plan)
    client = _BambooClient(get_bamboo_client_config())
    payload = client.queue_plan(identity["fullPlanKey"])
    return {
        **identity,
        "queued": True,
        "message": "Bamboo plan 실행을 요청했습니다.",
        "raw": payload,
    }


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

    def queue_plan(self, full_plan_key: str) -> dict:
        path = f"/rest/api/latest/queue/{parse.quote(full_plan_key)}"
        return self._request_json("POST", path, default={})

    def _request_json(self, method: str, path: str, allow_not_found: bool = False, default: dict | None = None) -> dict | None:
        req = request.Request(
            f"{self._config.server_url}{path}",
            data=None,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._config.token}",
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
            raise BambooOperationError(f"Bamboo API 요청이 실패했습니다: {exc.code} {payload}".strip()) from exc
        except error.URLError as exc:
            raise BambooOperationError(f"Bamboo API 연결에 실패했습니다: {exc.reason}") from exc


def _get_build_plan(plan_key: str) -> BuildPlan | None:
    return (
        BuildPlan.objects.select_related("project_build__project")
        .filter(plan_key=plan_key)
        .first()
    )


def _build_plan_identity(plan: BuildPlan) -> dict[str, str]:
    try:
        project_build = plan.project_build
    except BuildPlan.project_build.RelatedObjectDoesNotExist:
        project_build = None
    project = project_build.project if project_build is not None else None
    project_key = project.bitbucket_project_key if project is not None else ""
    full_plan_key = f"{project_key}-{plan.plan_key}" if project_key else plan.plan_key
    return {
        "projectKey": project_key,
        "planKey": plan.plan_key,
        "fullPlanKey": full_plan_key,
    }


def _plan_browse_url(identity: dict[str, str]) -> str:
    settings_payload = get_bamboo_system_settings()
    base_url = str(settings_payload["serverUrl"]).rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/browse/{identity['fullPlanKey']}"


def _extract_latest_result(payload: dict) -> dict:
    results = payload.get("results", {}) if isinstance(payload, dict) else {}
    result_items = results.get("result") if isinstance(results, dict) else None
    if isinstance(result_items, list) and result_items:
        result = result_items[0]
    elif isinstance(result_items, dict):
        result = result_items
    else:
        result = {}
    link = ""
    link_payload = result.get("link")
    if isinstance(link_payload, dict):
        href = link_payload.get("href")
        if isinstance(href, str):
            link = href
    return {
        "state": result.get("state", "") or result.get("buildState", ""),
        "number": str(result.get("number", "") or result.get("buildNumber", "")),
        "key": result.get("key", "") or result.get("planResultKey", {}).get("key", ""),
        "link": link,
    }


def _extract_stages(payload: dict) -> list[dict]:
    container = payload.get("stages")
    stage_items = container.get("stage") if isinstance(container, dict) else []
    if isinstance(stage_items, dict):
        stage_items = [stage_items]
    stages: list[dict] = []
    for stage in stage_items or []:
        jobs_container = stage.get("jobs", {}) if isinstance(stage, dict) else {}
        jobs = jobs_container.get("job") if isinstance(jobs_container, dict) else []
        if isinstance(jobs, dict):
            jobs = [jobs]
        stages.append(
            {
                "name": stage.get("name", ""),
                "description": stage.get("description", ""),
                "jobs": [
                    {
                        "key": job.get("key", ""),
                        "name": job.get("name", ""),
                    }
                    for job in jobs or []
                    if isinstance(job, dict)
                ],
            }
        )
    return stages


def _extract_named_items(container: dict | None, item_key: str) -> list[dict]:
    items = container.get(item_key) if isinstance(container, dict) else []
    if isinstance(items, dict):
        items = [items]
    return [item for item in items or [] if isinstance(item, dict)]


def _extract_variables(container: dict | None) -> list[dict]:
    if not isinstance(container, dict):
        return []
    variables = []
    for key, value in sorted(container.items()):
        if isinstance(value, (str, int, float, bool)) or value is None:
            variables.append({"key": key, "value": "" if value is None else str(value)})
    return variables
