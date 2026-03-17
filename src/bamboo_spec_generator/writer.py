from __future__ import annotations

from pathlib import Path

from .generator import (
    generate_coverity_yaml,
    generate_pom_xml,
    generate_plan_java,
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

    runtime_sections: list[str] = []
    for build in builds:
        runtime_sections.append(
            f"### {build.build_id}\n\n"
            f"- 필수 명령: {', '.join(build.build.runtime_requirements.commands)}\n"
            f"- 필수 환경변수: {', '.join(build.build.runtime_requirements.env_vars)}\n"
        )

    readme_path = output_root / "README.md"
    readme_path.write_text(
        "# Generated Bamboo Specs Project\n\n"
        "이 디렉터리는 Bamboo Repository Stored Specs 또는 Java Specs 배포용으로 사용할 수 있는 Maven 프로젝트입니다.\n"
        "루트 `pom.xml`은 `com.atlassian.bamboo:bamboo-specs-parent`를 상속합니다.\n"
        "생성된 Java Specs 클래스는 `@BambooSpec`를 사용하며, `src/main/java/` 아래에 위치합니다.\n"
        "각 빌드별 Coverity 설정 파일은 `coverity/<buildId>/coverity.yaml` 아래에 생성됩니다.\n"
        "각 Task의 실행 로직은 Bamboo `ScriptTask`의 inline body에 직접 포함됩니다.\n\n"
        "## 사전 점검\n\n"
        "- Bamboo 서버 버전과 `pom.xml`의 Bamboo Specs 버전이 호환되어야 합니다.\n"
        "- Bamboo Linked Repository 이름이 `projectKey/repoSlug` 규칙과 일치해야 합니다.\n"
        "- 에이전트에 Python capability(`system.builder.python`)가 등록되어 있어야 합니다.\n"
        "- 각 플랜의 원본 명령이 호출하는 도구(`mvn`, `npm`, `nuget`, `msbuild`)가 에이전트에 있어야 합니다.\n"
        "- 정적 분석 단계용 `coverity`, `custom-tool` 명령과 후속 단계용 `trigger-plan` 명령이 에이전트에 있어야 합니다.\n"
        "- Windows MSBuild 플랜은 `VS2022_ENV` 같은 환경변수로 Visual Studio 환경 스크립트 경로가 설정되어야 합니다.\n\n"
        "## 빌드별 런타임 요구사항\n\n"
        + "\n".join(runtime_sections)
        + "\n\n"
        "## 사용 방법\n\n"
        "1. Bamboo 서버 버전에 맞게 `pom.xml`의 Bamboo Specs 부모 버전을 조정합니다.\n"
        "2. Bamboo Linked Repository 이름이 `projectKey/repoSlug` 규칙과 일치하도록 Bamboo 쪽 구성을 준비합니다.\n"
        "3. Repository Stored Specs로 사용할 경우 이 디렉터리를 Bamboo가 읽는 저장소 루트의 `bamboo-specs/`로 배치합니다.\n"
        "4. publish 전에는 `mvn -q exec:java -Dexec.args=\"--dry-run\"`으로 계획을 점검합니다.\n"
        "5. 플랜 목록만 보려면 `mvn -q exec:java -Dexec.args=\"--print-plans\"`를 사용합니다.\n"
        "6. 실제 배포 시에는 `BAMBOO_URL`과 `BAMBOO_TOKEN_FILE`을 설정한 뒤 `mvn -q exec:java`를 사용합니다.\n",
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

    return written_files
