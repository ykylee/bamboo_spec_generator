from __future__ import annotations

from pathlib import PurePath

from .model import BuildDefinition


class ValidationError(Exception):
    pass


SUPPORTED_COMPILERS = {
    "vs2013",
    "vs2015",
    "vs2017",
    "vs2019",
    "vs2022",
    "vs2026",
    "node.js",
    "python",
    "maven",
    "keil",
    "cmake",
}

SUPPORTED_OS = {"windows", "linux"}
SUPPORTED_REPOSITORY_PROVIDERS = {"bitbucket"}
SUPPORTED_LINKAGE_MODES = {"linked", "create_if_missing"}
DEFAULT_REPOSITORY_BRANCHES = {"dev", "release", "master"}


def validate_build_definitions(build_definitions: list[BuildDefinition]) -> None:
    plan_keys: set[str] = set()
    build_ids_by_year: dict[str, set[str]] = {}

    for build in build_definitions:
        year_build_ids = build_ids_by_year.setdefault(build.year, set())
        if build.build_id in year_build_ids:
            raise ValidationError(
                f"Duplicate buildId '{build.build_id}' in year '{build.year}'."
            )
        year_build_ids.add(build.build_id)

        if build.plan_key in plan_keys:
            raise ValidationError(f"Duplicate planKey '{build.plan_key}'.")
        plan_keys.add(build.plan_key)

        if not build.language.strip():
            raise ValidationError(f"Build '{build.build_id}' must define language.")
        if not build.compiler.strip():
            raise ValidationError(f"Build '{build.build_id}' must define compiler.")
        if build.compiler not in SUPPORTED_COMPILERS:
            raise ValidationError(
                f"Build '{build.build_id}' compiler '{build.compiler}' is not supported."
            )
        if build.requirements.os.lower() not in SUPPORTED_OS:
            raise ValidationError(
                f"Build '{build.build_id}' requirements.os '{build.requirements.os}' is not supported."
            )
        if build.repository.provider not in SUPPORTED_REPOSITORY_PROVIDERS:
            raise ValidationError(
                f"Build '{build.build_id}' repository.provider '{build.repository.provider}' is not supported."
            )
        if not build.repository.project_key.strip():
            raise ValidationError(
                f"Build '{build.build_id}' must define repository.projectKey."
            )
        if not build.repository.repo_slug.strip():
            raise ValidationError(
                f"Build '{build.build_id}' must define repository.repoSlug."
            )
        if build.repository.linkage_mode not in SUPPORTED_LINKAGE_MODES:
            raise ValidationError(
                f"Build '{build.build_id}' repository.linkageMode '{build.repository.linkage_mode}' is not supported."
            )
        if not DEFAULT_REPOSITORY_BRANCHES.issubset(set(build.repository.branches)):
            raise ValidationError(
                f"Build '{build.build_id}' repository.branches must include dev, release, and master."
            )
        if not build.build.prepare_command.strip():
            raise ValidationError(f"Build '{build.build_id}' must define prepareCommand.")
        if not build.build.build_command.strip():
            raise ValidationError(f"Build '{build.build_id}' must define buildCommand.")
        if not build.build.sub_path.strip():
            raise ValidationError(f"Build '{build.build_id}' must define build.subPath when provided.")
        if not _is_valid_sub_path(build.build.sub_path):
            raise ValidationError(
                f"Build '{build.build_id}' build.subPath '{build.build.sub_path}' must be a repository-relative path."
            )
        if not build.build.static_analysis.custom_tool_commands:
            raise ValidationError(f"Build '{build.build_id}' must define custom tool commands.")
        if not any("analyze {buildCommand}" in command for command in build.build.static_analysis.custom_tool_commands):
            raise ValidationError(
                f"Build '{build.build_id}' custom tool commands must include 'analyze {{buildCommand}}'."
            )
        if build.build.post_build_trigger.type != "plan":
            raise ValidationError(
                f"Build '{build.build_id}' postBuildTrigger.type must be 'plan'."
            )
        if not build.build.post_build_trigger.target_plan_key.strip():
            raise ValidationError(
                f"Build '{build.build_id}' must define postBuildTrigger.targetPlanKey."
            )


def _is_valid_sub_path(value: str) -> bool:
    normalized = PurePath(value)
    if normalized.is_absolute():
        return False
    return ".." not in normalized.parts
