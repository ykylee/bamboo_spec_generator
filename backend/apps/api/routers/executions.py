from __future__ import annotations

from ninja import Router

from apps.api.schemas import ExecutionFinishIn, ExecutionStartIn, ExecutionStartOut
from apps.buildmeta.services import finish_execution, start_execution


router = Router(tags=["executions"])


@router.post("/build-plans/{plan_key}/executions/start", response=ExecutionStartOut)
def create_execution(request, plan_key: str, payload: ExecutionStartIn) -> dict:
    return start_execution(
        plan_key=plan_key,
        branch_kind=payload.branchKind,
        commit_hash=payload.commitHash,
        build_number=payload.buildNumber,
        started_at=payload.startedAt,
    )


@router.post("/build-executions/{execution_id}/finish")
def complete_execution(request, execution_id: str, payload: ExecutionFinishIn) -> dict:
    return finish_execution(
        execution_id=execution_id,
        success=payload.success,
        result_status=payload.resultStatus,
        summary_message=payload.summaryMessage,
        stage_name=payload.stageName,
        job_name=payload.jobName,
        task_name=payload.taskName,
        finished_at=payload.finishedAt,
        static_analysis_results=[result.dict() for result in payload.staticAnalysisResults],
    )
