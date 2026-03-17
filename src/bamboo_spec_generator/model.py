from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryDefinition:
    provider: str
    project_key: str
    repo_slug: str
    linkage_mode: str
    branches: list[str]


@dataclass(frozen=True)
class RequirementsDefinition:
    os: str
    extra_capabilities: list[str]


@dataclass(frozen=True)
class StaticAnalysisDefinition:
    custom_tool_commands: list[str]


@dataclass(frozen=True)
class RuntimeRequirementsDefinition:
    commands: list[str]
    env_vars: list[str]


@dataclass(frozen=True)
class PostBuildTriggerDefinition:
    type: str
    target_plan_key: str


@dataclass(frozen=True)
class BuildConfigDefinition:
    sub_path: str
    prepare_command: str
    build_command: str
    static_analysis: StaticAnalysisDefinition
    runtime_requirements: RuntimeRequirementsDefinition
    post_build_trigger: PostBuildTriggerDefinition


@dataclass(frozen=True)
class BuildDefinition:
    year: str
    build_id: str
    name: str
    plan_key: str
    description: str | None
    language: str
    compiler: str
    repository: RepositoryDefinition
    requirements: RequirementsDefinition
    build: BuildConfigDefinition
