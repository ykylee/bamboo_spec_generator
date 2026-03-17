from __future__ import annotations

import json
from pathlib import Path

from .model import (
    BuildConfigDefinition,
    BuildDefinition,
    PostBuildTriggerDefinition,
    RepositoryDefinition,
    RequirementsDefinition,
    StaticAnalysisDefinition,
)


def discover_input_files(input_root: Path) -> list[Path]:
    return sorted(path for path in input_root.glob("*/*.json") if path.is_file())


def parse_build_definition(path: Path) -> BuildDefinition:
    year = path.parent.name
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    repository = RepositoryDefinition(
        name=raw["repository"]["name"],
        branch=raw["repository"]["branch"],
    )

    requirements = RequirementsDefinition(
        os=raw["requirements"]["os"],
        extra_capabilities=list(raw["requirements"].get("extraCapabilities", [])),
    )

    static_analysis = StaticAnalysisDefinition(
        custom_tool_commands=list(raw["build"]["staticAnalysis"]["customTool"]["commands"]),
    )

    post_build_trigger = PostBuildTriggerDefinition(
        type=raw["build"]["postBuildTrigger"]["type"],
        target_plan_key=raw["build"]["postBuildTrigger"]["targetPlanKey"],
    )

    build_config = BuildConfigDefinition(
        prepare_command=raw["build"]["prepareCommand"],
        build_command=raw["build"]["buildCommand"],
        static_analysis=static_analysis,
        post_build_trigger=post_build_trigger,
    )

    return BuildDefinition(
        year=year,
        build_id=raw["buildId"],
        name=raw["name"],
        plan_key=raw["planKey"],
        description=raw.get("description"),
        language=raw["language"],
        compiler=raw["compiler"],
        repository=repository,
        requirements=requirements,
        build=build_config,
    )
