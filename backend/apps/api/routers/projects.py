from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError

from apps.api.schemas import ProjectCreateIn, ProjectUpdateIn
from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries
from apps.buildmeta.services import create_project, update_project


router = Router(tags=["projects"])


@router.get("/")
def get_projects(request, ci_provider: str | None = None) -> list[dict]:
    return list_project_summaries(ci_provider=ci_provider)


@router.post("/")
def post_project(request, payload: ProjectCreateIn) -> dict:
    try:
        return create_project(payload)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc


@router.get("/{project_key}")
def get_project(request, project_key: str, ci_provider: str | None = None) -> dict:
    payload = get_project_detail(project_key, ci_provider=ci_provider)
    if payload is None:
        raise HttpError(404, f"Project '{project_key}' was not found.")
    return payload


@router.put("/{project_key}")
def put_project(request, project_key: str, payload: ProjectUpdateIn, ci_provider: str | None = None) -> dict:
    try:
        result = update_project(project_key, payload, ci_provider=ci_provider)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    if result is None:
        raise HttpError(404, f"Project '{project_key}' was not found.")
    return result
