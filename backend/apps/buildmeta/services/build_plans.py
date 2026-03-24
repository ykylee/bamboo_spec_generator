from __future__ import annotations

from apps.buildmeta.models import BuildPlan


def update_build_plan_metadata(
    *,
    plan_key: str,
    static_analysis_tool_version: str,
    coverity_project: str,
    repository_linkage_mode_override: str,
) -> BuildPlan | None:
    plan = BuildPlan.objects.filter(plan_key=plan_key).first()
    if plan is None:
        return None

    plan.static_analysis_tool_version = static_analysis_tool_version.strip()
    plan.coverity_project = coverity_project.strip()
    plan.repository_linkage_mode_override = _normalize_repository_linkage_mode_override(
        repository_linkage_mode_override
    )
    plan.save(
        update_fields=[
            "static_analysis_tool_version",
            "coverity_project",
            "repository_linkage_mode_override",
            "updated_at",
        ]
    )
    return plan


def _normalize_repository_linkage_mode_override(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {
        BuildPlan.REPOSITORY_LINKAGE_MODE_LINKED,
        BuildPlan.REPOSITORY_LINKAGE_MODE_CREATE_IF_MISSING,
    }:
        return normalized
    return ""
