from __future__ import annotations

from pathlib import Path

from .generator import (
    generate_coverity_yaml,
    generate_plan_java,
    generate_python_scripts,
    generate_registry_java,
    to_java_class_name,
)
from .model import BuildDefinition


PACKAGE_NAME = "com.example.specs.generated"


def write_specs_project(output_root: Path, builds: list[BuildDefinition]) -> list[Path]:
    java_root = output_root / "src" / "main" / "java" / "com" / "example" / "specs" / "generated"
    java_root.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []

    readme_path = output_root / "README.md"
    readme_path.write_text(
        "# Generated Bamboo Specs Sample\n\n"
        "이 디렉터리는 샘플 생성기가 만든 Bamboo Specs Java 예제 프로젝트입니다.\n"
        "각 빌드별 Coverity 설정 파일은 `coverity/<buildId>/coverity.yaml` 아래에 생성됩니다.\n"
        "각 빌드별 Python 실행 스크립트는 `scripts/generated/<buildId>/` 아래에 생성됩니다.\n",
        encoding="utf-8",
    )
    written_files.append(readme_path)

    registry_path = java_root / "AllPlansRegistry.java"
    registry_path.write_text(generate_registry_java(builds, PACKAGE_NAME), encoding="utf-8")
    written_files.append(registry_path)

    for build in builds:
        class_name = to_java_class_name(build.build_id)
        output_path = java_root / f"{class_name}.java"
        output_path.write_text(generate_plan_java(build, PACKAGE_NAME), encoding="utf-8")
        written_files.append(output_path)

        coverity_root = output_root / "coverity" / build.build_id
        coverity_root.mkdir(parents=True, exist_ok=True)
        coverity_path = coverity_root / "coverity.yaml"
        coverity_path.write_text(generate_coverity_yaml(build), encoding="utf-8")
        written_files.append(coverity_path)

        scripts_root = output_root / "scripts" / "generated" / build.build_id
        scripts_root.mkdir(parents=True, exist_ok=True)
        for script_name, script_body in generate_python_scripts(build).items():
            script_path = scripts_root / script_name
            script_path.write_text(script_body, encoding="utf-8")
            written_files.append(script_path)

    return written_files
