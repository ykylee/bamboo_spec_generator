from __future__ import annotations

import sys
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.buildmeta.models import BuildPlan
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
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project", "project_build__repository")
            .prefetch_related("build_infos")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None
    if not hasattr(plan, "project_build"):
        return None
    build_info = _resolve_primary_build_info(plan)
    payload = _build_definition_payload_from_registration(plan=plan, build_info=build_info)
    return {
        "planKey": plan.plan_key,
        "buildId": plan.build_id,
        "year": str(timezone.now().year),
        "definitionVersion": "",
        "definition": payload,
    }


def get_prepare_context_by_plan_key(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project")
            .prefetch_related("project_build__project__repositories")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    project_build = plan.project_build
    project = project_build.project
    repositories = list(project.repositories.all())
    current_repository = getattr(project_build, "repository", None)

    if current_repository is None:
        current_repository = next((repo for repo in repositories if repo.is_representative), None)
    if current_repository is None and repositories:
        current_repository = repositories[0]
    linkage_mode = _repository_linkage_mode(project=project, repository=current_repository)
    clone_url = (
        build_git_clone_url(
            project_key=project.bitbucket_project_key,
            repo_slug=current_repository.repo_slug,
        )
        if current_repository
        else ""
    )

    return {
        "planKey": plan.plan_key,
        "project": {
            "jiraProjectKey": project.jira_project_key,
            "bitbucketProjectKey": project.bitbucket_project_key,
            "representativeRepoSlug": project.representative_repo_slug,
        },
        "currentRepository": {
            "repoSlug": current_repository.repo_slug if current_repository else "",
            "coverityProject": current_repository.coverity_project if current_repository else "",
            "coverityStream": current_repository.coverity_stream if current_repository else "",
            "applicationLink": "BITBUCKET_SERVER",
            "cloneUrl": clone_url,
            "linkageMode": linkage_mode,
        },
        "projectBuild": {
            "buildName": project_build.build_name,
            "buildType": project_build.build_type,
        },
        "repositories": [
            {"repoSlug": repo.repo_slug, "isRepresentative": repo.is_representative}
            for repo in repositories
        ],
        "variables": {
            "JIRA_PROJECT_KEY": project.jira_project_key,
            "BITBUCKET_PROJECT_KEY": project.bitbucket_project_key,
            "BITBUCKET_REPO_SLUG": current_repository.repo_slug if current_repository else "",
            "BITBUCKET_APPLICATION_LINK": "BITBUCKET_SERVER",
            "BITBUCKET_CLONE_URL": clone_url,
            "REPRESENTATIVE_REPO_SLUG": project.representative_repo_slug,
            "COVERITY_PROJECT": current_repository.coverity_project if current_repository else "",
            "COVERITY_STREAM": current_repository.coverity_stream if current_repository else "",
            "PROJECT_BUILD_NAME": project_build.build_name,
            "PROJECT_BUILD_TYPE": project_build.build_type,
            "currentRepository.linkageMode": linkage_mode,
        },
    }


def get_build_plan_preview(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project", "project_build__repository")
            .prefetch_related("build_infos", "build_infos__executions")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    repository = getattr(plan.project_build, "repository", None)
    project = plan.project_build.project
    build_infos = list(plan.build_infos.all().order_by("build_key"))
    plan_definition = _build_definition_for_plan_summary(plan=plan, build_infos=build_infos)

    prepare_job = {
        "jobId": "plan-prepare",
        "buildKey": "plan-prepare",
        "name": "plan-prepare",
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
                        "name": "Register Build Start",
                        "type": "metadata",
                        "detail": f"plan={plan.plan_key} · version update",
                    },
                    {
                        "name": "Record Execution Context",
                        "type": "metadata",
                        "detail": f"project={project.jira_project_key} · buildInfos={len(build_infos)}",
                    },
                ],
            }
        ],
        "sourceSummary": [
            {"label": "준비 단계", "value": "플랜 공통"},
        ],
    }

    jobs = []
    for build_info in build_infos:
        build_definition = _build_definition_for_export(plan=plan, build_info=build_info)
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

        jobs.append(
            {
                "jobId": build_info.build_key,
                "buildKey": build_info.build_key,
                "name": build_info.build_key or f"{plan.plan_key}-job",
                "operatingSystem": operating_system,
                "language": language,
                "compiler": compiler,
                "preProcess": pre_process,
                "buildCommand": build_command,
                "cleanCommand": clean_command,
                "hasBuildStage": has_build_stage,
                "coverityStream": coverity_stream,
                "buildSubPath": build_definition.build.sub_path,
                "analysisExcludedFiles": analysis_excluded_files,
                "repositorySlug": repository.repo_slug if repository else "",
                "executionCount": build_info.executions.count(),
                "detailUrl": f"/projects/{project.jira_project_key}/builds/{plan.plan_key}/infos/{build_info.build_key}/",
                "taskGroups": [
                    *(
                        [
                            {
                                "stageId": "build",
                                "stageName": "Build",
                                "tasks": [
                                    {
                                        "name": "Checkout Source",
                                        "type": "checkout",
                                        "detail": (
                                            f"{project.bitbucket_project_key}/{repository.repo_slug}"
                                            if repository
                                            else "Repository 미연결"
                                        ),
                                    },
                                    {
                                        "name": "Pre Process",
                                        "type": "script",
                                        "detail": pre_process or "미지정",
                                    },
                                    {
                                        "name": "Clean Command",
                                        "type": "script",
                                        "detail": clean_command or "미지정",
                                    },
                                    {
                                        "name": "Run Build",
                                        "type": "script",
                                        "detail": build_command or "미지정",
                                    },
                                    {
                                        "name": "Package Binary",
                                        "type": "artifact",
                                        "detail": "deployable binary package",
                                    },
                                ],
                            }
                        ]
                        if has_build_stage
                        else []
                    ),
                    {
                        "stageId": "analysis",
                        "stageName": "Analysis",
                        "tasks": [
                            {
                                "name": "Checkout Source",
                                "type": "checkout",
                                "detail": (
                                    f"{project.bitbucket_project_key}/{repository.repo_slug}"
                                    if repository
                                    else "Repository 미연결"
                                ),
                            },
                            {
                                "name": "Coverity Scan",
                                "type": "analysis",
                                "detail": coverity_stream or "Coverity Stream 미지정",
                            },
                            {
                                "name": "Custom Analysis",
                                "type": "analysis",
                                "detail": ", ".join(rendered_custom_commands) if rendered_custom_commands else "미지정",
                            },
                            {
                                "name": "Publish Report",
                                "type": "artifact",
                                "detail": "analysis report bundle",
                            },
                        ],
                    },
                ],
                "sourceSummary": [
                    {
                        "label": "OS/언어/컴파일러",
                        "value": "빌드 정보" if build_info.operating_system or build_info.language or build_info.compiler else "플랜 메타데이터",
                    },
                    {
                        "label": "명령어",
                        "value": "빌드 정보" if build_info.pre_process or build_info.build_command or build_info.clean_command else "기본값",
                    },
                    {
                        "label": "경로/Stream",
                        "value": (
                            "빌드 정보"
                            if build_info.build_sub_path or build_info.coverity_stream or build_info.analysis_excluded_files
                            else "기본 연결"
                        ),
                    },
                ],
            }
        )

    trigger_job = {
        "jobId": "plan-trigger",
        "buildKey": "plan-trigger",
        "name": "plan-trigger",
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
        "taskGroups": [
            {
                "stageId": "trigger-follow-up",
                "stageName": "Post Process",
                "tasks": [
                    {
                        "name": "Trigger Follow-up",
                        "type": "trigger",
                        "detail": plan_definition.build.post_build_trigger.target_plan_key or "미지정",
                    }
                ],
            }
        ],
        "sourceSummary": [
            {"label": "트리거", "value": "플랜 메타데이터"},
        ],
    }

    stages = [
        {
            "id": "prepare",
            "name": "Prepare",
            "jobCount": 1,
            "summary": "새 빌드 시작 시 버전 갱신과 실행 메타데이터 등록을 plan 공통 1회로 수행합니다.",
            "jobs": [
                {
                    "jobId": prepare_job["jobId"],
                    "name": prepare_job["name"],
                    "operatingSystem": "",
                    "taskCount": len(prepare_job["taskGroups"][0]["tasks"]),
                }
            ],
        },
        {
            "id": "build",
            "name": "Build",
            "jobCount": sum(1 for job in jobs if job["hasBuildStage"]),
            "summary": "checkout부터 build와 binary package 생성까지 build job에서 수행합니다. 스크립트 언어처럼 build가 없는 경우 이 단계는 생략됩니다.",
            "jobs": [
                {
                    "jobId": job["jobId"],
                    "name": job["name"],
                    "operatingSystem": job["operatingSystem"],
                    "taskCount": len(next(group for group in job["taskGroups"] if group["stageId"] == "build")["tasks"]),
                }
                for job in jobs
                if job["hasBuildStage"]
            ],
        },
        {
            "id": "analysis",
            "name": "Analysis",
            "jobCount": len(jobs),
            "summary": "analysis job은 build 산출물을 받지 않고 checkout부터 다시 시작해 report를 생성합니다.",
            "jobs": [
                {
                    "jobId": job["jobId"],
                    "name": job["name"],
                    "operatingSystem": job["operatingSystem"],
                    "taskCount": len(next(group for group in job["taskGroups"] if group["stageId"] == "analysis")["tasks"]),
                }
                for job in jobs
            ],
        },
        {
            "id": "post-process",
            "name": "Post Process",
            "jobCount": 1,
            "summary": "플랜 공통 후속 작업을 마지막 단계에서 수행합니다.",
            "jobs": [
                {
                    "jobId": trigger_job["jobId"],
                    "name": trigger_job["name"],
                    "operatingSystem": "",
                    "taskCount": 1,
                }
            ],
        },
    ]

    return {
        "plan": {
            "planKey": plan.plan_key,
            "buildId": plan.build_id,
            "buildName": plan.project_build.build_name,
            "staticAnalysisToolVersion": plan.static_analysis_tool_version,
            "coverityProject": plan.coverity_project,
            "definitionVersion": "",
            "definitionYear": "",
            "definitionConnected": False,
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
        "jobs": [prepare_job] + jobs + [trigger_job],
        "staticAnalysis": {
            "customToolCommands": list(plan_definition.build.static_analysis.custom_tool_commands),
            "postBuildTriggerType": plan_definition.build.post_build_trigger.type,
            "postBuildTriggerTargetPlanKey": plan_definition.build.post_build_trigger.target_plan_key,
        },
    }


def get_build_plan_export_draft(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project", "project_build__repository")
            .prefetch_related("build_infos")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    files: list[dict] = []
    build_infos = list(plan.build_infos.all().order_by("build_key"))
    repository = getattr(plan.project_build, "repository", None)
    coverity_system_settings = get_coverity_system_settings()

    for build_info in build_infos:
        build_definition = _build_definition_for_export(plan=plan, build_info=build_info)
        has_build_stage = not (
            is_no_build_language(language=build_definition.language, compiler=build_definition.compiler)
            and not build_definition.build.prepare_command.strip()
            and not build_definition.build.build_command.strip()
            and not build_info.clean_command.strip()
        )
        coverity_config = generate_coverity_yaml(
            build_definition,
            clean_command=build_info.clean_command,
            coverity_project=plan.coverity_project or (repository.coverity_project if repository else ""),
            coverity_stream=build_info.coverity_stream or (repository.coverity_stream if repository else ""),
            exclude_files_regex=build_info.analysis_excluded_files,
            connect_url=str(coverity_system_settings["connectUrl"]),
            on_new_cert=str(coverity_system_settings["onNewCert"]),
            commit_enabled=bool(coverity_system_settings["commitEnabled"]),
        )
        files.append(
            {
                "path": f"drafts/{plan.plan_key}/jobs/{build_info.build_key}/coverity.yaml",
                "label": f"{build_info.build_key} Coverity config",
                "language": "yaml",
                "content": coverity_config,
            }
        )
        python_scripts = render_python_scripts(build_definition, coverity_config=coverity_config)
        launcher_scripts = render_python_launcher_scripts(build_definition, coverity_config=coverity_config)
        script_names = ["prepare_build.py", "run_coverity.py", "run_custom_analysis.py", "trigger_follow_up.py"]
        if has_build_stage:
            script_names.append("run_build.py")
        for script_name in script_names:
            if script_name in python_scripts:
                files.append(
                    {
                        "path": f"drafts/{plan.plan_key}/jobs/{build_info.build_key}/{script_name}",
                        "label": f"{build_info.build_key} {script_name}",
                        "language": "python",
                        "content": python_scripts[script_name],
                    }
                )
        launcher_task_names = ["prepare_build", "run_coverity", "run_custom_analysis", "trigger_follow_up"]
        if has_build_stage:
            launcher_task_names.append("run_build")
        launcher_extension = ".bat" if build_definition.requirements.os.lower() == "windows" else ".sh"
        launcher_language = "batch" if launcher_extension == ".bat" else "shell"
        for task_name in launcher_task_names:
            launcher_name = f"{task_name}{launcher_extension}"
            if launcher_name not in launcher_scripts:
                continue
            files.append(
                {
                    "path": f"drafts/{plan.plan_key}/jobs/{build_info.build_key}/{launcher_name}",
                    "label": f"{build_info.build_key} {launcher_name}",
                    "language": launcher_language,
                    "content": launcher_scripts[launcher_name],
                }
            )

    return {
        "summary": {
            "planKey": plan.plan_key,
            "jobCount": len(build_infos),
            "fileCount": len(files),
        },
        "files": files,
    }


def _build_definition_for_export(*, plan: BuildPlan, build_info):
    return parse_build_definition_payload(
        _build_definition_payload_from_registration(plan=plan, build_info=build_info),
        year=str(timezone.now().year),
    )


def _build_definition_for_plan_summary(*, plan: BuildPlan, build_infos: list):
    build_info = build_infos[0] if build_infos else None
    return parse_build_definition_payload(
        _build_definition_payload_from_registration(plan=plan, build_info=build_info),
        year=str(timezone.now().year),
    )


def _build_definition_payload_from_registration(*, plan: BuildPlan, build_info) -> dict:
    project = plan.project_build.project
    repository = getattr(plan.project_build, "repository", None)
    linkage_mode = _repository_linkage_mode(project=project, repository=repository)
    clone_url = (
        build_git_clone_url(
            project_key=project.bitbucket_project_key,
            repo_slug=repository.repo_slug,
        )
        if repository
        else ""
    )
    language, compiler = _resolve_language_and_compiler(plan=plan, build_info=build_info)
    operating_system = _normalize_operating_system(getattr(build_info, "operating_system", ""))
    build_key = getattr(build_info, "build_key", "").strip()
    build_name = plan.project_build.build_name
    return {
        "buildId": plan.build_id,
        "name": f"{build_name} {build_key}".strip() if build_key else build_name,
        "planKey": plan.plan_key,
        "description": build_name,
        "language": language,
        "compiler": compiler,
        "repository": {
            "provider": "bitbucket",
            "projectKey": project.bitbucket_project_key,
            "repoSlug": repository.repo_slug if repository else "",
            "linkageMode": linkage_mode,
            "applicationLink": "BITBUCKET_SERVER",
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


def _resolve_primary_build_info(plan: BuildPlan):
    build_infos = list(plan.build_infos.all().order_by("build_key"))
    if build_infos:
        return build_infos[0]
    return None


def _resolve_language_and_compiler(*, plan: BuildPlan, build_info) -> tuple[str, str]:
    explicit_language = getattr(build_info, "language", "").strip()
    explicit_compiler = getattr(build_info, "compiler", "").strip()
    if explicit_language and explicit_compiler:
        return explicit_language, explicit_compiler

    build_type = (plan.project_build.build_type or "").strip().lower()
    runtime_stack = (plan.project_build.runtime_stack or "").strip().lower()
    inferred_language = explicit_language
    inferred_compiler = explicit_compiler

    if not inferred_language or not inferred_compiler:
        if build_type in {"maven", "java"} or "java" in runtime_stack:
            inferred_language = inferred_language or "java"
            inferred_compiler = inferred_compiler or "maven"
        elif build_type in {"node", "javascript", "typescript"} or "node" in runtime_stack:
            inferred_language = inferred_language or "javascript"
            inferred_compiler = inferred_compiler or "node.js"
        elif build_type == "python" or "python" in runtime_stack:
            inferred_language = inferred_language or "python"
            inferred_compiler = inferred_compiler or "python"
        else:
            inferred_language = inferred_language or plan.project_build.runtime_stack or ""
            inferred_compiler = inferred_compiler or plan.project_build.build_type or ""

    return inferred_language, inferred_compiler


def _normalize_operating_system(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "linux"


def _normalize_build_sub_path(value: str) -> str:
    normalized = (value or "").strip()
    return normalized or "."


def _repository_linkage_mode(*, project, repository) -> str:
    if repository is None:
        return "linked"
    if get_repository_linkage_mode() == "create_if_missing":
        return "create_if_missing"
    return "linked"


def _default_custom_tool_commands() -> list[str]:
    return ["custom-tool analyze {buildCommand}"]


def _default_runtime_commands(*, language: str, compiler: str) -> list[str]:
    normalized_language = (language or "").strip().lower()
    normalized_compiler = (compiler or "").strip().lower()
    if normalized_compiler == "maven" or normalized_language == "java":
        return ["mvn", "coverity"]
    if normalized_compiler == "node.js" or normalized_language in {"javascript", "typescript"}:
        return ["node", "coverity"]
    if normalized_compiler == "python" or normalized_language == "python":
        return ["python", "coverity"]
    return ["coverity"]


def _default_runtime_env_vars(*, language: str, compiler: str) -> list[str]:
    normalized_language = (language or "").strip().lower()
    normalized_compiler = (compiler or "").strip().lower()
    if normalized_compiler == "maven" or normalized_language == "java":
        return ["JAVA_HOME"]
    if normalized_compiler == "python" or normalized_language == "python":
        return ["PYTHONPATH"]
    return ["PATH"]
