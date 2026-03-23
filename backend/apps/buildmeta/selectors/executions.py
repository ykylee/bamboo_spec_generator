from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from apps.buildmeta.models import BuildPlan


def list_latest_failed_builds(limit: int = 5) -> list[dict]:
    plans = (
        BuildPlan.objects.select_related(
            "latest_version__latest_execution",
            "project_build__project",
        )
        .filter(latest_version__latest_success=False)
        .order_by("-latest_version__latest_execution__created_at")[:limit]
    )
    return [
        {
            "projectKey": plan.project_build.project.jira_project_key,
            "buildName": plan.project_build.build_name,
            "planKey": plan.plan_key,
            "version": plan.latest_version.version_text if plan.latest_version else "",
            "buildNumber": (
                plan.latest_version.latest_execution.build_number
                if plan.latest_version and plan.latest_version.latest_execution
                else ""
            ),
            "resultStatus": (
                plan.latest_version.latest_execution.result_status
                if plan.latest_version and plan.latest_version.latest_execution
                else ""
            ),
            "summaryMessage": (
                plan.latest_version.latest_execution.summary_message
                if plan.latest_version and plan.latest_version.latest_execution
                else ""
            ),
        }
        for plan in plans
    ]


def list_build_plan_summaries() -> list[dict]:
    plans = (
        BuildPlan.objects.select_related(
            "latest_version__latest_execution",
            "project_build__project",
            "project_build__repository",
        )
        .prefetch_related("executions", "build_infos")
        .order_by("project_build__project__jira_project_key", "project_build__build_name", "plan_key")
    )
    summaries = []
    for plan in plans:
        project_build = getattr(plan, "project_build", None)
        project = project_build.project if project_build is not None else None
        repository = project_build.repository if project_build is not None else None
        latest_execution = plan.latest_version.latest_execution if plan.latest_version is not None else None
        summaries.append(
            {
                "projectKey": project.jira_project_key if project is not None else "",
                "buildName": project_build.build_name if project_build is not None else plan.plan_key,
                "buildType": project_build.build_type if project_build is not None else "",
                "runtimeStack": project_build.runtime_stack if project_build is not None else "",
                "planKey": plan.plan_key,
                "buildId": plan.build_id,
                "staticAnalysisToolVersion": plan.static_analysis_tool_version,
                "coverityProject": plan.coverity_project,
                "repositorySlug": repository.repo_slug if repository is not None else "",
                "latestVersion": plan.latest_version.version_text if plan.latest_version is not None else "",
                "latestSuccess": plan.latest_version.latest_success if plan.latest_version is not None else None,
                "resultStatus": latest_execution.result_status if latest_execution is not None else "",
                "summaryMessage": latest_execution.summary_message if latest_execution is not None else "",
                "buildInfoCount": plan.build_infos.count(),
                "detailUrl": (
                    f"/projects/{project.jira_project_key}/builds/{plan.plan_key}/"
                    if project is not None
                    else ""
                ),
                "buildInfoUrl": (
                    f"/projects/{project.jira_project_key}/builds/{plan.plan_key}/infos/"
                    if project is not None
                    else ""
                ),
            }
        )
    return summaries


def list_executions_by_plan_key(plan_key: str) -> list[dict] | None:
    try:
        plan = BuildPlan.objects.prefetch_related(
            "executions__static_analysis_results",
            "executions__build_version",
        ).get(plan_key=plan_key)
    except ObjectDoesNotExist:
        return None

    executions = plan.executions.all().order_by("-created_at")
    return [
        {
            "buildExecutionId": str(execution.id),
            "buildVersionId": str(execution.build_version_id),
            "buildKey": execution.build_info.build_key if execution.build_info_id else "",
            "version": execution.build_version.version_text,
            "buildNumber": execution.build_number,
            "commitHash": execution.commit_hash,
            "success": execution.success,
            "resultStatus": execution.result_status,
            "summaryMessage": execution.summary_message,
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
