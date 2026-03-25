from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import BuildExecution, BuildUnit, JenkinsBuildUnit


def list_executions_by_job_path(job_path: str) -> list[dict] | None:
    try:
        jenkins_unit = JenkinsBuildUnit.objects.select_related("build_unit").get(job_path=job_path)
    except ObjectDoesNotExist:
        return None

    executions = (
        BuildExecution.objects.filter(build_unit=jenkins_unit.build_unit)
        .select_related("build_version")
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
            "resultStatus": _result_status(execution.status),
            "summaryMessage": execution.summary,
            "stageName": execution.stage_name,
            "jobName": execution.job_name,
            "taskName": execution.task_name,
            "startedAt": execution.started_at,
            "finishedAt": execution.finished_at,
            "createdAt": execution.created_at,
        }
        for execution in executions
    ]


def list_jenkins_job_summaries(*, ci_provider: str | None = None) -> list[dict]:
    build_units = (
        BuildUnit.objects.select_related(
            "project",
            "repository",
            "latest_version__latest_execution",
            "jenkins",
        )
        .prefetch_related("jenkins")
        .order_by("project__project_key", "display_name", "external_key")
    )
    if ci_provider:
        build_units = build_units.filter(ci_provider=ci_provider)
    else:
        build_units = build_units.filter(ci_provider=BuildUnit.PROVIDER_JENKINS)

    summaries = []
    for build_unit in build_units:
        latest_execution = build_unit.latest_version.latest_execution if build_unit.latest_version else None
        summaries.append(
            {
                "projectKey": build_unit.project.project_key,
                "buildName": build_unit.display_name,
                "buildType": build_unit.compiler,
                "runtimeStack": build_unit.runtime_stack,
                "jobPath": _job_path(build_unit),
                "jobType": _jenkins_attr(build_unit, "job_type"),
                "folderPath": _jenkins_attr(build_unit, "folder_path"),
                "pipelineKind": _jenkins_attr(build_unit, "pipeline_kind"),
                "repositorySlug": build_unit.repository.repo_slug if build_unit.repository_id else "",
                "latestVersion": build_unit.latest_version.version_text if build_unit.latest_version else "",
                "latestSuccess": build_unit.latest_version.latest_success if build_unit.latest_version else None,
                "resultStatus": _result_status(latest_execution.status) if latest_execution else "",
                "summaryMessage": latest_execution.summary if latest_execution else "",
                "detailUrl": f"/projects/{build_unit.project.project_key}/builds/{_job_path(build_unit)}/",
            }
        )
    return summaries


def _job_path(build_unit: BuildUnit) -> str:
    return getattr(getattr(build_unit, "jenkins", None), "job_path", "") or build_unit.external_key


def _jenkins_attr(build_unit: BuildUnit, attr: str) -> str:
    return getattr(getattr(build_unit, "jenkins", None), attr, "")


def _result_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized == BuildExecution.STATUS_SUCCESS:
        return "successful"
    return normalized
