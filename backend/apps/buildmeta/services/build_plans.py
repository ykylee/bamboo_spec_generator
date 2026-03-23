from __future__ import annotations

from apps.buildmeta.models import BuildPlan


def update_build_plan_metadata(*, plan_key: str, static_analysis_tool_version: str, coverity_project: str) -> BuildPlan | None:
    plan = BuildPlan.objects.filter(plan_key=plan_key).first()
    if plan is None:
        return None

    plan.static_analysis_tool_version = static_analysis_tool_version.strip()
    plan.coverity_project = coverity_project.strip()
    plan.save(update_fields=["static_analysis_tool_version", "coverity_project", "updated_at"])
    return plan
