from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import BuildPlan

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bamboo_spec_generator.generator import generate_coverity_yaml  # noqa: E402
from src.bamboo_spec_generator.parser import parse_build_definition_payload  # noqa: E402
from src.bamboo_spec_generator.script_renderer import render_python_launcher_scripts, render_python_scripts  # noqa: E402
from src.bamboo_spec_generator.validator import is_no_build_language  # noqa: E402


def _resolve_active_definition(plan: BuildPlan):
    return plan.definitions.filter(is_active=True).order_by("-created_at").first()


def _repository_application_link(repository_payload: dict) -> str:
    application_link = repository_payload.get("applicationLink", "")
    if isinstance(application_link, str) and application_link.strip():
        return application_link
    return "BITBUCKET_SERVER"


def get_active_definition_by_plan_key(plan_key: str) -> dict | None:
    try:
        plan = BuildPlan.objects.prefetch_related("definitions").get(plan_key=plan_key)
    except ObjectDoesNotExist:
        return None
    active_definition = _resolve_active_definition(plan)
    if active_definition is None:
        return None
    payload = dict(active_definition.definition_json)
    return {
        "planKey": plan.plan_key,
        "buildId": plan.build_id,
        "year": active_definition.year,
        "definitionVersion": active_definition.definition_hash,
        "definition": payload,
    }


def get_prepare_context_by_plan_key(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project")
            .prefetch_related("project_build__project__repositories")
            .prefetch_related("definitions")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    project_build = plan.project_build
    project = project_build.project
    active_definition = _resolve_active_definition(plan)
    definition_payload = active_definition.definition_json if active_definition else {}
    repository_payload = definition_payload.get("repository", {})
    repo_slug = repository_payload.get("repoSlug", "")
    application_link = _repository_application_link(repository_payload)
    repositories = list(project.repositories.all())

    current_repository = next((repo for repo in repositories if repo.repo_slug == repo_slug), None)
    if current_repository is None:
        current_repository = next((repo for repo in repositories if repo.is_representative), None)
    if current_repository is None and repositories:
        current_repository = repositories[0]

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
            "applicationLink": application_link,
            "linkageMode": repository_payload.get("linkageMode", "linked"),
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
            "BITBUCKET_APPLICATION_LINK": application_link,
            "REPRESENTATIVE_REPO_SLUG": project.representative_repo_slug,
            "COVERITY_PROJECT": current_repository.coverity_project if current_repository else "",
            "COVERITY_STREAM": current_repository.coverity_stream if current_repository else "",
            "PROJECT_BUILD_NAME": project_build.build_name,
            "PROJECT_BUILD_TYPE": project_build.build_type,
        },
    }


def get_build_plan_preview(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project", "project_build__repository")
            .prefetch_related("definitions", "build_infos", "build_infos__executions")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    active_definition = _resolve_active_definition(plan)
    definition_payload = active_definition.definition_json if active_definition else {}
    repository_payload = definition_payload.get("repository", {})
    requirements_payload = definition_payload.get("requirements", {})
    build_payload = definition_payload.get("build", {})
    static_analysis_payload = build_payload.get("staticAnalysis", {})
    custom_tool_payload = static_analysis_payload.get("customTool", {})
    runtime_requirements_payload = build_payload.get("runtimeRequirements", {})
    post_build_trigger_payload = build_payload.get("postBuildTrigger", {})
    repository = getattr(plan.project_build, "repository", None)
    project = plan.project_build.project
    build_infos = list(plan.build_infos.all().order_by("build_key"))

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
        "repositorySlug": repository.repo_slug if repository else repository_payload.get("repoSlug", ""),
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
        operating_system = build_info.operating_system or requirements_payload.get("os", "")
        build_command = build_info.build_command or build_payload.get("buildCommand", "")
        pre_process = build_info.pre_process or build_payload.get("prepareCommand", "")
        clean_command = build_info.clean_command
        language = build_info.language or definition_payload.get("language", "")
        compiler = build_info.compiler or definition_payload.get("compiler", "")
        has_build_stage = not (
            is_no_build_language(language=language, compiler=compiler)
            and not build_command.strip()
            and not clean_command.strip()
            and not pre_process.strip()
        )
        coverity_stream = build_info.coverity_stream or (repository.coverity_stream if repository else "")
        analysis_excluded_files = build_info.analysis_excluded_files
        custom_commands = list(custom_tool_payload.get("commands", []))
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
                "buildSubPath": build_info.build_sub_path or build_payload.get("subPath", "."),
                "analysisExcludedFiles": analysis_excluded_files,
                "repositorySlug": repository.repo_slug if repository else repository_payload.get("repoSlug", ""),
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
                                        "detail": f"{project.bitbucket_project_key}/{repository.repo_slug}" if repository else "Repository 미연결",
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
                                "detail": f"{project.bitbucket_project_key}/{repository.repo_slug}" if repository else "Repository 미연결",
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
                        "value": (
                            "빌드 정보"
                            if build_info.operating_system or build_info.language or build_info.compiler
                            else "정의 데이터"
                        ),
                    },
                    {
                        "label": "명령어",
                        "value": (
                            "빌드 정보"
                            if build_info.pre_process or build_info.build_command or build_info.clean_command
                            else "정의 데이터"
                        ),
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
        "repositorySlug": repository.repo_slug if repository else repository_payload.get("repoSlug", ""),
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
                        "detail": post_build_trigger_payload.get("targetPlanKey", "") or "미지정",
                    }
                ],
            }
        ],
        "sourceSummary": [
            {"label": "트리거", "value": "정의 데이터"},
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
            "definitionVersion": active_definition.definition_hash if active_definition else "",
            "definitionYear": active_definition.year if active_definition else "",
            "definitionConnected": active_definition is not None,
        },
        "repository": {
            "provider": repository_payload.get("provider", "bitbucket"),
            "projectKey": repository_payload.get("projectKey", project.bitbucket_project_key),
            "repoSlug": repository_payload.get("repoSlug", repository.repo_slug if repository else ""),
            "linkageMode": repository_payload.get("linkageMode", "linked"),
            "applicationLink": _repository_application_link(repository_payload),
            "branches": list(repository_payload.get("branches", ["dev", "release", "master"])),
        },
        "requirements": {
            "extraCapabilities": list(requirements_payload.get("extraCapabilities", [])),
            "runtimeCommands": list(runtime_requirements_payload.get("commands", [])),
            "runtimeEnvVars": list(runtime_requirements_payload.get("envVars", [])),
        },
        "stages": stages,
        "jobs": [prepare_job] + jobs + [trigger_job],
        "staticAnalysis": {
            "customToolCommands": list(custom_tool_payload.get("commands", [])),
            "postBuildTriggerType": post_build_trigger_payload.get("type", ""),
            "postBuildTriggerTargetPlanKey": post_build_trigger_payload.get("targetPlanKey", ""),
        },
    }


def get_build_plan_export_draft(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project", "project_build__repository")
            .prefetch_related("definitions", "build_infos")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    preview = get_build_plan_preview(plan_key)
    active_definition = _resolve_active_definition(plan)
    files: list[dict] = []
    build_infos = list(plan.build_infos.all().order_by("build_key"))

    files.append(
        {
            "path": f"drafts/{plan.plan_key}/plan-preview.json",
            "label": "Plan Preview JSON",
            "language": "json",
            "content": json.dumps(preview or {}, ensure_ascii=False, indent=2) + "\n",
        }
    )

    for build_info in build_infos:
        build_definition = _build_definition_for_export(plan=plan, build_info=build_info, active_definition=active_definition)
        has_build_stage = not (
            is_no_build_language(language=build_definition.language, compiler=build_definition.compiler)
            and not build_definition.build.prepare_command.strip()
            and not build_definition.build.build_command.strip()
            and not build_info.clean_command.strip()
        )
        manifest_payload = {
            "planKey": plan.plan_key,
            "buildId": plan.build_id,
            "jobKey": build_info.build_key,
            "language": build_definition.language,
            "compiler": build_definition.compiler,
            "operatingSystem": build_definition.requirements.os,
            "hasBuildStage": has_build_stage,
            "subPath": build_definition.build.sub_path,
            "prepareCommand": build_definition.build.prepare_command,
            "buildCommand": build_definition.build.build_command,
            "cleanCommand": build_info.clean_command,
            "coverityStream": build_info.coverity_stream,
            "analysisExcludedFiles": build_info.analysis_excluded_files,
        }
        files.append(
            {
                "path": f"drafts/{plan.plan_key}/jobs/{build_info.build_key}/manifest.json",
                "label": f"{build_info.build_key} manifest",
                "language": "json",
                "content": json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
            }
        )
        files.append(
            {
                "path": f"drafts/{plan.plan_key}/jobs/{build_info.build_key}/coverity.yaml",
                "label": f"{build_info.build_key} coverity",
                "language": "yaml",
                "content": generate_coverity_yaml(build_definition),
            }
        )
        python_scripts = render_python_scripts(build_definition)
        launcher_scripts = render_python_launcher_scripts(build_definition)
        script_names = ["prepare_build.py"]
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
        launcher_name = "run_build.bat" if build_definition.requirements.os.lower() == "windows" else "run_build.sh"
        if has_build_stage and launcher_name in launcher_scripts:
            files.append(
                {
                    "path": f"drafts/{plan.plan_key}/jobs/{build_info.build_key}/{launcher_name}",
                    "label": f"{build_info.build_key} launcher",
                    "language": "shell" if launcher_name.endswith(".sh") else "batch",
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


def _build_definition_for_export(*, plan: BuildPlan, build_info, active_definition):
    project = plan.project_build.project
    repository = getattr(plan.project_build, "repository", None)
    base_payload = _default_definition_payload(plan)
    if active_definition is not None:
        base_payload = copy.deepcopy(active_definition.definition_json)

    base_payload["buildId"] = plan.build_id
    base_payload["name"] = f"{plan.project_build.build_name} {build_info.build_key}".strip()
    base_payload["planKey"] = plan.plan_key
    base_payload["language"] = build_info.language or base_payload.get("language", "")
    base_payload["compiler"] = build_info.compiler or base_payload.get("compiler", "")

    repository_payload = base_payload.setdefault("repository", {})
    repository_payload["provider"] = repository_payload.get("provider", "bitbucket")
    repository_payload["projectKey"] = repository_payload.get("projectKey") or project.bitbucket_project_key
    repository_payload["repoSlug"] = repository_payload.get("repoSlug") or (repository.repo_slug if repository else "")
    repository_payload["linkageMode"] = repository_payload.get("linkageMode", "linked")
    repository_payload["applicationLink"] = repository_payload.get("applicationLink") or "BITBUCKET_SERVER"
    repository_payload["branches"] = list(repository_payload.get("branches", ["dev", "release", "master"]))

    requirements_payload = base_payload.setdefault("requirements", {})
    requirements_payload["os"] = build_info.operating_system or requirements_payload.get("os", "linux")
    requirements_payload["extraCapabilities"] = list(requirements_payload.get("extraCapabilities", []))

    build_payload = base_payload.setdefault("build", {})
    build_payload["subPath"] = build_info.build_sub_path or build_payload.get("subPath", ".")
    build_payload["prepareCommand"] = build_info.pre_process or build_payload.get("prepareCommand", "")
    build_payload["buildCommand"] = build_info.build_command or build_payload.get("buildCommand", "")
    build_payload.setdefault("staticAnalysis", {})
    build_payload["staticAnalysis"].setdefault("customTool", {})
    build_payload["staticAnalysis"]["customTool"]["commands"] = list(
        build_payload["staticAnalysis"]["customTool"].get("commands", [])
    )
    build_payload.setdefault("runtimeRequirements", {})
    build_payload["runtimeRequirements"]["commands"] = list(build_payload["runtimeRequirements"].get("commands", []))
    build_payload["runtimeRequirements"]["envVars"] = list(build_payload["runtimeRequirements"].get("envVars", []))
    build_payload.setdefault("postBuildTrigger", {})
    build_payload["postBuildTrigger"]["type"] = build_payload["postBuildTrigger"].get("type", "plan")
    build_payload["postBuildTrigger"]["targetPlanKey"] = build_payload["postBuildTrigger"].get("targetPlanKey", "")

    year = active_definition.year if active_definition is not None else "2026"
    return parse_build_definition_payload(base_payload, year=year)


def _default_definition_payload(plan: BuildPlan) -> dict:
    project = plan.project_build.project
    repository = getattr(plan.project_build, "repository", None)
    return {
        "buildId": plan.build_id,
        "name": plan.project_build.build_name,
        "planKey": plan.plan_key,
        "description": plan.project_build.build_name,
        "language": plan.project_build.runtime_stack or "",
        "compiler": plan.project_build.build_type or "",
        "repository": {
            "provider": "bitbucket",
            "projectKey": project.bitbucket_project_key,
            "repoSlug": repository.repo_slug if repository else "",
            "linkageMode": "linked",
            "applicationLink": "BITBUCKET_SERVER",
            "branches": ["dev", "release", "master"],
        },
        "requirements": {"os": "linux", "extraCapabilities": []},
        "build": {
            "subPath": ".",
            "prepareCommand": "",
            "buildCommand": "",
            "staticAnalysis": {"customTool": {"commands": []}},
            "runtimeRequirements": {"commands": [], "envVars": []},
            "postBuildTrigger": {"type": "plan", "targetPlanKey": ""},
        },
    }
