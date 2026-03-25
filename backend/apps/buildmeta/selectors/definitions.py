from __future__ import annotations

import sys
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.buildmeta.models import BambooBuildUnit, BuildUnitDefinition
from apps.buildmeta.services.system_settings import (
    build_git_clone_url,
    get_coverity_system_settings,
    get_repository_linkage_mode,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bamboo_spec_generator.generator import generate_coverity_yaml  # noqa: E402
from src.bamboo_spec_generator.parser import parse_build_definition_payload  # noqa: E402
from src.bamboo_spec_generator.script_renderer import render_python_launcher_scripts, render_python_scripts  # noqa: E402
from src.bamboo_spec_generator.validator import is_no_build_language  # noqa: E402


def get_active_definition_by_plan_key(plan_key: str) -> dict | None:
    definitions = get_active_definitions_by_plan_key(plan_key)
    return definitions[0] if definitions else None


def get_active_definitions_by_plan_key(plan_key: str) -> list[dict]:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        return []
    if _has_orphan_legacy_plan(plan_key):
        return []

    active_definitions = list(
        bamboo_unit.build_unit.definitions.filter(is_active=True).order_by("created_at")
    )
    if active_definitions:
        return [
            {
                "planKey": bamboo_unit.plan_key,
                "buildId": bamboo_unit.build_id,
                "year": definition.year or str(timezone.now().year),
                "definitionVersion": str(definition.version),
                "definition": definition.definition_json,
            }
            for definition in active_definitions
        ]

    build_infos = list(bamboo_unit.build_infos.all().order_by("build_key"))
    if not build_infos:
        build_infos = [None]

    definitions = []
    for build_info in build_infos:
        payload = _build_definition_payload_from_registration(bamboo_unit=bamboo_unit, build_info=build_info)
        definitions.append(
            {
                "planKey": bamboo_unit.plan_key,
                "buildId": bamboo_unit.build_id,
                "year": str(timezone.now().year),
                "definitionVersion": "",
                "definition": payload,
            }
        )
    return definitions


def get_prepare_context_by_plan_key(plan_key: str) -> dict | None:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        return None
    if _has_orphan_legacy_plan(plan_key):
        return None

    build_unit = bamboo_unit.build_unit
    project = build_unit.project
    repositories = list(project.repositories.all())
    current_repository = build_unit.repository

    if current_repository is None:
        current_repository = project.representative_repository
    if current_repository is None and repositories:
        current_repository = repositories[0]

    clone_url = current_repository.clone_url.strip() if current_repository else ""
    if current_repository and not clone_url:
        clone_url = build_git_clone_url(
            project_key=current_repository.repo_key,
            repo_slug=current_repository.repo_slug,
        )

    linkage_mode = (
        bamboo_unit.repository_linkage_mode.strip()
        or get_repository_linkage_mode()
    )

    return {
        "planKey": bamboo_unit.plan_key,
        "project": {
            "jiraProjectKey": project.project_key,
            "bitbucketProjectKey": current_repository.repo_key if current_repository else "",
            "representativeRepoSlug": project.representative_repository.repo_slug if project.representative_repository_id else "",
        },
        "currentRepository": {
            "repoSlug": current_repository.repo_slug if current_repository else "",
            "coverityProject": current_repository.coverity_project if current_repository else "",
            "coverityStream": current_repository.coverity_stream if current_repository else "",
            "applicationLink": bamboo_unit.application_link or "BITBUCKET_SERVER",
            "cloneUrl": clone_url,
            "linkageMode": linkage_mode,
        },
        "projectBuild": {
            "buildName": build_unit.display_name,
            "buildType": build_unit.compiler,
        },
        "repositories": [
            {"repoSlug": repo.repo_slug, "isRepresentative": repo.is_representative}
            for repo in repositories
        ],
        "variables": {
            "JIRA_PROJECT_KEY": project.project_key,
            "BITBUCKET_PROJECT_KEY": current_repository.repo_key if current_repository else "",
            "BITBUCKET_REPO_SLUG": current_repository.repo_slug if current_repository else "",
            "BITBUCKET_APPLICATION_LINK": bamboo_unit.application_link or "BITBUCKET_SERVER",
            "BITBUCKET_CLONE_URL": clone_url,
            "REPRESENTATIVE_REPO_SLUG": project.representative_repository.repo_slug if project.representative_repository_id else "",
            "COVERITY_PROJECT": current_repository.coverity_project if current_repository else "",
            "COVERITY_STREAM": current_repository.coverity_stream if current_repository else "",
            "PROJECT_BUILD_NAME": build_unit.display_name,
            "PROJECT_BUILD_TYPE": build_unit.compiler,
            "currentRepository.linkageMode": linkage_mode,
        },
    }


def get_build_plan_preview(plan_key: str) -> dict | None:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        return None
    if _has_orphan_legacy_plan(plan_key):
        return None

    build_unit = bamboo_unit.build_unit
    project = build_unit.project
    repository = build_unit.repository or project.representative_repository
    build_infos = list(bamboo_unit.build_infos.all().order_by("build_key"))
    plan_definition = _build_definition_for_plan_summary(bamboo_unit=bamboo_unit, build_infos=build_infos)

    prepare_job = {
        "jobId": "plan-prepare",
        "buildKey": "plan-prepare",
        "name": "Prepare Job",
        "operatingSystem": "",
        "language": "",
        "compiler": "",
        "preProcess": "",
        "buildCommand": "",
        "cleanCommand": "",
        "hasBuildStage": False,
        "coverityStream": "",
        "buildSubPath": "",
        "analysisExcludedFiles": "",
        "repositorySlug": repository.repo_slug if repository else "",
        "executionCount": 0,
        "detailUrl": "",
        "taskGroups": [
            {
                "stageId": "prepare",
                "stageName": "Prepare",
                "tasks": [
                    {
                        "name": "Checkout Source",
                        "type": "checkout",
                        "detail": f"{repository.repo_key}/{repository.repo_slug}" if repository else "Repository 미연결",
                    },
                    {
                        "name": "Prepare Build Script",
                        "type": "script",
                        "detail": f"plan={bamboo_unit.plan_key} · project={project.project_key} · buildInfos={len(build_infos)}",
                    },
                ],
            }
        ],
        "sourceSummary": [{"label": "준비 단계", "value": "플랜 공통"}],
    }

    build_jobs = []
    analysis_jobs = []
    for build_info in build_infos:
        build_definition = _build_definition_for_export(bamboo_unit=bamboo_unit, build_info=build_info)
        operating_system = build_definition.requirements.os
        build_command = build_definition.build.build_command
        pre_process = build_definition.build.prepare_command
        clean_command = build_info.clean_command.strip()
        language = build_definition.language
        compiler = build_definition.compiler
        has_build_stage = not (
            is_no_build_language(language=language, compiler=compiler)
            and not build_command.strip()
            and not clean_command.strip()
            and not pre_process.strip()
        )
        coverity_stream = build_info.coverity_stream or (repository.coverity_stream if repository else "")
        analysis_excluded_files = build_info.analysis_excluded_files
        custom_commands = list(build_definition.build.static_analysis.custom_tool_commands)
        rendered_custom_commands = [command.replace("{buildCommand}", build_command) for command in custom_commands]
        common_job_payload = {
            "buildKey": build_info.build_key,
            "operatingSystem": operating_system,
            "language": language,
            "compiler": compiler,
            "preProcess": pre_process,
            "buildCommand": build_command,
            "cleanCommand": clean_command,
            "coverityStream": coverity_stream,
            "buildSubPath": build_definition.build.sub_path,
            "analysisExcludedFiles": analysis_excluded_files,
            "repositorySlug": repository.repo_slug if repository else "",
            "executionCount": build_unit.executions.count(),
            "detailUrl": "",
            "sourceSummary": [
                {"label": "OS/언어/컴파일러", "value": "빌드 정보"},
                {"label": "명령어", "value": "빌드 정보"},
                {"label": "경로/Stream", "value": "빌드 정보" if analysis_excluded_files or coverity_stream else "기본 연결"},
            ],
        }
        if has_build_stage:
            build_jobs.append(
                {
                    **common_job_payload,
                    "jobId": f"{build_info.build_key}-build",
                    "name": _build_stage_job_name(build_info.build_key, bamboo_unit.plan_key),
                    "hasBuildStage": True,
                    "taskGroups": [{
                        "stageId": "build",
                        "stageName": "Build",
                        "tasks": [
                            {"name": "Checkout Source", "type": "checkout", "detail": f"{repository.repo_key}/{repository.repo_slug}" if repository else "Repository 미연결"},
                            {"name": "Run Build Script", "type": "script", "detail": _summarize_build_script(pre_process=pre_process, clean_command=clean_command, build_command=build_command)},
                        ],
                    }],
                }
            )
        analysis_jobs.append(
            {
                **common_job_payload,
                "jobId": f"{build_info.build_key}-analysis",
                "name": _analysis_stage_job_name(build_info.build_key, bamboo_unit.plan_key),
                "hasBuildStage": False,
                "taskGroups": [{
                    "stageId": "analysis",
                    "stageName": "Analysis",
                    "tasks": [
                        {"name": "Checkout Source", "type": "checkout", "detail": f"{repository.repo_key}/{repository.repo_slug}" if repository else "Repository 미연결"},
                        {"name": "Run Coverity Script", "type": "script", "detail": coverity_stream or "Coverity Stream 미지정"},
                        {"name": "Run Custom Analysis Script", "type": "script", "detail": ", ".join(rendered_custom_commands) if rendered_custom_commands else "미지정"},
                    ],
                }],
            }
        )

    trigger_job = {
        "jobId": "plan-trigger",
        "buildKey": "plan-trigger",
        "name": "Trigger Follow-up",
        "operatingSystem": "",
        "language": "",
        "compiler": "",
        "preProcess": "",
        "buildCommand": "",
        "cleanCommand": "",
        "coverityStream": "",
        "buildSubPath": "",
        "analysisExcludedFiles": "",
        "repositorySlug": repository.repo_slug if repository else "",
        "executionCount": 0,
        "detailUrl": "",
        "taskGroups": [{
            "stageId": "trigger-follow-up",
            "stageName": "Post Process",
            "tasks": [{"name": "Trigger Follow-up Script", "type": "script", "detail": plan_definition.build.post_build_trigger.target_plan_key or "미지정"}],
        }],
        "sourceSummary": [{"label": "트리거", "value": "플랜 메타데이터"}],
    }

    stages = [
        {"id": "prepare", "name": "Prepare", "jobCount": 1, "summary": "새 빌드 시작 시 버전 갱신과 실행 메타데이터 등록을 plan 공통 1회로 수행합니다.", "jobs": [{"jobId": prepare_job["jobId"], "name": prepare_job["name"], "operatingSystem": "", "taskCount": len(prepare_job["taskGroups"][0]["tasks"])}]},
        {"id": "build", "name": "Build", "jobCount": len(build_jobs), "summary": "checkout부터 build와 binary package 생성까지 build job에서 수행합니다. 스크립트 언어처럼 build가 없는 경우 이 단계는 생략됩니다.", "jobs": [{"jobId": job["jobId"], "name": job["name"], "operatingSystem": job["operatingSystem"], "taskCount": len(next(group for group in job["taskGroups"] if group["stageId"] == "build")["tasks"])} for job in build_jobs]},
        {"id": "analysis", "name": "Analysis", "jobCount": len(analysis_jobs), "summary": "analysis job은 build 산출물을 받지 않고 checkout부터 다시 시작해 report를 생성합니다.", "jobs": [{"jobId": job["jobId"], "name": job["name"], "operatingSystem": job["operatingSystem"], "taskCount": len(next(group for group in job["taskGroups"] if group["stageId"] == "analysis")["tasks"])} for job in analysis_jobs]},
        {"id": "post-process", "name": "Post Process", "jobCount": 1, "summary": "플랜 공통 후속 작업을 마지막 단계에서 수행합니다.", "jobs": [{"jobId": trigger_job["jobId"], "name": trigger_job["name"], "operatingSystem": "", "taskCount": 1}]},
    ]

    return {
        "plan": {
            "planKey": bamboo_unit.plan_key,
            "buildId": bamboo_unit.build_id,
            "buildName": build_unit.display_name,
            "staticAnalysisToolVersion": bamboo_unit.static_analysis_tool_version,
            "coverityProject": bamboo_unit.coverity_project,
            "definitionVersion": "",
            "definitionYear": "",
            "definitionConnected": build_unit.definitions.filter(is_active=True).exists(),
        },
        "repository": {
            "provider": plan_definition.repository.provider,
            "projectKey": plan_definition.repository.project_key,
            "repoSlug": plan_definition.repository.repo_slug,
            "linkageMode": plan_definition.repository.linkage_mode,
            "applicationLink": plan_definition.repository.application_link or "BITBUCKET_SERVER",
            "branches": list(plan_definition.repository.branches),
        },
        "requirements": {
            "extraCapabilities": list(plan_definition.requirements.extra_capabilities),
            "runtimeCommands": list(plan_definition.build.runtime_requirements.commands),
            "runtimeEnvVars": list(plan_definition.build.runtime_requirements.env_vars),
        },
        "stages": stages,
        "jobs": [prepare_job] + build_jobs + analysis_jobs + [trigger_job],
        "staticAnalysis": {
            "customToolCommands": list(plan_definition.build.static_analysis.custom_tool_commands),
            "postBuildTriggerType": plan_definition.build.post_build_trigger.type,
            "postBuildTriggerTargetPlanKey": plan_definition.build.post_build_trigger.target_plan_key,
        },
    }


def get_build_plan_export_draft(plan_key: str) -> dict | None:
    bamboo_unit = _get_bamboo_build_unit(plan_key)
    if bamboo_unit is None:
        return None
    if _has_orphan_legacy_plan(plan_key):
        return None

    files: list[dict] = []
    build_infos = list(bamboo_unit.build_infos.all().order_by("build_key"))
    repository = bamboo_unit.build_unit.repository or bamboo_unit.build_unit.project.representative_repository
    coverity_system_settings = get_coverity_system_settings()
    for build_info in build_infos:
        build_definition = _build_definition_for_export(bamboo_unit=bamboo_unit, build_info=build_info)
        has_build_stage = not (
            is_no_build_language(language=build_definition.language, compiler=build_definition.compiler)
            and not build_definition.build.prepare_command.strip()
            and not build_definition.build.build_command.strip()
            and not build_info.clean_command.strip()
        )
        coverity_config = generate_coverity_yaml(
            build_definition,
            clean_command=build_info.clean_command,
            coverity_project=bamboo_unit.coverity_project or (repository.coverity_project if repository else ""),
            coverity_stream=build_info.coverity_stream or (repository.coverity_stream if repository else ""),
            exclude_files_regex=build_info.analysis_excluded_files,
            connect_url=str(coverity_system_settings["connectUrl"]),
            on_new_cert=str(coverity_system_settings["onNewCert"]),
            commit_enabled=bool(coverity_system_settings["commitEnabled"]),
        )
        files.append({"path": f"drafts/{bamboo_unit.plan_key}/jobs/{build_info.build_key}/coverity.yaml", "label": f"{build_info.build_key} Coverity config", "language": "yaml", "content": coverity_config})
        python_scripts = render_python_scripts(build_definition, coverity_config=coverity_config)
        launcher_scripts = render_python_launcher_scripts(build_definition, coverity_config=coverity_config)
        script_names = ["prepare_build.py", "run_coverity.py", "run_custom_analysis.py", "trigger_follow_up.py"]
        if has_build_stage:
            script_names.append("run_build.py")
        for script_name in script_names:
            if script_name in python_scripts:
                files.append({"path": f"drafts/{bamboo_unit.plan_key}/jobs/{build_info.build_key}/{script_name}", "label": f"{build_info.build_key} {script_name}", "language": "python", "content": python_scripts[script_name]})
        launcher_task_names = ["prepare_build", "run_coverity", "run_custom_analysis", "trigger_follow_up"]
        if has_build_stage:
            launcher_task_names.append("run_build")
        launcher_extension = ".bat" if build_definition.requirements.os.lower() == "windows" else ".sh"
        launcher_language = "batch" if launcher_extension == ".bat" else "shell"
        for task_name in launcher_task_names:
            launcher_name = f"{task_name}{launcher_extension}"
            if launcher_name not in launcher_scripts:
                continue
            files.append({"path": f"drafts/{bamboo_unit.plan_key}/jobs/{build_info.build_key}/{launcher_name}", "label": f"{build_info.build_key} {launcher_name}", "language": launcher_language, "content": launcher_scripts[launcher_name]})
    return {"summary": {"planKey": bamboo_unit.plan_key, "jobCount": len(build_infos), "fileCount": len(files)}, "files": files}


def _get_bamboo_build_unit(plan_key: str) -> BambooBuildUnit | None:
    return (
        BambooBuildUnit.objects.select_related("build_unit__project", "build_unit__repository", "build_unit__project__representative_repository")
        .prefetch_related("build_infos", "build_unit__definitions", "build_unit__executions")
        .filter(plan_key=plan_key)
        .first()
    )


def _has_orphan_legacy_plan(plan_key: str) -> bool:
    bamboo_unit = BambooBuildUnit.objects.select_related("build_unit__project", "build_unit__repository").filter(plan_key=plan_key).first()
    if bamboo_unit is None:
        return False
    build_unit = bamboo_unit.build_unit
    project = build_unit.project
    return (
        project.project_key.startswith("DETACHED-")
        and build_unit.repository_id is None
        and not project.repositories.exists()
    )


def _build_definition_for_export(*, bamboo_unit: BambooBuildUnit, build_info):
    return parse_build_definition_payload(
        _build_definition_payload_from_registration(bamboo_unit=bamboo_unit, build_info=build_info),
        year=str(timezone.now().year),
    )


def _build_definition_for_plan_summary(*, bamboo_unit: BambooBuildUnit, build_infos: list):
    build_info = build_infos[0] if build_infos else None
    return parse_build_definition_payload(
        _build_definition_payload_from_registration(bamboo_unit=bamboo_unit, build_info=build_info),
        year=str(timezone.now().year),
    )


def _build_definition_payload_from_registration(*, bamboo_unit: BambooBuildUnit | None = None, plan=None, build_info=None) -> dict:
    if bamboo_unit is not None:
        build_unit = bamboo_unit.build_unit
        project = build_unit.project
        repository = build_unit.repository or project.representative_repository
        build_id = bamboo_unit.build_id
        plan_key = bamboo_unit.plan_key
        linkage_mode = bamboo_unit.repository_linkage_mode or get_repository_linkage_mode()
        application_link = bamboo_unit.application_link or "BITBUCKET_SERVER"
        build_name = build_unit.display_name
    else:
        project_build = getattr(plan, "project_build", None)
        project = getattr(project_build, "project", None)
        repository = getattr(project_build, "repository", None)
        build_id = getattr(plan, "build_id", "")
        plan_key = getattr(plan, "plan_key", "")
        linkage_mode = _repository_linkage_mode(plan=plan, project=project, repository=repository)
        application_link = "BITBUCKET_SERVER"
        build_name = getattr(project_build, "build_name", "") or build_id

    clone_url = repository.clone_url.strip() if repository else ""
    if repository and not clone_url:
        clone_url = build_git_clone_url(
            project_key=getattr(repository, "repo_key", "") or getattr(project, "bitbucket_project_key", ""),
            repo_slug=repository.repo_slug,
        )
    language, compiler = _resolve_language_and_compiler(plan=plan or bamboo_unit, build_info=build_info)
    operating_system = _normalize_operating_system(getattr(build_info, "operating_system", ""))
    build_key = getattr(build_info, "build_key", "").strip()
    return {
        "buildId": build_id,
        "buildKey": build_key,
        "name": f"{build_name} {build_key}".strip() if build_key else build_name,
        "planKey": plan_key,
        "description": build_name,
        "language": language or "python",
        "compiler": compiler or "script",
        "repository": {
            "provider": getattr(repository, "repo_type", "bitbucket") if repository else "bitbucket",
            "projectKey": getattr(repository, "repo_key", "") if repository else getattr(project, "bitbucket_project_key", ""),
            "repoSlug": repository.repo_slug if repository else "",
            "linkageMode": linkage_mode,
            "applicationLink": application_link,
            "cloneUrl": clone_url,
            "branches": ["dev", "release", "master"],
        },
        "requirements": {"os": operating_system, "extraCapabilities": []},
        "build": {
            "subPath": _normalize_build_sub_path(getattr(build_info, "build_sub_path", "")),
            "prepareCommand": getattr(build_info, "pre_process", "").strip(),
            "buildCommand": getattr(build_info, "build_command", "").strip(),
            "staticAnalysis": {"customTool": {"commands": _default_custom_tool_commands()}},
            "runtimeRequirements": {
                "commands": _default_runtime_commands(language=language, compiler=compiler),
                "envVars": _default_runtime_env_vars(language=language, compiler=compiler),
            },
            "postBuildTrigger": {"type": "plan", "targetPlanKey": ""},
        },
    }


def _normalize_operating_system(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "linux"


def _normalize_build_sub_path(value: str) -> str:
    return (value or "").strip() or "."


def _default_custom_tool_commands() -> list[str]:
    return ["custom-tool analyze {buildCommand}"]


def _default_runtime_commands(*, language: str, compiler: str) -> list[str]:
    commands: list[str] = []
    normalized_language = (language or "").strip().lower()
    normalized_compiler = (compiler or "").strip().lower()
    if normalized_language == "java" or normalized_compiler == "maven":
        commands.append("mvn")
    if normalized_language in {"node", "node.js", "javascript", "typescript"}:
        commands.append("npm")
    commands.append("coverity")
    return commands


def _default_runtime_env_vars(*, language: str, compiler: str) -> list[str]:
    env_vars: list[str] = []
    normalized_language = (language or "").strip().lower()
    normalized_compiler = (compiler or "").strip().lower()
    if normalized_language == "java" or normalized_compiler == "maven":
        env_vars.append("JAVA_HOME")
    elif not env_vars:
        env_vars.append("PATH")
    return env_vars


def _summarize_build_script(*, pre_process: str, clean_command: str, build_command: str) -> str:
    return " · ".join(
        [
            f"pre={pre_process.strip() or '-'}",
            f"clean={clean_command.strip() or '-'}",
            f"build={build_command.strip() or '-'}",
        ]
    )


def _build_stage_job_name(build_key: str, plan_key: str) -> str:
    return f"{build_key or plan_key} Build"


def _analysis_stage_job_name(build_key: str, plan_key: str) -> str:
    return f"{build_key or plan_key} Analysis"


def _repository_linkage_mode(*, plan, project, repository) -> str:
    override = getattr(plan, "repository_linkage_mode_override", "").strip()
    if override:
        return override
    if repository is not None:
        return get_repository_linkage_mode()
    return "linked"


def _resolve_language_and_compiler(*, plan, build_info) -> tuple[str, str]:
    explicit_language = (getattr(build_info, "language", "") or "").strip()
    explicit_compiler = (getattr(build_info, "compiler", "") or "").strip()
    project_build = getattr(plan, "project_build", None)
    if project_build is not None:
        fallback_language = (getattr(project_build, "runtime_stack", "") or "").strip()
        fallback_compiler = (getattr(project_build, "build_type", "") or "").strip()
    else:
        build_unit = getattr(plan, "build_unit", None)
        fallback_language = (getattr(build_unit, "language", "") or getattr(build_unit, "runtime_stack", "") or "").strip()
        fallback_compiler = (getattr(build_unit, "compiler", "") or "").strip()
    return explicit_language or fallback_language, explicit_compiler or fallback_compiler


def _resolve_primary_build_info(plan):
    build_infos = getattr(plan, "build_infos", None)
    if build_infos is None:
        return None
    ordered = build_infos.all().order_by("build_key")
    return ordered[0] if ordered else None
