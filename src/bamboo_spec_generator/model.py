from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryDefinition:
    name: str
    branch: str


@dataclass(frozen=True)
class RequirementsDefinition:
    os: str
    extra_capabilities: list[str]


@dataclass(frozen=True)
class StaticAnalysisDefinition:
    custom_tool_commands: list[str]


@dataclass(frozen=True)
class PostBuildTriggerDefinition:
    type: str
    target_plan_key: str


@dataclass(frozen=True)
class BuildConfigDefinition:
    prepare_command: str
    build_command: str
    static_analysis: StaticAnalysisDefinition
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
