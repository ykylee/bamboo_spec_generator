from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StageModuleDefinition:
    module_id: str
    name: str
    order: int
    enabled: bool
    jobs: list[str]
    source_path: Path


@dataclass(frozen=True)
class JobModuleDefinition:
    module_id: str
    name: str
    ci_provider: str
    enabled: bool
    tasks: list[str]
    source_path: Path


@dataclass(frozen=True)
class TaskModuleDefinition:
    module_id: str
    name: str
    ci_provider: str
    task_kind: str
    source_path: Path


@dataclass(frozen=True)
class ModuleLoadIssue:
    module_kind: str
    module_id: str
    source_path: Path
    error_code: str
    error_message: str


@dataclass(frozen=True)
class ModuleRegistrySnapshot:
    stages: dict[str, StageModuleDefinition]
    jobs: dict[str, JobModuleDefinition]
    tasks: dict[tuple[str, str], TaskModuleDefinition]
    issues: list[ModuleLoadIssue]


def load_active_module_registry(active_root: Path) -> ModuleRegistrySnapshot:
    stage_paths = sorted((active_root / "stages" / "common").glob("*")) if (active_root / "stages" / "common").exists() else []
    job_paths = sorted((active_root / "jobs" / "common").glob("*")) if (active_root / "jobs" / "common").exists() else []
    task_paths: list[Path] = []
    for provider in ("bamboo", "jenkins"):
        provider_root = active_root / "tasks" / provider
        if provider_root.exists():
            task_paths.extend(sorted(provider_root.glob("*")))

    stages: dict[str, StageModuleDefinition] = {}
    jobs: dict[str, JobModuleDefinition] = {}
    tasks: dict[tuple[str, str], TaskModuleDefinition] = {}
    issues: list[ModuleLoadIssue] = []

    for path in stage_paths:
        module, issue = _load_stage_module(path)
        if issue:
            issues.append(issue)
            continue
        if module.module_id in stages:
            issues.append(
                ModuleLoadIssue("stage_module", module.module_id, path, "duplicate_module_id", "Duplicate stage module id")
            )
            continue
        stages[module.module_id] = module

    for path in job_paths:
        module, issue = _load_job_module(path)
        if issue:
            issues.append(issue)
            continue
        if module.module_id in jobs:
            issues.append(
                ModuleLoadIssue("job_module", module.module_id, path, "duplicate_module_id", "Duplicate job module id")
            )
            continue
        jobs[module.module_id] = module

    for path in task_paths:
        module, issue = _load_task_module(path)
        if issue:
            issues.append(issue)
            continue
        key = (module.ci_provider, module.module_id)
        if key in tasks:
            issues.append(
                ModuleLoadIssue("task_module", module.module_id, path, "duplicate_module_id", "Duplicate task module id")
            )
            continue
        tasks[key] = module

    issues.extend(_validate_registry(stages=stages, jobs=jobs, tasks=tasks))
    return ModuleRegistrySnapshot(stages=stages, jobs=jobs, tasks=tasks, issues=issues)


def _load_stage_module(path: Path) -> tuple[StageModuleDefinition | None, ModuleLoadIssue | None]:
    payload, issue = _parse_module_file(path)
    if issue:
        return None, issue
    try:
        metadata = payload["metadata"]
        spec = payload["spec"]
        return (
            StageModuleDefinition(
                module_id=str(metadata["id"]).strip(),
                name=str(metadata.get("name", metadata["id"])).strip(),
                order=int(spec.get("order", 0)),
                enabled=bool(spec.get("enabled", True)),
                jobs=[str(job).strip() for job in spec.get("jobs", [])],
                source_path=path,
            ),
            None,
        )
    except Exception as exc:
        return None, ModuleLoadIssue("stage_module", "", path, "invalid_schema", f"Invalid stage module: {exc}")


def _load_job_module(path: Path) -> tuple[JobModuleDefinition | None, ModuleLoadIssue | None]:
    payload, issue = _parse_module_file(path)
    if issue:
        return None, issue
    try:
        metadata = payload["metadata"]
        spec = payload["spec"]
        return (
            JobModuleDefinition(
                module_id=str(metadata["id"]).strip(),
                name=str(metadata.get("name", metadata["id"])).strip(),
                ci_provider=str(spec["ciProvider"]).strip(),
                enabled=bool(spec.get("enabled", True)),
                tasks=[str(task).strip() for task in spec.get("tasks", [])],
                source_path=path,
            ),
            None,
        )
    except Exception as exc:
        return None, ModuleLoadIssue("job_module", "", path, "invalid_schema", f"Invalid job module: {exc}")


def _load_task_module(path: Path) -> tuple[TaskModuleDefinition | None, ModuleLoadIssue | None]:
    payload, issue = _parse_module_file(path)
    if issue:
        return None, issue
    try:
        metadata = payload["metadata"]
        spec = payload["spec"]
        kind = str(payload["kind"]).strip()
        provider = "bamboo" if kind == "BambooTaskModule" else "jenkins" if kind == "JenkinsTaskModule" else ""
        return (
            TaskModuleDefinition(
                module_id=str(metadata["id"]).strip(),
                name=str(metadata.get("name", metadata["id"])).strip(),
                ci_provider=provider,
                task_kind=str(spec["taskKind"]).strip(),
                source_path=path,
            ),
            None,
        )
    except Exception as exc:
        return None, ModuleLoadIssue("task_module", "", path, "invalid_schema", f"Invalid task module: {exc}")


def _parse_module_file(path: Path) -> tuple[dict[str, Any], ModuleLoadIssue | None]:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                return {}, ModuleLoadIssue("", "", path, "yaml_dependency_missing", f"PyYAML is required: {exc}")
            payload = yaml.safe_load(text)
        else:
            return {}, ModuleLoadIssue("", "", path, "unsupported_extension", f"Unsupported extension: {path.suffix}")
    except Exception as exc:
        return {}, ModuleLoadIssue("", "", path, "parse_failed", f"Failed to parse module file: {exc}")
    if not isinstance(payload, dict):
        return {}, ModuleLoadIssue("", "", path, "invalid_payload", "Module payload must be an object")
    if "metadata" not in payload or "spec" not in payload:
        return {}, ModuleLoadIssue("", "", path, "invalid_payload", "Module payload must include metadata and spec")
    return payload, None


def _validate_registry(
    *,
    stages: dict[str, StageModuleDefinition],
    jobs: dict[str, JobModuleDefinition],
    tasks: dict[tuple[str, str], TaskModuleDefinition],
) -> list[ModuleLoadIssue]:
    issues: list[ModuleLoadIssue] = []
    for stage in stages.values():
        if not stage.jobs:
            issues.append(
                ModuleLoadIssue("stage_module", stage.module_id, stage.source_path, "empty_jobs", "Stage must reference at least one job")
            )
        for job_id in stage.jobs:
            if job_id not in jobs:
                issues.append(
                    ModuleLoadIssue("stage_module", stage.module_id, stage.source_path, "missing_job", f"Referenced job '{job_id}' does not exist")
                )
    for job in jobs.values():
        if job.ci_provider not in {"bamboo", "jenkins"}:
            issues.append(
                ModuleLoadIssue("job_module", job.module_id, job.source_path, "invalid_provider", f"Unsupported ciProvider '{job.ci_provider}'")
            )
            continue
        if not job.tasks:
            issues.append(
                ModuleLoadIssue("job_module", job.module_id, job.source_path, "empty_tasks", "Job must reference at least one task")
            )
        for task_id in job.tasks:
            if (job.ci_provider, task_id) not in tasks:
                issues.append(
                    ModuleLoadIssue("job_module", job.module_id, job.source_path, "missing_task", f"Referenced task '{task_id}' does not exist for provider '{job.ci_provider}'")
                )
    return issues
