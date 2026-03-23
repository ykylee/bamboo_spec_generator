from __future__ import annotations

import re

from django.db import transaction

from apps.buildmeta.models import BuildPlan, BuildPlanBuildInfo


def initialize_specs_draft_data(*, reset_existing: bool = False) -> dict[str, int]:
    plans = (
        BuildPlan.objects.select_related("project_build__repository")
        .prefetch_related("definitions", "build_infos")
        .order_by("plan_key")
    )

    return _initialize_specs_draft_plans(plans=plans, reset_existing=reset_existing)


def initialize_specs_draft_for_plan(*, plan_key: str, reset_existing: bool = False) -> dict[str, int]:
    plans = (
        BuildPlan.objects.filter(plan_key=plan_key)
        .select_related("project_build__repository")
        .prefetch_related("definitions", "build_infos")
    )
    return _initialize_specs_draft_plans(plans=plans, reset_existing=reset_existing)


def _initialize_specs_draft_plans(*, plans, reset_existing: bool) -> dict[str, int]:
    initialized_count = 0
    updated_count = 0
    removed_count = 0
    skipped_count = 0

    with transaction.atomic():
        for plan in plans:
            if not hasattr(plan, "project_build"):
                skipped_count += 1
                continue

            repository = getattr(plan.project_build, "repository", None)
            if reset_existing:
                removed_count += plan.build_infos.count()
                plan.build_infos.all().delete()

            if plan.build_infos.exists():
                inferred_language, inferred_compiler = _infer_language_and_compiler(
                    build_type=plan.project_build.build_type,
                    runtime_stack=plan.project_build.runtime_stack,
                )
                for build_info in plan.build_infos.all():
                    changed = False
                    normalized_operating_system = (build_info.operating_system or "linux").strip()
                    normalized_language = build_info.language.strip() or inferred_language
                    normalized_compiler = build_info.compiler.strip() or inferred_compiler
                    normalized_stream = build_info.coverity_stream.strip() or (repository.coverity_stream if repository else "")
                    normalized_sub_path = _normalize_build_sub_path(build_info.build_sub_path)

                    if build_info.operating_system != normalized_operating_system:
                        build_info.operating_system = normalized_operating_system
                        changed = True
                    if build_info.language != normalized_language:
                        build_info.language = normalized_language
                        changed = True
                    if build_info.compiler != normalized_compiler:
                        build_info.compiler = normalized_compiler
                        changed = True
                    if build_info.coverity_stream != normalized_stream:
                        build_info.coverity_stream = normalized_stream
                        changed = True
                    if build_info.build_sub_path != normalized_sub_path:
                        build_info.build_sub_path = normalized_sub_path
                        changed = True

                    if changed:
                        build_info.save(
                            update_fields=[
                                "operating_system",
                                "language",
                                "compiler",
                                "coverity_stream",
                                "build_sub_path",
                                "updated_at",
                            ]
                        )
                        updated_count += 1
                continue

            operating_system = "linux"
            inferred_language, inferred_compiler = _infer_language_and_compiler(
                build_type=plan.project_build.build_type,
                runtime_stack=plan.project_build.runtime_stack,
            )
            BuildPlanBuildInfo.objects.create(
                build_plan=plan,
                build_key=_default_build_key(build_id=plan.build_id, operating_system=operating_system),
                operating_system=operating_system,
                pre_process="",
                build_command="",
                clean_command="",
                language=inferred_language,
                compiler=inferred_compiler,
                analysis_excluded_files="",
                coverity_stream=repository.coverity_stream if repository else "",
                build_sub_path=".",
            )
            initialized_count += 1

    return {
        "initializedCount": initialized_count,
        "updatedCount": updated_count,
        "removedCount": removed_count,
        "skippedCount": skipped_count,
    }


def _default_build_key(*, build_id: str, operating_system: str) -> str:
    normalized_build_id = re.sub(r"[^a-z0-9]+", "-", build_id.strip().lower()).strip("-")
    normalized_os = re.sub(r"[^a-z0-9]+", "-", (operating_system or "linux").strip().lower()).strip("-")
    return f"{normalized_build_id}-{normalized_os}"


def _normalize_build_sub_path(value: str) -> str:
    normalized = (value or "").strip()
    return normalized or "."


def _infer_language_and_compiler(*, build_type: str, runtime_stack: str) -> tuple[str, str]:
    normalized_build_type = (build_type or "").strip().lower()
    normalized_runtime = (runtime_stack or "").strip().lower()

    if normalized_build_type == "maven" or "java" in normalized_runtime:
        return "java", "maven" if normalized_build_type == "maven" else "java"
    if normalized_build_type == "gradle":
        return "java", "gradle"
    if normalized_build_type in {"node", "javascript", "typescript"} or "node" in normalized_runtime:
        return "javascript", "node.js"
    if normalized_build_type == "python" or "python" in normalized_runtime:
        return "python", "python"
    if normalized_build_type == "dotnet" or ".net" in normalized_runtime:
        return "csharp", "dotnet"
    return "", ""
