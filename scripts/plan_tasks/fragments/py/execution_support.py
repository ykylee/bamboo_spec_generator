import json
import os
from pathlib import Path
from urllib import error, request


EXECUTION_WORKING_DIRECTORY = Path({{SUB_PATH}})
EXECUTION_STATE_DIRECTORY = EXECUTION_WORKING_DIRECTORY / ".bamboo-meta"
EXECUTION_STATE_PATH = EXECUTION_STATE_DIRECTORY / "execution-state.json"
STATIC_ANALYSIS_DIRECTORY = EXECUTION_STATE_DIRECTORY / "static-analysis"
PLAN_KEY = {{PLAN_KEY}}


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _first_environment_value(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _resolve_branch_name() -> str:
    return _first_environment_value(
        "bamboo_planRepository_branchName",
        "bamboo_repository_branch_name",
        "BAMBOO_BRANCH",
        "GIT_BRANCH",
    )


def _resolve_branch_kind(branch_name: str) -> str:
    normalized = branch_name.lower().removeprefix("refs/heads/")
    if normalized in {"master", "main"}:
        return "master"
    if normalized.startswith("release"):
        return "release"
    return "dev"


def _resolve_build_number() -> str:
    return _first_environment_value("bamboo_buildNumber", "bamboo_build_number", "BUILD_NUMBER")


def _resolve_commit_hash() -> str:
    return _first_environment_value(
        "bamboo_planRepository_revision",
        "bamboo_repository_revision",
        "GIT_COMMIT",
        "COMMIT_HASH",
    )


def _api_request(method: str, path: str, payload: dict) -> dict | None:
    base_url = os.environ.get("BAMBOO_API_BASE_URL", "").rstrip("/")
    token = os.environ.get("BAMBOO_API_TOKEN", "")
    if not base_url or not token:
        return None

    data = json.dumps(payload).encode("utf-8")
    request_obj = request.Request(
        f"{base_url}{path}",
        data=data,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with request.urlopen(request_obj, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        print(f"[execution-api] request failed: {exc}")
        return None


def _load_execution_state() -> dict:
    return _read_json(EXECUTION_STATE_PATH) or {}


def _save_execution_state(payload: dict) -> None:
    _write_json(EXECUTION_STATE_PATH, payload)


def record_static_analysis_result(tool_name: str, status: str, summary: str = "", metrics_json: dict | None = None) -> None:
    payload = {
        "toolName": tool_name,
        "status": status,
        "summary": summary,
        "metricsJson": metrics_json,
    }
    _write_json(STATIC_ANALYSIS_DIRECTORY / f"{tool_name}.json", payload)


def collect_static_analysis_results() -> list[dict]:
    if not STATIC_ANALYSIS_DIRECTORY.is_dir():
        return []
    results: list[dict] = []
    for path in sorted(STATIC_ANALYSIS_DIRECTORY.glob("*.json")):
        payload = _read_json(path)
        if payload is not None:
            results.append(payload)
    return results


def start_execution_if_configured() -> dict | None:
    state = _load_execution_state()
    if state.get("buildExecutionId"):
        return state

    build_number = _resolve_build_number()
    commit_hash = _resolve_commit_hash()
    if not PLAN_KEY or not build_number or not commit_hash:
        return None

    branch_name = _resolve_branch_name()
    payload = _api_request(
        "POST",
        f"/api/v1/build-plans/{PLAN_KEY}/executions/start",
        {
            "branchKind": _resolve_branch_kind(branch_name),
            "commitHash": commit_hash,
            "buildNumber": build_number,
        },
    )
    if payload is None:
        return None

    state = {
        "planKey": PLAN_KEY,
        "buildNumber": build_number,
        "commitHash": commit_hash,
        "branchName": branch_name,
        "buildExecutionId": payload.get("buildExecutionId", ""),
        "buildVersionId": payload.get("buildVersionId", ""),
        "version": payload.get("version", ""),
        "reusedExistingVersion": payload.get("reusedExistingVersion", False),
        "finished": False,
    }
    _save_execution_state(state)
    return state


def finish_execution_if_configured(
    *,
    success: bool,
    result_status: str,
    summary_message: str = "",
    stage_name: str = "",
    job_name: str = "",
    task_name: str = "",
) -> dict | None:
    state = _load_execution_state()
    execution_id = state.get("buildExecutionId", "")
    if not execution_id or state.get("finished"):
        return None

    payload = _api_request(
        "POST",
        f"/api/v1/build-executions/{execution_id}/finish",
        {
            "success": success,
            "resultStatus": result_status,
            "summaryMessage": summary_message,
            "stageName": stage_name,
            "jobName": job_name,
            "taskName": task_name,
            "staticAnalysisResults": collect_static_analysis_results(),
        },
    )
    if payload is None:
        return None

    state["finished"] = True
    state["success"] = success
    state["resultStatus"] = result_status
    _save_execution_state(state)
    return payload
