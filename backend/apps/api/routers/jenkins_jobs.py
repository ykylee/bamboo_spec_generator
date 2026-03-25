from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError

from apps.buildmeta.selectors.jenkins import list_executions_by_job_path, list_jenkins_job_summaries
from apps.buildmeta.services.jenkins import (
    JenkinsOperationError,
    get_jenkins_build_details,
    get_jenkins_client_config,
    get_jenkins_job_details,
    get_jenkins_job_status,
    trigger_jenkins_job,
)


router = Router(tags=["jenkins-jobs"])


@router.get("/")
def list_jenkins_jobs(request) -> list[dict]:
    return list_jenkins_job_summaries(ci_provider="jenkins")


@router.get("/{job_path}/status")
def get_jenkins_job_status_endpoint(request, job_path: str) -> dict:
    try:
        return get_jenkins_job_status(job_path)
    except JenkinsOperationError as exc:
        raise HttpError(400, exc.summary)


@router.get("/{job_path}/details")
def get_jenkins_job_details_endpoint(request, job_path: str) -> dict:
    try:
        return get_jenkins_job_details(job_path)
    except JenkinsOperationError as exc:
        raise HttpError(404, exc.summary)


@router.get("/{job_path}/executions")
def get_jenkins_executions(request, job_path: str) -> list[dict]:
    payload = list_executions_by_job_path(job_path)
    if payload is None:
        raise HttpError(404, f"Jenkins job '{job_path}' was not found.")
    return payload


@router.post("/{job_path}/trigger")
def trigger_jenkins_job_endpoint(request, job_path: str, parameters: dict | None = None) -> dict:
    try:
        return trigger_jenkins_job(job_path, parameters)
    except JenkinsOperationError as exc:
        raise HttpError(400, exc.summary)


@router.get("/{job_path}/builds/{build_number}")
def get_jenkins_build_endpoint(request, job_path: str, build_number: str) -> dict:
    try:
        return get_jenkins_build_details(job_path, build_number)
    except JenkinsOperationError as exc:
        raise HttpError(404, exc.summary)


@router.get("/system-status")
def get_jenkins_system_status(request) -> dict:
    from apps.buildmeta.services.jenkins import collect_jenkins_system_status
    try:
        collect_jenkins_system_status()
    except JenkinsOperationError as exc:
        raise HttpError(400, exc.summary)
    config = get_jenkins_client_config()
    return {
        "serverUrl": config.server_url,
        "connected": True,
    }
