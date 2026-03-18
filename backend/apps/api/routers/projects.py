from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError

from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries


router = Router(tags=["projects"])


@router.get("/")
def get_projects(request) -> list[dict]:
    return list_project_summaries()


@router.get("/{jira_project_key}")
def get_project(request, jira_project_key: str) -> dict:
    payload = get_project_detail(jira_project_key)
    if payload is None:
        raise HttpError(404, f"Project '{jira_project_key}' was not found.")
    return payload
