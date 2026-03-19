from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError

from apps.api.schemas import ProjectCreateIn, ProjectUpdateIn
from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries
from apps.buildmeta.services import create_project, update_project


router = Router(tags=["projects"])


@router.get("/")
def get_projects(request) -> list[dict]:
    return list_project_summaries()


@router.post("/")
def post_project(request, payload: ProjectCreateIn) -> dict:
    try:
        return create_project(payload)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc


@router.get("/{jira_project_key}")
def get_project(request, jira_project_key: str) -> dict:
    payload = get_project_detail(jira_project_key)
    if payload is None:
        raise HttpError(404, f"Project '{jira_project_key}' was not found.")
    return payload


@router.put("/{jira_project_key}")
def put_project(request, jira_project_key: str, payload: ProjectUpdateIn) -> dict:
    try:
        result = update_project(jira_project_key, payload)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    if result is None:
        raise HttpError(404, f"Project '{jira_project_key}' was not found.")
    return result
