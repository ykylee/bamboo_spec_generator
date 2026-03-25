from __future__ import annotations

from datetime import datetime

from django.db import transaction

from apps.buildmeta.models import (
    BambooBuildInfo,
    BambooBuildUnit,
    BuildExecution,
    BuildVersion,
    StaticAnalysisResult,
)


BRANCH_KIND_MASTER = "master"
BRANCH_KIND_RELEASE = "release"
BRANCH_KIND_DEV = "dev"

INITIAL_VERSION_BY_BRANCH = {
    BRANCH_KIND_MASTER: (1, 0, 0),
    BRANCH_KIND_RELEASE: (0, 1, 0),
    BRANCH_KIND_DEV: (0, 0, 1),
}


def _next_version_numbers(latest_version: BuildVersion | None, branch_kind: str) -> tuple[int, int, int]:
    normalized = (branch_kind or BRANCH_KIND_DEV).strip().lower()
    if normalized not in INITIAL_VERSION_BY_BRANCH:
        normalized = BRANCH_KIND_DEV
    if latest_version is None:
        return INITIAL_VERSION_BY_BRANCH[normalized]
    if normalized == BRANCH_KIND_MASTER:
        return latest_version.version_major + 1, 0, 0
    if normalized == BRANCH_KIND_RELEASE:
        return latest_version.version_major, latest_version.version_minor + 1, 0
    return latest_version.version_major, latest_version.version_minor, latest_version.version_patch + 1


@transaction.atomic
def start_execution(
    *,
    plan_key: str,
    branch_kind: str,
    commit_hash: str,
    build_number: str,
    build_key: str = "",
    started_at: datetime | None = None,
) -> dict:
    bamboo_unit = (
        BambooBuildUnit.objects.select_for_update()
        .select_related("build_unit__latest_version")
        .get(plan_key=plan_key)
    )
    build_unit = bamboo_unit.build_unit
    build_info = _resolve_build_info(bamboo_unit=bamboo_unit, build_key=build_key)
    existing_execution = (
        BuildExecution.objects.select_related("build_version")
        .filter(
            build_unit=build_unit,
            execution_number=build_number,
            external_execution_key=build_info.build_key if build_info is not None else "",
        )
        .order_by("-created_at")
        .first()
    )
    if existing_execution is not None:
        if existing_execution.commit_hash != commit_hash:
            raise ValueError(
                f"Build number '{build_number}' for plan '{plan_key}' is already associated with a different commit."
            )
        version = existing_execution.build_version
        if version is not None:
            version.latest_execution = existing_execution
            version.save(update_fields=["latest_execution", "updated_at"])
        return {
            "buildVersionId": str(version.id) if version is not None else "",
            "buildExecutionId": str(existing_execution.id),
            "version": version.version_text if version is not None else "",
            "buildKey": build_info.build_key if build_info is not None else "",
            "reusedExistingVersion": True,
        }

    version = (
        BuildVersion.objects.filter(build_unit=build_unit, commit_hash=commit_hash)
        .order_by("-version_major", "-version_minor", "-version_patch", "-created_at")
        .first()
    )
    reused_existing_version = version is not None
    if version is None:
        major, minor, patch = _next_version_numbers(build_unit.latest_version, branch_kind)
        BuildVersion.objects.filter(build_unit=build_unit, is_latest=True).update(is_latest=False)
        version = BuildVersion.objects.create(
            build_unit=build_unit,
            version_text=f"v{major}.{minor}.{patch}",
            version_major=major,
            version_minor=minor,
            version_patch=patch,
            branch_kind=(branch_kind or BRANCH_KIND_DEV).strip().lower(),
            branch_name=(branch_kind or "").strip(),
            commit_hash=commit_hash,
            is_latest=True,
        )
        build_unit.latest_version = version
        build_unit.save(update_fields=["latest_version", "updated_at"])

    execution = BuildExecution.objects.create(
        build_unit=build_unit,
        build_version=version,
        execution_number=build_number,
        external_execution_key=build_info.build_key if build_info is not None else "",
        trigger_type="build",
        branch_name=(branch_kind or "").strip(),
        commit_hash=commit_hash,
        status=BuildExecution.STATUS_RUNNING,
        started_at=started_at,
    )

    version.latest_execution = execution
    version.save(update_fields=["latest_execution", "updated_at"])

    return {
        "buildVersionId": str(version.id),
        "buildExecutionId": str(execution.id),
        "version": version.version_text,
        "buildKey": build_info.build_key if build_info is not None else "",
        "reusedExistingVersion": reused_existing_version,
    }


def _resolve_build_info(*, bamboo_unit: BambooBuildUnit, build_key: str) -> BambooBuildInfo | None:
    normalized_key = build_key.strip()
    if not normalized_key:
        return None
    build_info = BambooBuildInfo.objects.filter(bamboo_build_unit=bamboo_unit, build_key=normalized_key).first()
    if build_info is None:
        raise ValueError(f"Build info '{normalized_key}' is not registered for plan '{bamboo_unit.plan_key}'.")
    return build_info


def record_static_analysis_results(*, execution_id: str, static_analysis_results: list[dict]) -> dict:
    execution = BuildExecution.objects.get(pk=execution_id)
    updated_count = 0
    for result in static_analysis_results:
        StaticAnalysisResult.objects.update_or_create(
            build_execution=execution,
            tool_name=result["toolName"],
            defaults={
                "status": result["status"],
                "summary": result.get("summary", ""),
                "metrics_json": result.get("metricsJson"),
            },
        )
        updated_count += 1
    return {
        "buildExecutionId": str(execution.id),
        "updatedCount": updated_count,
    }


@transaction.atomic
def finish_execution(
    *,
    execution_id: str,
    success: bool,
    result_status: str,
    summary_message: str = "",
    stage_name: str = "",
    job_name: str = "",
    task_name: str = "",
    finished_at: datetime | None = None,
    static_analysis_results: list[dict] | None = None,
) -> dict:
    execution = BuildExecution.objects.select_related("build_version", "build_unit").get(pk=execution_id)
    _record_static_analysis_results_for_execution(execution, static_analysis_results or [])

    normalized_status = _normalize_execution_status(result_status=result_status, success=success)
    if _should_apply_execution_finish(execution, success):
        execution.status = normalized_status
        execution.summary = summary_message
        execution.stage_name = stage_name
        execution.job_name = job_name
        execution.task_name = task_name
        execution.finished_at = finished_at
        execution.save()

    version = execution.build_version
    if version is not None:
        version.latest_execution = execution
        version.latest_success = success
        version.save(update_fields=["latest_execution", "latest_success", "updated_at"])
        if version.is_latest:
            build_unit = execution.build_unit
            build_unit.latest_version = version
            build_unit.save(update_fields=["latest_version", "updated_at"])

    return {
        "buildExecutionId": str(execution.id),
        "buildVersionId": str(version.id) if version is not None else "",
        "resultStatus": result_status,
        "success": execution.status == BuildExecution.STATUS_SUCCESS,
    }


def _record_static_analysis_results_for_execution(
    execution: BuildExecution,
    static_analysis_results: list[dict],
) -> None:
    for result in static_analysis_results:
        StaticAnalysisResult.objects.update_or_create(
            build_execution=execution,
            tool_name=result["toolName"],
            defaults={
                "status": result["status"],
                "summary": result.get("summary", ""),
                "metrics_json": result.get("metricsJson"),
            },
        )


def _normalize_execution_status(*, result_status: str, success: bool) -> str:
    normalized = (result_status or "").strip().lower()
    if normalized in {
        BuildExecution.STATUS_QUEUED,
        BuildExecution.STATUS_RUNNING,
        BuildExecution.STATUS_SUCCESS,
        BuildExecution.STATUS_FAILED,
        BuildExecution.STATUS_CANCELED,
    }:
        return normalized
    return BuildExecution.STATUS_SUCCESS if success else BuildExecution.STATUS_FAILED


def _should_apply_execution_finish(execution: BuildExecution, success: bool) -> bool:
    is_terminal = execution.finished_at is not None or execution.status != BuildExecution.STATUS_RUNNING
    if not is_terminal:
        return True
    if execution.status == BuildExecution.STATUS_FAILED and success:
        return False
    return True
