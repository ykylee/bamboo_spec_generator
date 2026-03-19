from __future__ import annotations

from datetime import datetime

from django.db import transaction

from apps.buildmeta.models import BuildExecution, BuildPlan, BuildVersion, StaticAnalysisResult


INITIAL_VERSION_BY_BRANCH = {
    BuildVersion.BRANCH_KIND_MASTER: (1, 0, 0),
    BuildVersion.BRANCH_KIND_RELEASE: (0, 1, 0),
    BuildVersion.BRANCH_KIND_DEV: (0, 0, 1),
}


def _next_version_numbers(latest_version: BuildVersion | None, branch_kind: str) -> tuple[int, int, int]:
    if latest_version is None:
        return INITIAL_VERSION_BY_BRANCH[branch_kind]
    if branch_kind == BuildVersion.BRANCH_KIND_MASTER:
        return latest_version.major + 1, 0, 0
    if branch_kind == BuildVersion.BRANCH_KIND_RELEASE:
        return latest_version.major, latest_version.minor + 1, 0
    return latest_version.major, latest_version.minor, latest_version.patch + 1


@transaction.atomic
def start_execution(
    *,
    plan_key: str,
    branch_kind: str,
    commit_hash: str,
    build_number: str,
    started_at: datetime | None = None,
) -> dict:
    plan = BuildPlan.objects.select_for_update().select_related("latest_version").get(plan_key=plan_key)
    existing_execution = (
        BuildExecution.objects.select_related("build_version")
        .filter(build_plan=plan, build_number=build_number)
        .order_by("-created_at")
        .first()
    )
    if existing_execution is not None:
        if existing_execution.commit_hash != commit_hash:
            raise ValueError(
                f"Build number '{build_number}' for plan '{plan_key}' is already associated with a different commit."
            )
        version = existing_execution.build_version
        version.latest_execution = existing_execution
        version.save(update_fields=["latest_execution", "updated_at"])
        return {
            "buildVersionId": str(version.id),
            "buildExecutionId": str(existing_execution.id),
            "version": version.version_text,
            "reusedExistingVersion": True,
        }

    version = BuildVersion.objects.filter(
        build_plan=plan,
        commit_hash=commit_hash,
    ).order_by("-major", "-minor", "-patch", "-created_at").first()
    reused_existing_version = version is not None
    if version is None:
        major, minor, patch = _next_version_numbers(plan.latest_version, branch_kind)
        BuildVersion.objects.filter(build_plan=plan, is_latest=True).update(is_latest=False)
        version = BuildVersion.objects.create(
            build_plan=plan,
            version_text=f"v{major}.{minor}.{patch}",
            major=major,
            minor=minor,
            patch=patch,
            branch_kind=branch_kind,
            commit_hash=commit_hash,
            is_latest=True,
        )
        plan.latest_version = version
        plan.save(update_fields=["latest_version", "updated_at"])

    execution = BuildExecution.objects.create(
        build_plan=plan,
        build_version=version,
        build_number=build_number,
        commit_hash=commit_hash,
        success=False,
        result_status="running",
        started_at=started_at,
    )

    version.latest_execution = execution
    version.save(update_fields=["latest_execution", "updated_at"])

    return {
        "buildVersionId": str(version.id),
        "buildExecutionId": str(execution.id),
        "version": version.version_text,
        "reusedExistingVersion": reused_existing_version,
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
    execution = BuildExecution.objects.select_related("build_version", "build_plan").get(pk=execution_id)
    execution.success = success
    execution.result_status = result_status
    execution.summary_message = summary_message
    execution.stage_name = stage_name
    execution.job_name = job_name
    execution.task_name = task_name
    execution.finished_at = finished_at
    execution.save()

    for result in static_analysis_results or []:
        StaticAnalysisResult.objects.update_or_create(
            build_execution=execution,
            tool_name=result["toolName"],
            defaults={
                "status": result["status"],
                "summary": result.get("summary", ""),
                "metrics_json": result.get("metricsJson"),
            },
        )

    version = execution.build_version
    version.latest_execution = execution
    version.latest_success = success
    version.save(update_fields=["latest_execution", "latest_success", "updated_at"])

    if version.is_latest:
        plan = execution.build_plan
        plan.latest_version = version
        plan.save(update_fields=["latest_version", "updated_at"])

    return {
        "buildExecutionId": str(execution.id),
        "buildVersionId": str(version.id),
        "resultStatus": execution.result_status,
        "success": execution.success,
    }
