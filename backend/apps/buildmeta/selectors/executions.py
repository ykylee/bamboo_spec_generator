from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import BambooBuildUnit, BambooPublishExecution, BuildExecution, BuildUnit


def list_latest_failed_builds(limit: int = 5) -> list[dict]:
    build_units = (
        BuildUnit.objects.select_related(
            "project",
            "repository",
            "latest_version__latest_execution",
            "bamboo",
        )
        .filter(latest_version__latest_success=False)
        .order_by("-latest_version__latest_execution__created_at")[:limit]
    )
    return [
        {
            "projectKey": build_unit.project.project_key,
            "buildName": build_unit.display_name,
            "planKey": _plan_key(build_unit),
            "version": build_unit.latest_version.version_text if build_unit.latest_version else "",
            "buildNumber": (
                build_unit.latest_version.latest_execution.execution_number
                if build_unit.latest_version and build_unit.latest_version.latest_execution
                else ""
            ),
                "resultStatus": (
                _legacy_result_status(build_unit.latest_version.latest_execution.status)
                if build_unit.latest_version and build_unit.latest_version.latest_execution
                else ""
            ),
            "summaryMessage": (
                build_unit.latest_version.latest_execution.summary
                if build_unit.latest_version and build_unit.latest_version.latest_execution
                else ""
            ),
        }
        for build_unit in build_units
    ]


def list_build_plan_summaries(*, ci_provider: str | None = None) -> list[dict]:
    build_units = (
        BuildUnit.objects.select_related(
            "project",
            "repository",
            "latest_version__latest_execution",
            "bamboo",
        )
        .prefetch_related("executions", "bamboo__build_infos")
        .order_by("project__project_key", "display_name", "external_key")
    )
    if ci_provider:
        build_units = build_units.filter(ci_provider=ci_provider)

    summaries = []
    for build_unit in build_units:
        latest_execution = build_unit.latest_version.latest_execution if build_unit.latest_version is not None else None
        summaries.append(
            {
                "projectKey": build_unit.project.project_key,
                "buildName": build_unit.display_name,
                "buildType": build_unit.compiler,
                "runtimeStack": build_unit.runtime_stack,
                "planKey": _plan_key(build_unit),
                "buildId": _build_id(build_unit),
                "staticAnalysisToolVersion": _bamboo_attr(build_unit, "static_analysis_tool_version"),
                "coverityProject": _bamboo_attr(build_unit, "coverity_project"),
                "repositorySlug": build_unit.repository.repo_slug if build_unit.repository_id else "",
                "latestVersion": build_unit.latest_version.version_text if build_unit.latest_version is not None else "",
                "latestSuccess": build_unit.latest_version.latest_success if build_unit.latest_version is not None else None,
                "resultStatus": _legacy_result_status(latest_execution.status) if latest_execution is not None else "",
                "summaryMessage": latest_execution.summary if latest_execution is not None else "",
                "buildInfoCount": build_unit.bamboo.build_infos.count() if hasattr(build_unit, "bamboo") else 0,
                "detailUrl": _detail_url(build_unit),
                "buildInfoUrl": _build_info_url(build_unit),
            }
        )
    return summaries


def list_executions_by_plan_key(plan_key: str) -> list[dict] | None:
    try:
        bamboo_unit = BambooBuildUnit.objects.select_related("build_unit").get(plan_key=plan_key)
    except ObjectDoesNotExist:
        return None

    executions = (
        BuildExecution.objects.filter(build_unit=bamboo_unit.build_unit)
        .select_related("build_version")
        .prefetch_related("static_analysis_results")
        .order_by("-created_at")
    )
    return [
        {
            "buildExecutionId": str(execution.id),
            "buildVersionId": str(execution.build_version_id or ""),
            "buildKey": execution.external_execution_key or "",
            "version": execution.build_version.version_text if execution.build_version else "",
            "buildNumber": execution.execution_number,
            "commitHash": execution.commit_hash,
            "success": execution.status == BuildExecution.STATUS_SUCCESS,
            "resultStatus": _legacy_result_status(execution.status),
            "summaryMessage": execution.summary,
            "stageName": execution.stage_name,
            "jobName": execution.job_name,
            "taskName": execution.task_name,
            "startedAt": execution.started_at,
            "finishedAt": execution.finished_at,
            "createdAt": execution.created_at,
            "staticAnalysisResults": [
                {
                    "toolName": result.tool_name,
                    "status": result.status,
                    "summary": result.summary,
                    "metricsJson": result.metrics_json,
                }
                for result in execution.static_analysis_results.all().order_by("tool_name")
            ],
        }
        for execution in executions
    ]


def list_publish_executions_by_plan_key(plan_key: str, limit: int = 5) -> list[dict]:
    executions = (
        BambooPublishExecution.objects.filter(build_unit__bamboo__plan_key=plan_key)
        .order_by("-created_at")[:limit]
    )
    return [
        {
            "publishExecutionId": str(execution.id),
            "status": execution.status,
            "message": execution.message,
            "output": execution.output,
            "returnCode": execution.return_code,
            "triggerSource": "web_ui",
            "requestedBy": "",
            "createdAt": execution.created_at,
        }
        for execution in executions
    ]


def _plan_key(build_unit: BuildUnit) -> str:
    return getattr(getattr(build_unit, "bamboo", None), "plan_key", "") or build_unit.external_key


def _build_id(build_unit: BuildUnit) -> str:
    return getattr(getattr(build_unit, "bamboo", None), "build_id", "") or build_unit.external_key


def _bamboo_attr(build_unit: BuildUnit, attr: str) -> str:
    return getattr(getattr(build_unit, "bamboo", None), attr, "")


def _detail_url(build_unit: BuildUnit) -> str:
    if build_unit.ci_provider == BuildUnit.PROVIDER_JENKINS:
        job_path = getattr(getattr(build_unit, "jenkins", None), "job_path", "") or build_unit.external_key
        return f"/projects/{build_unit.project.project_key}/jenkins-jobs/{job_path}/?provider=jenkins"
    return f"/projects/{build_unit.project.project_key}/builds/{_plan_key(build_unit)}/"


def _build_info_url(build_unit: BuildUnit) -> str:
    if build_unit.ci_provider == BuildUnit.PROVIDER_JENKINS:
        return ""
    return f"/projects/{build_unit.project.project_key}/builds/{_plan_key(build_unit)}/infos/"


def _legacy_result_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized == BuildExecution.STATUS_SUCCESS:
        return "successful"
    return normalized
