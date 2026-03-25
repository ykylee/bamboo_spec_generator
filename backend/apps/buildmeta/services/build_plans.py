from __future__ import annotations

from apps.buildmeta.models import BambooBuildUnit


def update_build_plan_metadata(
    *,
    plan_key: str,
    static_analysis_tool_version: str,
    coverity_project: str,
    repository_linkage_mode_override: str,
) -> BambooBuildUnit | None:
    bamboo_unit = BambooBuildUnit.objects.filter(plan_key=plan_key).first()
    if bamboo_unit is None:
        return None

    bamboo_unit.static_analysis_tool_version = static_analysis_tool_version.strip()
    bamboo_unit.coverity_project = coverity_project.strip()
    bamboo_unit.repository_linkage_mode = _normalize_repository_linkage_mode_override(
        repository_linkage_mode_override
    )
    bamboo_unit.save(
        update_fields=[
            "static_analysis_tool_version",
            "coverity_project",
            "repository_linkage_mode",
            "updated_at",
        ]
    )
    return bamboo_unit


def _normalize_repository_linkage_mode_override(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"linked", "create_if_missing"}:
        return normalized
    return ""
