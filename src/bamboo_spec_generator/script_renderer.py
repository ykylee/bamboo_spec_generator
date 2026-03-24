from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .coverity import generate_coverity_yaml
from .model import BuildDefinition
from .script_assets import load_python_script_assets


REPO_ROOT = Path(__file__).resolve().parents[2]


class ScriptRenderError(Exception):
    pass


@dataclass(frozen=True)
class ScriptRenderContext:
    replacements: dict[str, str]


def render_python_scripts(
    build: BuildDefinition,
    prepare_context: dict | None = None,
    coverity_config: str | None = None,
) -> dict[str, str]:
    assets = load_python_script_assets(build)
    context = ScriptRenderContext(
        replacements=_build_replacements(build, prepare_context=prepare_context, coverity_config=coverity_config)
    )
    return {script_name: _render_template(template, context.replacements) for script_name, template in assets.items()}


def render_python_launcher_scripts(
    build: BuildDefinition,
    prepare_context: dict | None = None,
    coverity_config: str | None = None,
) -> dict[str, str]:
    extension = _launcher_extension(build)
    replacements = {
        "{{PYTHON_COMMAND}}": _python_command(build),
    }
    rendered: dict[str, str] = {}
    for script_name in render_python_scripts(
        build,
        prepare_context=prepare_context,
        coverity_config=coverity_config,
    ):
        template = _read_launcher_template(build, script_name.removesuffix(".py"))
        launcher_name = script_name.removesuffix(".py") + extension
        rendered[launcher_name] = _render_template(
            template,
            {
                **replacements,
                "{{SCRIPT_NAME}}": script_name,
            },
        )
    return rendered


def get_python_launcher_asset_sources(build: BuildDefinition) -> dict[str, str]:
    extension = _launcher_extension(build)
    sources: dict[str, str] = {}
    for script_name in render_python_scripts(build):
        task_name = script_name.removesuffix(".py")
        launcher_name = task_name + extension
        sources[launcher_name] = str(_resolve_launcher_template_path(build, task_name).relative_to(REPO_ROOT))
    return sources


def _format_commands(commands: list[str]) -> str:
    return "\n".join(f"    {command!r}," for command in commands)


def _render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    missing = sorted({token for token in _find_placeholders(rendered)})
    if missing:
        joined = ", ".join(missing)
        raise ScriptRenderError(f"Unresolved script placeholders: {joined}")
    return rendered


def _find_placeholders(value: str) -> set[str]:
    placeholders: set[str] = set()
    start = 0
    while True:
        open_index = value.find("{{", start)
        if open_index == -1:
            return placeholders
        close_index = value.find("}}", open_index + 2)
        if close_index == -1:
            return placeholders
        placeholders.add(value[open_index : close_index + 2])
        start = close_index + 2


def _render_custom_tool_commands(build: BuildDefinition) -> list[str]:
    rendered: list[str] = []
    for command in build.build.static_analysis.custom_tool_commands:
        rendered.append(command.replace("{buildCommand}", build.build.build_command))
    return rendered


def _build_replacements(
    build: BuildDefinition,
    *,
    prepare_context: dict | None = None,
    coverity_config: str | None = None,
) -> dict[str, str]:
    return {
        "{{SUB_PATH}}": repr(build.build.sub_path),
        "{{PLAN_KEY}}": repr(build.plan_key),
        "{{BUILD_KEY}}": repr(build.build_key),
        "{{PREPARE_COMMAND}}": repr(build.build.prepare_command),
        "{{PREPARE_CONTEXT_EXPORTS}}": _prepare_context_exports(prepare_context),
        "{{BUILD_COMMAND}}": repr(build.build.build_command),
        "{{COVERITY_CONFIG}}": repr(coverity_config if coverity_config is not None else generate_coverity_yaml(build)),
        "{{CUSTOM_TOOL_COMMANDS}}": _format_commands(_render_custom_tool_commands(build)),
        "{{TARGET_PLAN_KEY}}": repr(build.build.post_build_trigger.target_plan_key),
        "{{COMPILER_ENV_VAR}}": repr(_compiler_env_var(build.compiler)),
    }


def _compiler_env_var(compiler: str) -> str:
    if compiler.startswith("vs"):
        return compiler.upper() + "_ENV"
    return "MSBUILD_ENV"


def _prepare_context_exports(prepare_context: dict | None) -> str:
    if not prepare_context:
        return "    pass"
    variables = prepare_context.get("variables", {})
    if not variables:
        return "    pass"
    lines = []
    for key, value in sorted(variables.items()):
        lines.append(f"    os.environ[{key!r}] = {str(value)!r}")
    return "\n".join(lines)


def _python_command(build: BuildDefinition) -> str:
    return "python" if build.requirements.os.lower() == "windows" else "python3"


def _launcher_extension(build: BuildDefinition) -> str:
    return ".bat" if build.requirements.os.lower() == "windows" else ".sh"


def _read_launcher_template(build: BuildDefinition, task_name: str) -> str:
    template_path = _resolve_launcher_template_path(build, task_name)
    return template_path.read_text(encoding="utf-8")


def _resolve_launcher_template_path(build: BuildDefinition, task_name: str) -> Path:
    os_name = build.requirements.os.lower()
    plan_tasks_root = Path(__file__).resolve().parents[2] / "scripts" / "plan_tasks"
    task_overlay_root = plan_tasks_root / "overlays" / "task" / task_name
    common_root = plan_tasks_root / "common"

    if os_name == "windows":
        template_path = task_overlay_root / "bat" / "python_task_launcher.bat"
        fallback_path = common_root / "bat" / "python_task_launcher.bat"
    else:
        template_path = task_overlay_root / "sh" / "python_task_launcher.sh"
        fallback_path = common_root / "sh" / "python_task_launcher.sh"

    if not template_path.is_file():
        template_path = fallback_path
    return template_path
