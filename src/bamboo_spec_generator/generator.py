from __future__ import annotations

from .model import BuildDefinition


def to_java_class_name(build_id: str) -> str:
    return "".join(part.capitalize() for part in build_id.replace("_", "-").split("-")) + "PlanSpecs"


def generate_plan_java(build: BuildDefinition, package_name: str) -> str:
    class_name = to_java_class_name(build.build_id)
    description = _escape_java(build.description or build.name)
    project_key = _project_key(build.year)
    build_script_root = f"scripts/generated/{build.build_id}"

    return f"""package {package_name};

import com.atlassian.bamboo.specs.api.builders.job.Job;
import com.atlassian.bamboo.specs.api.builders.plan.Plan;
import com.atlassian.bamboo.specs.api.builders.plan.Project;
import com.atlassian.bamboo.specs.api.builders.plan.Stage;
import com.atlassian.bamboo.specs.api.builders.requirement.Requirement;
import com.atlassian.bamboo.specs.builders.task.ScriptTask;

// Sample generated Bamboo Specs source close to Bamboo Java Specs builder style.
public final class {class_name} {{
    private static final String PROJECT_KEY = "{project_key}";
    private static final String PLAN_KEY = "{build.plan_key}";
    private static final String YEAR = "{build.year}";
    private static final String SCRIPT_ROOT = "{build_script_root}";

    private {class_name}() {{
    }}

    public static Plan plan() {{
        Project project = new Project()
            .key(PROJECT_KEY)
            .name("Generated Plans " + YEAR);

        return new Plan(project, "{description}", PLAN_KEY)
            .description("{description}")
            .stages(
                prepareStage(),
                buildStage(),
                staticAnalysisStage(),
                triggerFollowUpStage()
            );
    }}

    public static Stage prepareStage() {{
        return new Stage("Prepare")
            .jobs(new Job("Prepare Job", "PREP")
{_requirements_chain(build, 4)}
                .tasks(new ScriptTask()
                    .fileFromPath(SCRIPT_ROOT + "/prepare_build.py")
                    .interpreterShell()));
    }}

    public static Stage buildStage() {{
        return new Stage("Build")
            .jobs(new Job("Build Job", "BLD")
{_requirements_chain(build, 4)}
                .tasks(new ScriptTask()
                    .fileFromPath(SCRIPT_ROOT + "/run_build.py")
                    .interpreterShell()));
    }}

    public static Stage staticAnalysisStage() {{
        return new Stage("Static Analysis")
            .jobs(
                new Job("Coverity Scan", "COV")
{_requirements_chain(build, 5)}
                    .tasks(new ScriptTask()
                        .fileFromPath(SCRIPT_ROOT + "/run_coverity.py")
                        .interpreterShell()),
                new Job("Custom Analysis", "CUST")
{_requirements_chain(build, 5)}
                    .tasks(new ScriptTask()
                        .fileFromPath(SCRIPT_ROOT + "/run_custom_analysis.py")
                        .interpreterShell())
            );
    }}

    public static Stage triggerFollowUpStage() {{
        return new Stage("Trigger Follow-up")
            .jobs(new Job("Trigger Job", "TRIG")
                .tasks(new ScriptTask()
                    .fileFromPath(SCRIPT_ROOT + "/trigger_follow_up.py")
                    .interpreterShell()));
    }}
}}
"""


def generate_coverity_yaml(build: BuildDefinition) -> str:
    coverity_language = _coverity_language(build.language)
    return (
        "capture:\n"
        "  build:\n"
        f'    build-command: "{_escape_yaml(build.build.build_command)}"\n'
        "  languages:\n"
        "    include:\n"
        f"      - {coverity_language}\n"
    )


def generate_registry_java(builds: list[BuildDefinition], package_name: str) -> str:
    class_names = [to_java_class_name(build.build_id) for build in builds]
    registry_lines = ",\n".join(f"            {name}.plan()" for name in class_names)

    return f"""package {package_name};

import java.util.List;
import com.atlassian.bamboo.specs.api.builders.plan.Plan;

// Sample generated registry for all plans in a single specs repository.
public final class AllPlansRegistry {{
    private AllPlansRegistry() {{
    }}

    public static List<Plan> plans() {{
        return List.of(
{registry_lines}
        );
    }}
}}
"""


def generate_python_scripts(build: BuildDefinition) -> dict[str, str]:
    custom_tool_commands = _render_custom_tool_commands(build)
    custom_tool_command_lines = ",\n        ".join(repr(command) for command in custom_tool_commands)

    return {
        "prepare_build.py": f"""#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    command = {build.build.prepare_command!r}
    return subprocess.run(parse_command(command), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
        "run_build.py": f"""#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    command = {build.build.build_command!r}
    return subprocess.run(parse_command(command), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
        "run_coverity.py": f"""#!/usr/bin/env python3
from __future__ import annotations

import subprocess


def main() -> int:
    command = ["coverity", "scan", "--config", "coverity/{build.build_id}/coverity.yaml"]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
        "run_custom_analysis.py": f"""#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess


COMMANDS = [
        {custom_tool_command_lines}
]


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    for command in COMMANDS:
        result = subprocess.run(parse_command(command), check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
        "trigger_follow_up.py": f"""#!/usr/bin/env python3
from __future__ import annotations

import subprocess


def main() -> int:
    command = ["trigger-plan", "{build.build.post_build_trigger.target_plan_key}"]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
    }


def _render_custom_tool_commands(build: BuildDefinition) -> list[str]:
    rendered: list[str] = []
    for command in build.build.static_analysis.custom_tool_commands:
        rendered.append(command.replace("{buildCommand}", build.build.build_command))
    return rendered


def _coverity_language(language: str) -> str:
    mapping = {
        "java": "java",
        "nodejs": "javascript",
        "node.js": "javascript",
        "javascript": "javascript",
        "python": "python",
    }
    return mapping.get(language.lower(), language.lower())


def _requirements_chain(build: BuildDefinition, indent_size: int) -> str:
    indent = " " * indent_size
    lines = [
        f'{indent}.requirements(Requirement.equals("operating.system", "{_normalize_os(build.requirements.os)}"))',
        f'{indent}.requirements(Requirement.exists("{_escape_java(_compiler_capability_key(build.compiler))}"))',
    ]
    for capability in build.requirements.extra_capabilities:
        lines.append(f'{indent}.requirements(Requirement.exists("{_escape_java(_extra_capability_key(capability))}"))')
    return "\n".join(lines)


def _normalize_os(value: str) -> str:
    mapping = {
        "windows": "Windows",
        "linux": "Linux",
    }
    return mapping.get(value.lower(), value)


def _compiler_capability_key(compiler: str) -> str:
    mapping = {
        "vs2013": "system.builder.visualstudio.2013",
        "vs2015": "system.builder.visualstudio.2015",
        "vs2017": "system.builder.visualstudio.2017",
        "vs2019": "system.builder.visualstudio.2019",
        "vs2022": "system.builder.visualstudio.2022",
        "vs2026": "system.builder.visualstudio.2026",
        "node.js": "system.builder.nodejs",
        "python": "system.builder.python",
        "maven": "system.builder.mvn3.Maven 3",
        "keil": "system.builder.keil",
        "cmake": "system.builder.cmake",
    }
    return mapping.get(compiler, compiler)


def _extra_capability_key(capability: str) -> str:
    mapping = {
        "cuda12.1": "system.cuda.12.1",
        "nuget": "system.builder.nuget",
    }
    return mapping.get(capability, capability)




def _project_key(year: str) -> str:
    return f"Y{year}"


def _escape_java(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
