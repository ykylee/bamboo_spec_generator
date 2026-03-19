from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import BuildPlan


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
