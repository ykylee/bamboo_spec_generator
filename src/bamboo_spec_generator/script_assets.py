from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from .model import BuildDefinition


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_TASKS_ROOT = Path(__file__).resolve().parents[2] / "scripts" / "plan_tasks"
COMMON_PY_ROOT = PLAN_TASKS_ROOT / "common" / "py"
FRAGMENTS_PY_ROOT = PLAN_TASKS_ROOT / "fragments" / "py"
MSBUILD_OVERLAY_PY_ROOT = PLAN_TASKS_ROOT / "overlays" / "compiler" / "msbuild" / "py"


class ScriptAssetError(Exception):
    pass


@dataclass(frozen=True)
class PythonScriptAsset:
    template: str
    command_support: str
    pre_run: str


def load_python_script_assets(build: BuildDefinition) -> dict[str, str]:
    rendered_assets: dict[str, str] = {}
    for script_name, task_name in _python_task_mapping().items():
        asset = _compose_python_asset(task_name, build)
        rendered_assets[script_name] = (
            asset.template.replace("{{COMMAND_SUPPORT}}", asset.command_support).replace("{{PRE_RUN}}", asset.pre_run)
        )
    return rendered_assets


def get_python_script_asset_sources(build: BuildDefinition) -> dict[str, dict[str, str | None]]:
    sources: dict[str, dict[str, str | None]] = {}
    for script_name, task_name in _python_task_mapping().items():
        template_path = COMMON_PY_ROOT / f"{task_name}.py"
        command_support_path: Path | None = None
        pre_run_path: Path | None = None

        if _uses_msbuild(build) and task_name in {"prepare_build", "run_build", "run_custom_analysis"}:
            command_support_path = FRAGMENTS_PY_ROOT / "msbuild_command_support.py"
            pre_run_path = MSBUILD_OVERLAY_PY_ROOT / f"{task_name}_pre_run.pyfrag"
        elif task_name in {"prepare_build", "run_build", "run_custom_analysis"}:
            command_support_path = FRAGMENTS_PY_ROOT / "basic_command_support.py"

        sources[script_name] = {
            "template": _relative_path(template_path),
            "commandSupport": _relative_path(command_support_path),
            "preRun": _relative_path(pre_run_path),
        }
    return sources


def _compose_python_asset(task_name: str, build: BuildDefinition) -> PythonScriptAsset:
    template = _read_asset(COMMON_PY_ROOT / f"{task_name}.py")
    if _uses_msbuild(build) and task_name in {"prepare_build", "run_build", "run_custom_analysis"}:
        command_support = _read_asset(FRAGMENTS_PY_ROOT / "msbuild_command_support.py")
        pre_run = _read_asset(MSBUILD_OVERLAY_PY_ROOT / f"{task_name}_pre_run.pyfrag")
    elif task_name in {"prepare_build", "run_build", "run_custom_analysis"}:
        command_support = _read_asset(FRAGMENTS_PY_ROOT / "basic_command_support.py")
        pre_run = ""
    else:
        command_support = ""
        pre_run = ""
    return PythonScriptAsset(template=template, command_support=command_support, pre_run=pre_run)


def _read_asset(asset_path: Path) -> str:
    if not asset_path.is_file():
        raise ScriptAssetError(f"Missing script asset: {asset_path}")
    return asset_path.read_text(encoding="utf-8")


def _python_task_mapping() -> dict[str, str]:
    return {
        "prepare_build.py": "prepare_build",
        "run_build.py": "run_build",
        "run_coverity.py": "run_coverity",
        "run_custom_analysis.py": "run_custom_analysis",
        "trigger_follow_up.py": "trigger_follow_up",
    }


def _relative_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(REPO_ROOT))


def _uses_msbuild(build: BuildDefinition) -> bool:
    return build.compiler.startswith("vs") or "--tool msbuild" in build.build.build_command
