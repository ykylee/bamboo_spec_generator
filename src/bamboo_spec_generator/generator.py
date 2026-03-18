from __future__ import annotations

from .model import BuildDefinition

BAMBOO_SPECS_VERSION = "11.0.2"


def to_java_class_name(build_id: str) -> str:
    return "".join(part.capitalize() for part in build_id.replace("_", "-").split("-")) + "PlanSpecs"


def generate_plan_java(build: BuildDefinition, package_name: str) -> str:
    class_name = to_java_class_name(build.build_id)
    description = _escape_java(build.description or build.name)
    project_key = _project_key(build.year)
    linked_repository_name = _linked_repository_name(build)
    python_scripts = generate_python_scripts(build)
    python_command = _python_command(build)

    return f"""package {package_name};

import com.atlassian.bamboo.specs.api.BambooSpec;
import com.atlassian.bamboo.specs.api.builders.plan.Plan;
import com.atlassian.bamboo.specs.api.builders.plan.Job;
import com.atlassian.bamboo.specs.api.builders.plan.Stage;
import com.atlassian.bamboo.specs.api.builders.project.Project;
import com.atlassian.bamboo.specs.api.builders.requirement.Requirement;
import com.atlassian.bamboo.specs.builders.task.ScriptTask;
import com.atlassian.bamboo.specs.builders.task.VcsCheckoutTask;

@BambooSpec
public class {class_name} {{
    private static final String PROJECT_KEY = "{project_key}";
    private static final String PLAN_KEY = "{build.plan_key}";
    private static final String YEAR = "{build.year}";
    private static final String LINKED_REPOSITORY = "{linked_repository_name}";
    private static final String PYTHON_COMMAND = "{python_command}";
    private static final String SCRIPT_DIRECTORY = ".bamboo-specs";
    private static final String PREPARE_BUILD_SCRIPT = {_java_text_block(python_scripts["prepare_build.py"], 4)};
    private static final String RUN_BUILD_SCRIPT = {_java_text_block(python_scripts["run_build.py"], 4)};
    private static final String RUN_COVERITY_SCRIPT = {_java_text_block(python_scripts["run_coverity.py"], 4)};
    private static final String RUN_CUSTOM_ANALYSIS_SCRIPT = {_java_text_block(python_scripts["run_custom_analysis.py"], 4)};
    private static final String TRIGGER_FOLLOW_UP_SCRIPT = {_java_text_block(python_scripts["trigger_follow_up.py"], 4)};

    public Plan plan() {{
        return createPlan();
    }}

    public Plan createPlan() {{
        Project project = new Project()
            .key(PROJECT_KEY)
            .name("Generated Plans " + YEAR);

        return new Plan(project, "{description}", PLAN_KEY)
            .description("{description}")
            .linkedRepositories(LINKED_REPOSITORY)
            .stages(
                prepareStage(),
                buildStage(),
                staticAnalysisStage(),
                triggerFollowUpStage()
            );
    }}

    private Stage prepareStage() {{
        return new Stage("Prepare")
            .jobs(new Job("Prepare Job", "PREP")
{_requirements_chain(build, 4)}
                .tasks(
                    new VcsCheckoutTask().addCheckoutOfDefaultRepository(),
                    pythonScriptTask("prepare_build.py", PREPARE_BUILD_SCRIPT)
                ));
    }}

    private Stage buildStage() {{
        return new Stage("Build")
            .jobs(new Job("Build Job", "BLD")
{_requirements_chain(build, 4)}
                .tasks(
                    new VcsCheckoutTask().addCheckoutOfDefaultRepository(),
                    pythonScriptTask("run_build.py", RUN_BUILD_SCRIPT)
                ));
    }}

    private Stage staticAnalysisStage() {{
        return new Stage("Static Analysis")
            .jobs(
                new Job("Coverity Scan", "COV")
{_requirements_chain(build, 5)}
                    .tasks(
                        new VcsCheckoutTask().addCheckoutOfDefaultRepository(),
                        pythonScriptTask("run_coverity.py", RUN_COVERITY_SCRIPT)
                    ),
                new Job("Custom Analysis", "CUST")
{_requirements_chain(build, 5)}
                    .tasks(
                        new VcsCheckoutTask().addCheckoutOfDefaultRepository(),
                        pythonScriptTask("run_custom_analysis.py", RUN_CUSTOM_ANALYSIS_SCRIPT)
                    )
            );
    }}

    private Stage triggerFollowUpStage() {{
        return new Stage("Trigger Follow-up")
            .jobs(new Job("Trigger Job", "TRIG")
                .tasks(
                    pythonScriptTask("trigger_follow_up.py", TRIGGER_FOLLOW_UP_SCRIPT)
                ));
    }}

    private ScriptTask pythonScriptTask(String scriptName, String scriptBody) {{
        return new ScriptTask()
            .inlineBody(pythonWrapperCommand(scriptName, scriptBody))
            .interpreterShell();
    }}

{_python_wrapper_command_method(build)}
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
    registry_lines = ",\n".join(f"            new {name}().plan()" for name in class_names)

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


def generate_specs_publisher_java(package_name: str) -> str:
    return f"""package {package_name};

import com.atlassian.bamboo.specs.api.builders.plan.Plan;
import com.atlassian.bamboo.specs.util.BambooServer;
import com.atlassian.bamboo.specs.util.FileTokenCredentials;
import java.util.Arrays;
import java.util.List;

public final class SpecsPublisher {{
    private SpecsPublisher() {{
    }}

    public static void main(String[] args) {{
        List<Plan> plans = AllPlansRegistry.plans();
        if (Arrays.asList(args).contains("--print-plans")) {{
            for (Plan plan : plans) {{
                System.out.println(plan.toString());
            }}
            return;
        }}
        if (Arrays.asList(args).contains("--dry-run")) {{
            for (Plan plan : plans) {{
                System.out.println("DRY RUN: " + plan.toString());
            }}
            return;
        }}

        String bambooUrl = System.getenv("BAMBOO_URL");
        if (bambooUrl == null || bambooUrl.isBlank()) {{
            throw new IllegalStateException("BAMBOO_URL environment variable is required.");
        }}

        String credentialsFile = System.getenv().getOrDefault("BAMBOO_TOKEN_FILE", ".credentials");
        BambooServer server = new BambooServer(bambooUrl, new FileTokenCredentials(credentialsFile));
        for (Plan plan : plans) {{
            server.publish(plan);
        }}
    }}
}}
"""


def generate_pom_xml(package_name: str) -> str:
    package_path = package_name.replace(".", "/")
    return f"""<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>com.atlassian.bamboo</groupId>
    <artifactId>bamboo-specs-parent</artifactId>
    <version>{BAMBOO_SPECS_VERSION}</version>
  </parent>

  <groupId>com.example.specs</groupId>
  <artifactId>bamboo-specs</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>jar</packaging>
  <name>Generated Bamboo Specs</name>

  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <java.version>17</java.version>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <maven.compiler.release></maven.compiler.release>
    <generated.specs.package>{package_name}</generated.specs.package>
  </properties>

  <dependencies>
    <dependency>
      <groupId>com.atlassian.bamboo</groupId>
      <artifactId>bamboo-specs-api</artifactId>
    </dependency>
    <dependency>
      <groupId>com.atlassian.bamboo</groupId>
      <artifactId>bamboo-specs</artifactId>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        <artifactId>exec-maven-plugin</artifactId>
        <version>3.5.0</version>
        <configuration>
          <mainClass>{package_name}.SpecsPublisher</mainClass>
        </configuration>
      </plugin>
    </plugins>
    <resources>
      <resource>
        <directory>coverity</directory>
        <targetPath>coverity</targetPath>
      </resource>
    </resources>
  </build>
</project>
"""


def generate_python_scripts(build: BuildDefinition) -> dict[str, str]:
    custom_tool_commands = _render_custom_tool_commands(build)
    custom_tool_command_lines = ",\n        ".join(repr(command) for command in custom_tool_commands)
    prepare_build_script = _generate_prepare_build_script(build)
    run_build_script = _generate_run_build_script(build)
    coverity_config = generate_coverity_yaml(build)
    run_custom_analysis_script = _generate_run_custom_analysis_script(build, custom_tool_command_lines)

    return {
        "prepare_build.py": prepare_build_script,
        "run_build.py": run_build_script,
        "run_coverity.py": f"""#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile


WORKING_DIRECTORY = Path({build.build.sub_path!r})
CONFIG_CONTENT = {coverity_config!r}


def main() -> int:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False) as config_file:
        config_file.write(CONFIG_CONTENT)
        config_path = Path(config_file.name)

    try:
        command = ["coverity", "scan", "--config", str(config_path)]
        return subprocess.run(command, cwd=WORKING_DIRECTORY, check=False).returncode
    finally:
        if config_path.exists():
            config_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
""",
        "run_custom_analysis.py": run_custom_analysis_script,
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


def _generate_prepare_build_script(build: BuildDefinition) -> str:
    if not _uses_msbuild(build):
        return f"""#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess


WORKING_DIRECTORY = Path({build.build.sub_path!r})


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    command = {build.build.prepare_command!r}
    return subprocess.run(parse_command(command), cwd=WORKING_DIRECTORY, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
"""

    return f"""#!/usr/bin/env python3
from __future__ import annotations

{_msbuild_script_support(build)}


def main() -> int:
    command = {build.build.prepare_command!r}
    return run_command(command)


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _generate_run_build_script(build: BuildDefinition) -> str:
    if not _uses_msbuild(build):
        return f"""#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess


WORKING_DIRECTORY = Path({build.build.sub_path!r})


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    command = {build.build.build_command!r}
    return subprocess.run(parse_command(command), cwd=WORKING_DIRECTORY, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
"""

    return f"""#!/usr/bin/env python3
from __future__ import annotations

{_msbuild_script_support(build)}


def main() -> int:
    command = {build.build.build_command!r}
    ensure_directory_build_targets()
    return run_command(command)


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _generate_run_custom_analysis_script(build: BuildDefinition, custom_tool_command_lines: str) -> str:
    if not _uses_msbuild(build):
        return f"""#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess


WORKING_DIRECTORY = Path({build.build.sub_path!r})


COMMANDS = [
        {custom_tool_command_lines}
]


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    for command in COMMANDS:
        result = subprocess.run(parse_command(command), cwd=WORKING_DIRECTORY, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

    return f"""#!/usr/bin/env python3
from __future__ import annotations

{_msbuild_script_support(build)}


COMMANDS = [
        {custom_tool_command_lines}
]


def main() -> int:
    ensure_directory_build_targets()
    for command in COMMANDS:
        result = run_command(command)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _uses_msbuild(build: BuildDefinition) -> bool:
    return build.compiler.startswith("vs") or "--tool msbuild" in build.build.build_command


def _compiler_env_var(compiler: str) -> str:
    if compiler.startswith("vs"):
        return compiler.upper() + "_ENV"
    return "MSBUILD_ENV"


def _msbuild_script_support(build: BuildDefinition) -> str:
    env_var_name = _compiler_env_var(build.compiler)
    return f"""import os
from pathlib import Path
import shlex
import subprocess


WORKING_DIRECTORY = Path({build.build.sub_path!r})


DIRECTORY_BUILD_TARGETS = \"\"\"<Project>
  <PropertyGroup>
    <Optimization>Disabled</Optimization>
    <WholeProgramOptimization>false</WholeProgramOptimization>
    <LinkTimeCodeGeneration>Default</LinkTimeCodeGeneration>
  </PropertyGroup>
  <ItemDefinitionGroup>
    <ClCompile>
      <Optimization>Disabled</Optimization>
      <WholeProgramOptimization>false</WholeProgramOptimization>
    </ClCompile>
    <Link>
      <LinkTimeCodeGeneration>Default</LinkTimeCodeGeneration>
    </Link>
  </ItemDefinitionGroup>
</Project>
\"\"\"


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def ensure_directory_build_targets() -> None:
    WORKING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (WORKING_DIRECTORY / "Directory.Build.targets").write_text(DIRECTORY_BUILD_TARGETS, encoding="utf-8")


def build_wrapped_command(command: str) -> list[str]:
    if os.name != "nt":
        return parse_command(command)

    env_var_name = "{env_var_name}"
    vcvars_path = os.environ.get(env_var_name)
    if not vcvars_path:
        raise RuntimeError(f"Missing required environment variable: {{env_var_name}}")
    return ["cmd.exe", "/d", "/s", "/c", f'call "{{vcvars_path}}" && {{command}}']


def run_command(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(build_wrapped_command(command), cwd=WORKING_DIRECTORY, check=False)
"""


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
    lines = [f'{indent}.requirements(Requirement.equals("operating.system", "{_normalize_os(build.requirements.os)}"))']
    for capability in _required_capability_keys(build):
        lines.append(f'{indent}.requirements(Requirement.exists("{_escape_java(capability)}"))')
    return "\n".join(lines)


def _required_capability_keys(build: BuildDefinition) -> list[str]:
    capability_keys = [_compiler_capability_key(build.compiler)]
    capability_keys.extend(_extra_capability_key(capability) for capability in build.requirements.extra_capabilities)
    capability_keys.append(_runtime_python_capability_key())

    ordered_unique: list[str] = []
    for capability_key in capability_keys:
        if capability_key not in ordered_unique:
            ordered_unique.append(capability_key)
    return ordered_unique


def _runtime_python_capability_key() -> str:
    return "system.builder.python"


def _python_command(build: BuildDefinition) -> str:
    return "python" if build.requirements.os.lower() == "windows" else "python3"


def _python_wrapper_command_method(build: BuildDefinition) -> str:
    if build.requirements.os.lower() == "windows":
        return """    private String pythonWrapperCommand(String scriptName, String scriptBody) {
        return String.join("\\r\\n",
            "@echo off",
            "setlocal",
            "powershell -NoProfile -Command ^",
            "  \\"$scriptDir = '" + SCRIPT_DIRECTORY + "'; ^",
            "   if (-not (Test-Path $scriptDir)) { New-Item -ItemType Directory -Path $scriptDir | Out-Null }; ^",
            "   $path = Join-Path $scriptDir '" + scriptName + "'; ^",
            "   $script = @'",
            scriptBody,
            "'@; ^",
            "   Set-Content -Path $path -Value $script -Encoding UTF8; ^",
            "   & " + PYTHON_COMMAND + " $path; ^",
            "   exit $LASTEXITCODE\\"");
    }"""

    return """    private String pythonWrapperCommand(String scriptName, String scriptBody) {
        return String.join("\\n",
            "set -eu",
            "mkdir -p " + SCRIPT_DIRECTORY,
            "cat <<'__BAMBOO_SPEC_PY__' > " + SCRIPT_DIRECTORY + "/" + scriptName,
            scriptBody,
            "__BAMBOO_SPEC_PY__",
            PYTHON_COMMAND + " " + SCRIPT_DIRECTORY + "/" + scriptName);
    }"""


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
        "python": "system.builder.python",
    }
    return mapping.get(capability, capability)


def _linked_repository_name(build: BuildDefinition) -> str:
    return f"{build.repository.project_key}/{build.repository.repo_slug}"




def _project_key(year: str) -> str:
    return f"Y{year}"


def _escape_java(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _java_text_block(value: str, indent_size: int) -> str:
    indent = " " * indent_size
    escaped = value.replace('"""', '\\"""').rstrip("\n")
    return f'"""\n{escaped}\n{indent}"""'
