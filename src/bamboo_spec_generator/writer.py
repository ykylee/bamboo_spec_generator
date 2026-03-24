from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .generator import (
    generate_coverity_yaml,
    generate_pom_xml,
    generate_plan_java,
    generate_plan_java_for_builds,
    generate_registry_java,
    generate_specs_publisher_java,
    to_java_class_name,
)
from .model import BuildDefinition
from .script_assets import get_python_script_asset_sources
from .script_renderer import (
    get_python_launcher_asset_sources,
    render_python_launcher_scripts,
    render_python_scripts,
)


PACKAGE_NAME = "com.example.specs.generated"


def write_specs_project(
    output_root: Path,
    builds: list[BuildDefinition],
    prepare_contexts: dict[str, dict] | None = None,
) -> list[Path]:
    java_root = output_root / "src" / "main" / "java" / "com" / "example" / "specs" / "generated"
    java_root.mkdir(parents=True, exist_ok=True)
    scripts_index_entries: list[dict[str, str]] = []
    repository_link_entries: list[dict[str, Any]] = []
    generated_at_utc = _generated_at_utc()
    source_revision = _source_revision()
    previous_bundles = _load_previous_bundles(output_root / "scripts")

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
        "각 빌드별 렌더링된 Python Task 스크립트와 실행 보조 자산은 `scripts/<bundleId>/` 아래에 기록됩니다.\n"
        "저장소 연결 모드와 브랜치 정책은 `repository-links.json` 및 각 번들의 `manifest.json`에 함께 기록됩니다.\n"
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
        "3. `repository-links.json`에서 각 플랜의 `linkageMode`, 브랜치 정책, 후속 등록 필요 여부를 확인합니다.\n"
        "4. `scripts/<bundleId>/`에 기록된 최종 스크립트와 OS별 launcher로 생성 내용을 검토할 수 있습니다.\n"
        "5. Repository Stored Specs로 사용할 경우 이 디렉터리를 Bamboo가 읽는 저장소 루트의 `bamboo-specs/`로 배치합니다.\n"
        "6. publish 전에는 `mvn -q exec:java -Dexec.args=\"--dry-run\"`으로 계획을 점검합니다.\n"
        "7. 플랜 목록만 보려면 `mvn -q exec:java -Dexec.args=\"--print-plans\"`를 사용합니다.\n"
        "8. `pom.xml`에는 Bamboo Specs 종료 스레드와 `exec-maven-plugin` 충돌을 피하기 위해 `cleanupDaemonThreads=false`가 기본 설정됩니다.\n"
        "9. 실제 배포 시에는 `BAMBOO_URL`과 `BAMBOO_TOKEN_FILE`을 설정한 뒤 `mvn -q exec:java`를 사용합니다.\n",
        encoding="utf-8",
    )
    written_files.append(readme_path)

    registry_path = java_root / "AllPlansRegistry.java"
    registry_path.write_text(generate_registry_java(builds, PACKAGE_NAME), encoding="utf-8")
    written_files.append(registry_path)

    publisher_path = java_root / "SpecsPublisher.java"
    publisher_path.write_text(generate_specs_publisher_java(PACKAGE_NAME), encoding="utf-8")
    written_files.append(publisher_path)

    builds_by_plan_key: dict[str, list[BuildDefinition]] = {}
    for build in builds:
        builds_by_plan_key.setdefault(build.plan_key, []).append(build)

    for plan_builds in builds_by_plan_key.values():
        representative_build = plan_builds[0]
        class_name = to_java_class_name(representative_build.build_id)
        output_path = java_root / f"{class_name}.java"
        if len(plan_builds) == 1:
            output_path.write_text(generate_plan_java(representative_build, PACKAGE_NAME), encoding="utf-8")
        else:
            output_path.write_text(generate_plan_java_for_builds(plan_builds, PACKAGE_NAME), encoding="utf-8")
        written_files.append(output_path)

    for build in builds:
        scripts_root = output_root / "scripts" / build.build_id
        if build.build_key:
            scripts_root = output_root / "scripts" / f"{build.build_id}-{build.build_key}"
        scripts_root.mkdir(parents=True, exist_ok=True)
        prepare_context = (prepare_contexts or {}).get(build.plan_key)
        python_scripts = render_python_scripts(build, prepare_context=prepare_context)
        launcher_scripts = render_python_launcher_scripts(build, prepare_context=prepare_context)

        for script_name, script_body in python_scripts.items():
            script_path = scripts_root / script_name
            script_path.write_text(script_body, encoding="utf-8")
            written_files.append(script_path)
        for script_name, script_body in launcher_scripts.items():
            script_path = scripts_root / script_name
            script_path.write_text(script_body, encoding="utf-8")
            written_files.append(script_path)
        bundle_readme_path = scripts_root / "README.md"
        bundle_readme_path.write_text(_generate_scripts_bundle_readme(build, python_scripts, launcher_scripts), encoding="utf-8")
        written_files.append(bundle_readme_path)
        if prepare_context:
            prepare_context_path = scripts_root / "prepare-context.json"
            prepare_context_path.write_text(json.dumps(prepare_context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            written_files.append(prepare_context_path)
        manifest_path = scripts_root / "manifest.json"
        manifest_text = _generate_scripts_bundle_manifest(
            build,
            python_scripts,
            launcher_scripts,
            generated_at_utc,
            source_revision,
            prepare_context,
        )
        manifest_path.write_text(manifest_text, encoding="utf-8")
        written_files.append(manifest_path)
        summary_path = scripts_root / "bundle-summary.txt"
        summary_path.write_text(_generate_scripts_bundle_summary(build, manifest_text), encoding="utf-8")
        written_files.append(summary_path)
        scripts_index_entries.append(_build_scripts_index_entry(build, manifest_text))
        repository_link_entries.append(_build_repository_link_entry(build))

        coverity_root = output_root / "coverity" / build.build_id
        coverity_root.mkdir(parents=True, exist_ok=True)
        coverity_path = coverity_root / "coverity.yaml"
        coverity_path.write_text(generate_coverity_yaml(build), encoding="utf-8")
        written_files.append(coverity_path)

    repository_links_path = output_root / "repository-links.json"
    repository_links_text = _generate_repository_links(repository_link_entries)
    repository_links_path.write_text(repository_links_text, encoding="utf-8")
    written_files.append(repository_links_path)
    repository_links_summary_path = output_root / "repository-links-summary.txt"
    repository_links_summary_path.write_text(
        _generate_repository_links_summary(repository_links_text),
        encoding="utf-8",
    )
    written_files.append(repository_links_summary_path)

    scripts_root = output_root / "scripts"
    index_path = scripts_root / "index.json"
    index_text = _generate_scripts_index(scripts_index_entries, generated_at_utc, source_revision)
    index_path.write_text(index_text, encoding="utf-8")
    written_files.append(index_path)
    index_summary_path = scripts_root / "index-summary.txt"
    index_summary_path.write_text(_generate_scripts_index_summary(index_text), encoding="utf-8")
    written_files.append(index_summary_path)
    compare_report_path = scripts_root / "compare-report.txt"
    compare_report_json = _build_compare_report(previous_bundles, scripts_root, index_text)
    compare_report_path.write_text(_format_compare_report_text(compare_report_json), encoding="utf-8")
    written_files.append(compare_report_path)
    compare_report_json_path = scripts_root / "compare-report.json"
    compare_report_json_path.write_text(json.dumps(compare_report_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written_files.append(compare_report_json_path)

    return written_files


def _generate_scripts_bundle_readme(
    build: BuildDefinition,
    python_scripts: dict[str, str],
    launcher_scripts: dict[str, str],
) -> str:
    launcher_extension = ".bat" if build.requirements.os.lower() == "windows" else ".sh"
    task_lines: list[str] = []
    for script_name in python_scripts:
        launcher_name = script_name.removesuffix(".py") + launcher_extension
        task_label = script_name.removesuffix(".py")
        task_lines.append(
            f"- `{task_label}`: Python `{script_name}`, launcher `{launcher_name}`"
        )

    runtime_commands = ", ".join(build.build.runtime_requirements.commands)
    runtime_env_vars = ", ".join(build.build.runtime_requirements.env_vars)

    return (
        f"# Script Bundle: {build.build_id}\n\n"
        "이 디렉터리는 생성 시점에 렌더링된 Task 스크립트와 실행 보조 자산을 담습니다.\n\n"
        "## 실행 환경\n\n"
        f"- OS: {build.requirements.os}\n"
        f"- Compiler: {build.compiler}\n"
        f"- Python command: {'python' if build.requirements.os.lower() == 'windows' else 'python3'}\n"
        f"- Working subPath: `{build.build.sub_path}`\n\n"
        "## 저장소 연결\n\n"
        f"- Provider: {build.repository.provider}\n"
        f"- Project key: {build.repository.project_key}\n"
        f"- Repo slug: {build.repository.repo_slug}\n"
        f"- Linked repository name: `{build.repository.project_key}/{build.repository.repo_slug}`\n"
        f"- Linkage mode: `{build.repository.linkage_mode}`\n"
        f"- Bamboo application link: `{_repository_application_link(build)}`\n"
        f"- Branches: {', '.join(build.repository.branches)}\n"
        f"- Branch trigger policy: {_format_branch_trigger_policy_text(build.repository.branches)}\n"
        f"- Branch matching pattern: `{_branch_matching_pattern(build.repository.branches)}`\n"
        f"- Additional registration required: {'yes' if build.repository.linkage_mode == 'create_if_missing' else 'no'}\n\n"
        "## Task 파일 매핑\n\n"
        + "\n".join(task_lines)
        + "\n\n"
        "## 런타임 요구사항\n\n"
        f"- 필수 명령: {runtime_commands}\n"
        f"- 필수 환경변수: {runtime_env_vars}\n\n"
        "## 사용 메모\n\n"
        "- Bamboo 실행 시 실제 Task 본문은 Java Specs의 inline body에 포함됩니다.\n"
        "- 이 디렉터리의 파일은 생성 결과 검토, 디버깅, 차이 비교용 산출물입니다.\n"
        f"- OS 기준 launcher 확장자는 `{launcher_extension}` 입니다.\n"
    )


def _generate_scripts_bundle_manifest(
    build: BuildDefinition,
    python_scripts: dict[str, str],
    launcher_scripts: dict[str, str],
    generated_at_utc: str,
    source_revision: str,
    prepare_context: dict | None,
) -> str:
    launcher_extension = ".bat" if build.requirements.os.lower() == "windows" else ".sh"
    python_asset_sources = get_python_script_asset_sources(build)
    launcher_asset_sources = get_python_launcher_asset_sources(build)
    tasks = []
    for script_name in python_scripts:
        task_name = script_name.removesuffix(".py")
        launcher_name = task_name + launcher_extension
        tasks.append(
            {
                "taskName": task_name,
                "pythonScript": script_name,
                "launcherScript": launcher_name,
                "assetSources": {
                    "pythonScript": python_asset_sources[script_name],
                    "launcherScript": launcher_asset_sources[launcher_name],
                },
                "checksums": {
                    "pythonScriptSha256": _sha256_text(python_scripts[script_name]),
                    "launcherScriptSha256": _sha256_text(launcher_scripts[launcher_name]),
                },
            }
        )

    payload = {
        "buildId": build.build_id,
        "planKey": build.plan_key,
        "generatedAtUtc": generated_at_utc,
        "generatorVersion": __version__,
        "sourceRevision": source_revision,
        "os": build.requirements.os,
        "compiler": build.compiler,
        "pythonCommand": "python" if build.requirements.os.lower() == "windows" else "python3",
        "workingSubPath": build.build.sub_path,
        "runtimeRequirements": {
            "commands": build.build.runtime_requirements.commands,
            "envVars": build.build.runtime_requirements.env_vars,
        },
        "repository": _build_repository_link_entry(build),
        "prepareContext": prepare_context or {"variables": {}},
        "tasks": tasks,
    }
    payload["bundleContentSha256"] = _sha256_text(
        json.dumps(
            {
                "buildId": payload["buildId"],
                "planKey": payload["planKey"],
                "os": payload["os"],
                "compiler": payload["compiler"],
                "pythonCommand": payload["pythonCommand"],
                "workingSubPath": payload["workingSubPath"],
                "runtimeRequirements": payload["runtimeRequirements"],
                "repository": payload["repository"],
                "prepareContext": payload["prepareContext"],
                "tasks": payload["tasks"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    payload["bundleSha256"] = _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_scripts_bundle_summary(build: BuildDefinition, manifest_text: str) -> str:
    manifest = json.loads(manifest_text)
    lines = [
        f"buildId={manifest['buildId']}",
        f"planKey={manifest['planKey']}",
        f"generatedAtUtc={manifest['generatedAtUtc']}",
        f"generatorVersion={manifest['generatorVersion']}",
        f"sourceRevision={manifest['sourceRevision']}",
        f"os={manifest['os']}",
        f"compiler={manifest['compiler']}",
        f"pythonCommand={manifest['pythonCommand']}",
        f"workingSubPath={manifest['workingSubPath']}",
        f"bundleContentSha256={manifest['bundleContentSha256']}",
        f"bundleSha256={manifest['bundleSha256']}",
        f"runtime.commands={','.join(manifest['runtimeRequirements']['commands'])}",
        f"runtime.envVars={','.join(manifest['runtimeRequirements']['envVars'])}",
        f"repository.provider={manifest['repository']['provider']}",
        f"repository.projectKey={manifest['repository']['projectKey']}",
        f"repository.repoSlug={manifest['repository']['repoSlug']}",
        f"repository.linkedRepositoryName={manifest['repository']['linkedRepositoryName']}",
        f"repository.linkageMode={manifest['repository']['linkageMode']}",
        f"repository.applicationLink={manifest['repository']['applicationLink']}",
        f"repository.cloneUrl={manifest['repository'].get('cloneUrl', '')}",
        f"repository.branches={','.join(manifest['repository']['branches'])}",
        f"repository.branchTriggerPolicy={','.join(_format_branch_trigger_policy_entries(manifest['repository']['branches']))}",
        f"repository.branchMatchingPattern={manifest['repository']['branchMatchingPattern']}",
        f"repository.requiresRegistration={str(manifest['repository']['requiresRepositoryRegistration']).lower()}",
        f"prepareContext.variables={','.join(sorted(manifest['prepareContext'].get('variables', {}).keys()))}",
    ]

    for task in manifest["tasks"]:
        task_name = task["taskName"]
        lines.extend(
            [
                f"task.{task_name}.pythonScript={task['pythonScript']}",
                f"task.{task_name}.launcherScript={task['launcherScript']}",
                f"task.{task_name}.source.template={task['assetSources']['pythonScript']['template']}",
                f"task.{task_name}.source.commandSupport={task['assetSources']['pythonScript']['commandSupport'] or ''}",
                f"task.{task_name}.source.preRun={task['assetSources']['pythonScript']['preRun'] or ''}",
                f"task.{task_name}.source.launcher={task['assetSources']['launcherScript']}",
                f"task.{task_name}.sha256.python={task['checksums']['pythonScriptSha256']}",
                f"task.{task_name}.sha256.launcher={task['checksums']['launcherScriptSha256']}",
            ]
        )

    return "\n".join(lines) + "\n"


def _build_scripts_index_entry(build: BuildDefinition, manifest_text: str) -> dict[str, str]:
    manifest = json.loads(manifest_text)
    return {
        "buildId": build.build_id,
        "planKey": build.plan_key,
        "generatedAtUtc": manifest["generatedAtUtc"],
        "generatorVersion": manifest["generatorVersion"],
        "sourceRevision": manifest["sourceRevision"],
        "os": build.requirements.os,
        "compiler": build.compiler,
        "linkageMode": manifest["repository"]["linkageMode"],
        "bundlePath": f"scripts/{build.build_id}",
        "bundleManifest": f"scripts/{build.build_id}/manifest.json",
        "bundleSummary": f"scripts/{build.build_id}/bundle-summary.txt",
        "bundleContentSha256": manifest["bundleContentSha256"],
        "bundleSha256": manifest["bundleSha256"],
    }


def _generate_scripts_index(entries: list[dict[str, str]], generated_at_utc: str, source_revision: str) -> str:
    ordered_entries = sorted(entries, key=lambda entry: entry["buildId"])
    payload = {
        "generatedAtUtc": generated_at_utc,
        "generatorVersion": __version__,
        "sourceRevision": source_revision,
        "bundles": ordered_entries,
    }
    payload["indexSha256"] = _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _generate_scripts_index_summary(index_text: str) -> str:
    index = json.loads(index_text)
    lines = [
        f"generatedAtUtc={index['generatedAtUtc']}",
        f"generatorVersion={index['generatorVersion']}",
        f"sourceRevision={index['sourceRevision']}",
        f"indexSha256={index['indexSha256']}",
    ]
    for bundle in index["bundles"]:
        build_id = bundle["buildId"]
        lines.extend(
            [
                f"bundle.{build_id}.planKey={bundle['planKey']}",
                f"bundle.{build_id}.generatedAtUtc={bundle['generatedAtUtc']}",
                f"bundle.{build_id}.generatorVersion={bundle['generatorVersion']}",
                f"bundle.{build_id}.sourceRevision={bundle['sourceRevision']}",
                f"bundle.{build_id}.os={bundle['os']}",
                f"bundle.{build_id}.compiler={bundle['compiler']}",
                f"bundle.{build_id}.linkageMode={bundle['linkageMode']}",
                f"bundle.{build_id}.path={bundle['bundlePath']}",
                f"bundle.{build_id}.manifest={bundle['bundleManifest']}",
                f"bundle.{build_id}.summary={bundle['bundleSummary']}",
                f"bundle.{build_id}.contentSha256={bundle['bundleContentSha256']}",
                f"bundle.{build_id}.sha256={bundle['bundleSha256']}",
            ]
        )
    return "\n".join(lines) + "\n"


def _generated_at_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_repository_link_entry(build: BuildDefinition) -> dict[str, Any]:
    return {
        "buildId": build.build_id,
        "planKey": build.plan_key,
        "provider": build.repository.provider,
        "projectKey": build.repository.project_key,
        "repoSlug": build.repository.repo_slug,
        "linkedRepositoryName": f"{build.repository.project_key}/{build.repository.repo_slug}",
        "linkageMode": build.repository.linkage_mode,
        "applicationLink": _repository_application_link(build),
        "cloneUrl": build.repository.clone_url or "",
        "branches": list(build.repository.branches),
        "branchTriggerPolicy": [
            {
                "branch": branch,
                "order": index,
                "enabled": True,
            }
            for index, branch in enumerate(build.repository.branches, start=1)
        ],
        "branchMatchingPattern": _branch_matching_pattern(build.repository.branches),
        "requiresRepositoryRegistration": build.repository.linkage_mode == "create_if_missing",
    }


def _generate_repository_links(entries: list[dict[str, Any]]) -> str:
    payload = {"entries": sorted(entries, key=lambda entry: entry["buildId"])}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _generate_repository_links_summary(repository_links_text: str) -> str:
    repository_links = json.loads(repository_links_text)
    lines: list[str] = []
    for entry in repository_links["entries"]:
        build_id = entry["buildId"]
        lines.extend(
            [
                f"buildId={build_id}",
                f"planKey={entry['planKey']}",
                f"repository.provider={entry['provider']}",
                f"repository.projectKey={entry['projectKey']}",
                f"repository.repoSlug={entry['repoSlug']}",
                f"repository.linkedRepositoryName={entry['linkedRepositoryName']}",
                f"repository.linkageMode={entry['linkageMode']}",
                f"repository.applicationLink={entry['applicationLink']}",
                f"repository.cloneUrl={entry.get('cloneUrl', '')}",
                f"repository.branches={','.join(entry['branches'])}",
                f"repository.branchTriggerPolicy={','.join(_format_branch_trigger_policy_entries(entry['branches']))}",
                f"repository.branchMatchingPattern={entry['branchMatchingPattern']}",
                f"repository.requiresRegistration={str(entry['requiresRepositoryRegistration']).lower()}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _format_branch_trigger_policy_entries(branches: list[str]) -> list[str]:
    return [f"{branch}:{index}:enabled" for index, branch in enumerate(branches, start=1)]


def _format_branch_trigger_policy_text(branches: list[str]) -> str:
    return ", ".join(
        f"{branch}(order={index}, enabled=true)"
        for index, branch in enumerate(branches, start=1)
    )


def _branch_matching_pattern(branches: list[str]) -> str:
    escaped = [branch.replace("\\", "\\\\").replace("|", "\\|") for branch in branches]
    return "^(" + "|".join(escaped) + ")$"


def _repository_application_link(build: BuildDefinition) -> str:
    if build.repository.application_link and build.repository.application_link.strip():
        return build.repository.application_link
    return "BITBUCKET_SERVER"


def _source_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[2],
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _load_previous_bundles(scripts_root: Path) -> dict[str, dict[str, Any]]:
    index_path = scripts_root / "index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        bundles: dict[str, dict[str, Any]] = {}
        for bundle in index.get("bundles", []):
            bundles[bundle["buildId"]] = {
                **bundle,
                "manifestData": _load_manifest_data(scripts_root.parent / bundle["bundleManifest"]),
            }
        return bundles

    bundles: dict[str, dict[str, Any]] = {}
    if not scripts_root.exists():
        return bundles
    for manifest_path in sorted(scripts_root.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        bundles[manifest["buildId"]] = {
            "buildId": manifest["buildId"],
            "bundleManifest": str(manifest_path.relative_to(scripts_root.parent)),
            "bundleSummary": str((manifest_path.parent / "bundle-summary.txt").relative_to(scripts_root.parent)),
            "bundlePath": str(manifest_path.parent.relative_to(scripts_root.parent)),
            "bundleContentSha256": manifest.get("bundleContentSha256", ""),
            "bundleSha256": manifest.get("bundleSha256", ""),
            "planKey": manifest.get("planKey", ""),
            "os": manifest.get("os", ""),
            "compiler": manifest.get("compiler", ""),
            "generatedAtUtc": manifest.get("generatedAtUtc", ""),
            "generatorVersion": manifest.get("generatorVersion", ""),
            "sourceRevision": manifest.get("sourceRevision", ""),
            "manifestData": manifest,
        }
    return bundles


def _build_compare_report(previous_bundles: dict[str, dict[str, Any]], scripts_root: Path, index_text: str) -> dict[str, Any]:
    current_index = json.loads(index_text)
    current_bundles: dict[str, dict[str, Any]] = {}
    for bundle in current_index["bundles"]:
        current_bundles[bundle["buildId"]] = {
            **bundle,
            "manifestData": _load_manifest_data(scripts_root.parent / bundle["bundleManifest"]),
        }

    if not previous_bundles:
        return {
            "baseline": "none",
            "current": {
                "generatedAtUtc": current_index["generatedAtUtc"],
                "generatorVersion": current_index["generatorVersion"],
                "sourceRevision": current_index["sourceRevision"],
            },
            "status": "initial-generation",
            "bundles": [],
        }

    all_build_ids = sorted(set(previous_bundles) | set(current_bundles))
    bundles: list[dict[str, Any]] = []

    for build_id in all_build_ids:
        previous = previous_bundles.get(build_id)
        current = current_bundles.get(build_id)
        if previous is None and current is not None:
            bundles.append(
                {
                    "buildId": build_id,
                    "status": "added",
                    "currentContentSha256": current["bundleContentSha256"],
                    "currentSha256": current["bundleSha256"],
                }
            )
            continue
        if previous is not None and current is None:
            bundles.append(
                {
                    "buildId": build_id,
                    "status": "removed",
                    "previousContentSha256": previous["bundleContentSha256"],
                    "previousSha256": previous["bundleSha256"],
                }
            )
            continue

        assert previous is not None and current is not None
        status = "unchanged" if previous["bundleContentSha256"] == current["bundleContentSha256"] else "changed"
        bundle_entry: dict[str, Any] = {
            "buildId": build_id,
            "status": status,
            "previousContentSha256": previous["bundleContentSha256"],
            "currentContentSha256": current["bundleContentSha256"],
            "previousSha256": previous["bundleSha256"],
            "currentSha256": current["bundleSha256"],
        }
        if status == "changed":
            bundle_entry["bundleChanges"] = _describe_bundle_level_changes(previous["manifestData"], current["manifestData"])
            bundle_entry["taskChanges"] = _describe_task_level_changes(previous["manifestData"], current["manifestData"])
        bundles.append(bundle_entry)

    return {
        "baseline": "existing-output",
        "current": {
            "generatedAtUtc": current_index["generatedAtUtc"],
            "generatorVersion": current_index["generatorVersion"],
            "sourceRevision": current_index["sourceRevision"],
        },
        "bundles": bundles,
    }


def _load_manifest_data(manifest_path: Path) -> dict[str, Any]:
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _describe_task_level_changes(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    previous_tasks = {task["taskName"]: task for task in previous_manifest.get("tasks", [])}
    current_tasks = {task["taskName"]: task for task in current_manifest.get("tasks", [])}

    for task_name in sorted(set(previous_tasks) | set(current_tasks)):
        previous_task = previous_tasks.get(task_name)
        current_task = current_tasks.get(task_name)
        if previous_task is None and current_task is not None:
            changes.append({"taskName": task_name, "status": "added"})
            continue
        if previous_task is not None and current_task is None:
            changes.append({"taskName": task_name, "status": "removed"})
            continue

        assert previous_task is not None and current_task is not None
        python_changed = (
            previous_task["checksums"]["pythonScriptSha256"] != current_task["checksums"]["pythonScriptSha256"]
        )
        launcher_changed = (
            previous_task["checksums"]["launcherScriptSha256"] != current_task["checksums"]["launcherScriptSha256"]
        )
        if not python_changed and not launcher_changed:
            source_changes = _describe_task_source_changes(previous_task, current_task)
            if source_changes:
                changes.append({"taskName": task_name, "status": "changed", "sourceChanges": source_changes})
            continue

        task_change: dict[str, Any] = {"taskName": task_name, "status": "changed"}
        if python_changed:
            task_change["pythonScriptChanged"] = {
                "previousSha256": previous_task["checksums"]["pythonScriptSha256"],
                "currentSha256": current_task["checksums"]["pythonScriptSha256"],
            }
        if launcher_changed:
            task_change["launcherScriptChanged"] = {
                "previousSha256": previous_task["checksums"]["launcherScriptSha256"],
                "currentSha256": current_task["checksums"]["launcherScriptSha256"],
            }
        source_changes = _describe_task_source_changes(previous_task, current_task)
        if source_changes:
            task_change["sourceChanges"] = source_changes
        changes.append(task_change)
    return changes


def _describe_bundle_level_changes(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
) -> dict[str, Any]:
    changes: dict[str, Any] = {}

    if previous_manifest.get("workingSubPath") != current_manifest.get("workingSubPath"):
        changes["workingSubPath"] = {
            "previous": previous_manifest.get("workingSubPath", ""),
            "current": current_manifest.get("workingSubPath", ""),
        }

    previous_runtime = previous_manifest.get("runtimeRequirements", {})
    current_runtime = current_manifest.get("runtimeRequirements", {})
    previous_commands = previous_runtime.get("commands", [])
    current_commands = current_runtime.get("commands", [])
    previous_env_vars = previous_runtime.get("envVars", [])
    current_env_vars = current_runtime.get("envVars", [])

    if previous_commands != current_commands:
        changes["runtimeCommands"] = {
            "previous": previous_commands,
            "current": current_commands,
        }

    if previous_env_vars != current_env_vars:
        changes["runtimeEnvVars"] = {
            "previous": previous_env_vars,
            "current": current_env_vars,
        }

    return changes


def _describe_task_source_changes(
    previous_task: dict[str, Any],
    current_task: dict[str, Any],
) -> dict[str, dict[str, str]]:
    changes: dict[str, dict[str, str]] = {}
    previous_python_sources = previous_task.get("assetSources", {}).get("pythonScript", {})
    current_python_sources = current_task.get("assetSources", {}).get("pythonScript", {})

    for source_key in ("template", "commandSupport", "preRun"):
        previous_value = previous_python_sources.get(source_key) or ""
        current_value = current_python_sources.get(source_key) or ""
        if previous_value != current_value:
            changes[source_key] = {
                "previous": previous_value,
                "current": current_value,
            }

    previous_launcher_source = previous_task.get("assetSources", {}).get("launcherScript") or ""
    current_launcher_source = current_task.get("assetSources", {}).get("launcherScript") or ""
    if previous_launcher_source != current_launcher_source:
        changes["launcher"] = {
            "previous": previous_launcher_source,
            "current": current_launcher_source,
        }

    return changes


def _format_compare_report_text(compare_report: dict[str, Any]) -> str:
    lines = [
        f"baseline={compare_report['baseline']}",
        f"current.generatedAtUtc={compare_report['current']['generatedAtUtc']}",
        f"current.generatorVersion={compare_report['current']['generatorVersion']}",
        f"current.sourceRevision={compare_report['current']['sourceRevision']}",
    ]

    if compare_report.get("status"):
        lines.append(f"status={compare_report['status']}")
        return "\n".join(lines) + "\n"

    for bundle in compare_report["bundles"]:
        build_id = bundle["buildId"]
        lines.append(f"bundle.{build_id}.status={bundle['status']}")
        if "previousContentSha256" in bundle:
            lines.append(f"bundle.{build_id}.previousContentSha256={bundle['previousContentSha256']}")
        if "currentContentSha256" in bundle:
            lines.append(f"bundle.{build_id}.currentContentSha256={bundle['currentContentSha256']}")
        if "previousSha256" in bundle:
            lines.append(f"bundle.{build_id}.previousSha256={bundle['previousSha256']}")
        if "currentSha256" in bundle:
            lines.append(f"bundle.{build_id}.currentSha256={bundle['currentSha256']}")

        for key, change in bundle.get("bundleChanges", {}).items():
            if key == "workingSubPath":
                lines.extend(
                    [
                        f"bundle.{build_id}.workingSubPath.changed=true",
                        f"bundle.{build_id}.workingSubPath.previous={change['previous']}",
                        f"bundle.{build_id}.workingSubPath.current={change['current']}",
                    ]
                )
            elif key == "runtimeCommands":
                lines.extend(
                    [
                        f"bundle.{build_id}.runtime.commands.changed=true",
                        f"bundle.{build_id}.runtime.commands.previous={','.join(change['previous'])}",
                        f"bundle.{build_id}.runtime.commands.current={','.join(change['current'])}",
                    ]
                )
            elif key == "runtimeEnvVars":
                lines.extend(
                    [
                        f"bundle.{build_id}.runtime.envVars.changed=true",
                        f"bundle.{build_id}.runtime.envVars.previous={','.join(change['previous'])}",
                        f"bundle.{build_id}.runtime.envVars.current={','.join(change['current'])}",
                    ]
                )

        for task in bundle.get("taskChanges", []):
            task_name = task["taskName"]
            lines.append(f"bundle.{build_id}.task.{task_name}.status={task['status']}")
            if "pythonScriptChanged" in task:
                lines.extend(
                    [
                        f"bundle.{build_id}.task.{task_name}.pythonScript.changed=true",
                        f"bundle.{build_id}.task.{task_name}.pythonScript.previousSha256={task['pythonScriptChanged']['previousSha256']}",
                        f"bundle.{build_id}.task.{task_name}.pythonScript.currentSha256={task['pythonScriptChanged']['currentSha256']}",
                    ]
                )
            if "launcherScriptChanged" in task:
                lines.extend(
                    [
                        f"bundle.{build_id}.task.{task_name}.launcherScript.changed=true",
                        f"bundle.{build_id}.task.{task_name}.launcherScript.previousSha256={task['launcherScriptChanged']['previousSha256']}",
                        f"bundle.{build_id}.task.{task_name}.launcherScript.currentSha256={task['launcherScriptChanged']['currentSha256']}",
                    ]
                )
            for source_key, change in task.get("sourceChanges", {}).items():
                lines.extend(
                    [
                        f"bundle.{build_id}.task.{task_name}.source.{source_key}.changed=true",
                        f"bundle.{build_id}.task.{task_name}.source.{source_key}.previous={change['previous']}",
                        f"bundle.{build_id}.task.{task_name}.source.{source_key}.current={change['current']}",
                    ]
                )

    return "\n".join(lines) + "\n"
