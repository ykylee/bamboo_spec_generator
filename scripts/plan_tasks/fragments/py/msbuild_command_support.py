import os
from pathlib import Path
import shlex
import subprocess


WORKING_DIRECTORY = Path({{SUB_PATH}})


DIRECTORY_BUILD_TARGETS = """<Project>
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
"""


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def ensure_directory_build_targets() -> None:
    WORKING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (WORKING_DIRECTORY / "Directory.Build.targets").write_text(DIRECTORY_BUILD_TARGETS, encoding="utf-8")


def build_wrapped_command(command: str) -> list[str]:
    if os.name != "nt":
        return parse_command(command)

    env_var_name = {{COMPILER_ENV_VAR}}
    vcvars_path = os.environ.get(env_var_name)
    if not vcvars_path:
        raise RuntimeError(f"Missing required environment variable: {env_var_name}")
    return ["cmd.exe", "/d", "/s", "/c", f'call "{vcvars_path}" && {command}']


def run_command(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(build_wrapped_command(command), cwd=WORKING_DIRECTORY, check=False)
