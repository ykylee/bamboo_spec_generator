from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError

from apps.buildmeta.selectors.definitions import get_active_definition_by_plan_key, get_prepare_context_by_plan_key


router = Router(tags=["build-plans"])


@router.get("/{plan_key}/active-definition")
def get_active_definition(request, plan_key: str) -> dict:
    payload = get_active_definition_by_plan_key(plan_key)
    if payload is None:
        raise HttpError(404, f"Build plan '{plan_key}' was not found.")
    return payload


@router.get("/{plan_key}/prepare-context")
def get_prepare_context(request, plan_key: str) -> dict:
    payload = get_prepare_context_by_plan_key(plan_key)
    if payload is None:
        raise HttpError(404, f"Prepare context for '{plan_key}' was not found.")
    return payload
