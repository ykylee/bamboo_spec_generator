from __future__ import annotations

from datetime import datetime

from ninja import Schema


class StaticAnalysisResultIn(Schema):
    toolName: str
    status: str
    summary: str = ""
    metricsJson: dict | None = None


class ExecutionStartIn(Schema):
    branchKind: str
    commitHash: str
    buildNumber: str
    startedAt: datetime | None = None


class ExecutionStartOut(Schema):
    buildVersionId: str
    buildExecutionId: str
    version: str
    reusedExistingVersion: bool


class ExecutionFinishIn(Schema):
    success: bool
    resultStatus: str
    summaryMessage: str = ""
    stageName: str = ""
    jobName: str = ""
    taskName: str = ""
    finishedAt: datetime | None = None
    staticAnalysisResults: list[StaticAnalysisResultIn] = []
