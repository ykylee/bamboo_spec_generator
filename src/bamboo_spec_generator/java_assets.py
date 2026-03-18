from __future__ import annotations

from pathlib import Path

from .model import BuildDefinition


PLAN_TASKS_ROOT = Path(__file__).resolve().parents[2] / "scripts" / "plan_tasks"
JAVA_WRAPPER_ROOTS = {
    "windows": PLAN_TASKS_ROOT / "common" / "bat",
    "linux": PLAN_TASKS_ROOT / "common" / "sh",
}


class JavaAssetError(Exception):
    pass


def load_python_wrapper_method(build: BuildDefinition) -> str:
    os_name = build.requirements.os.lower()
    root = JAVA_WRAPPER_ROOTS.get(os_name)
    if root is None:
        raise JavaAssetError(f"Unsupported OS for python wrapper asset: {build.requirements.os}")

    asset_path = root / "python_wrapper_method.javafrag"
    if not asset_path.is_file():
        raise JavaAssetError(f"Missing Java wrapper asset: {asset_path}")
    return asset_path.read_text(encoding="utf-8")
