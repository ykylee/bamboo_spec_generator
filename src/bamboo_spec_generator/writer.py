from __future__ import annotations

from pathlib import Path

from .generator import (
    generate_coverity_yaml,
    generate_pom_xml,
    generate_plan_java,
    generate_python_scripts,
    generate_registry_java,
    generate_specs_publisher_java,
    to_java_class_name,
)
from .model import BuildDefinition


PACKAGE_NAME = "com.example.specs.generated"


def write_specs_project(output_root: Path, builds: list[BuildDefinition]) -> list[Path]:
    java_root = output_root / "src" / "main" / "java" / "com" / "example" / "specs" / "generated"
    java_root.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []

    pom_path = output_root / "pom.xml"
    pom_path.write_text(generate_pom_xml(PACKAGE_NAME), encoding="utf-8")
    written_files.append(pom_path)

    readme_path = output_root / "README.md"
    readme_path.write_text(
        "# Generated Bamboo Specs Project\n\n"
        "이 디렉터리는 Bamboo Repository Stored Specs 또는 Java Specs 배포용으로 사용할 수 있는 Maven 프로젝트입니다.\n"
        "루트 `pom.xml`은 `com.atlassian.bamboo:bamboo-specs-parent`를 상속합니다.\n"
        "생성된 Java Specs 클래스는 `@BambooSpec`를 사용하며, `src/main/java/` 아래에 위치합니다.\n"
        "각 빌드별 Coverity 설정 파일은 `coverity/<buildId>/coverity.yaml` 아래에 생성됩니다.\n"
        "각 빌드별 Python 실행 스크립트는 `scripts/generated/<buildId>/` 아래에 생성됩니다.\n\n"
        "## 사용 방법\n\n"
        "1. Bamboo 서버 버전에 맞게 `pom.xml`의 Bamboo Specs 부모 버전을 조정합니다.\n"
        "2. Bamboo Linked Repository 이름이 `projectKey/repoSlug` 규칙과 일치하도록 Bamboo 쪽 구성을 준비합니다.\n"
        "3. Repository Stored Specs로 사용할 경우 이 디렉터리를 Bamboo가 읽는 저장소 루트의 `bamboo-specs/`로 배치합니다.\n"
        "4. 로컬에서 수동 배포하려면 `BAMBOO_URL`과 `BAMBOO_TOKEN_FILE`을 설정한 뒤 `mvn exec:java`를 사용합니다.\n",
        encoding="utf-8",
    )
    written_files.append(readme_path)

    registry_path = java_root / "AllPlansRegistry.java"
    registry_path.write_text(generate_registry_java(builds, PACKAGE_NAME), encoding="utf-8")
    written_files.append(registry_path)

    publisher_path = java_root / "SpecsPublisher.java"
    publisher_path.write_text(generate_specs_publisher_java(PACKAGE_NAME), encoding="utf-8")
    written_files.append(publisher_path)

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
