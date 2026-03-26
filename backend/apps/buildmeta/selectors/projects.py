from __future__ import annotations

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

from apps.buildmeta.models import BuildUnit, Project


def _project_queryset():
    return Project.objects.prefetch_related(
        "repositories",
        "build_units__repository",
        "build_units__bamboo",
        "build_units__jenkins",
        "build_units__versions__latest_execution",
    )


def list_project_summaries(*, ci_provider: str | None = None) -> list[dict]:
    summaries = []
    projects = _project_queryset().all().order_by("ci_provider", "project_key")
    if ci_provider:
        projects = projects.filter(ci_provider=ci_provider)
    for project in projects:
        repositories = list(project.repositories.all())
        build_units = list(project.build_units.all())
        generation_status = _build_generation_status(project, repositories, build_units)
        missing_coverity_count = sum(
            1 for repo in repositories if not repo.coverity_project or not repo.coverity_stream
        )
        failed_build_count = sum(
            1 for build_unit in build_units if build_unit.latest_version is not None and build_unit.latest_version.latest_success is False
        )
        representative_repo_slug = project.representative_repository.repo_slug if project.representative_repository_id else ""
        representative_repo_key = project.representative_repository.repo_key if project.representative_repository_id else ""
        warning_tags = list(generation_status["generationReadinessIssues"])
        if missing_coverity_count:
            warning_tags.append(f"Coverity 미지정 {missing_coverity_count}")
        if failed_build_count:
            warning_tags.append(f"마지막 빌드 실패 {failed_build_count}")

        summaries.append(
            {
                "projectKey": project.project_key,
                "name": project.name,
                "description": project.description,
                "ownerTeam": project.owner_team,
                "serviceType": project.service_type,
                "ciProvider": project.ci_provider,
                "status": project.status,
                "representativeRepoSlug": representative_repo_slug,
                "repositoryCount": len(repositories),
                "repositorySlugs": [repo.repo_slug for repo in sorted(repositories, key=lambda item: item.repo_slug)],
                "buildUnitCount": len(build_units),
                "buildCount": len(build_units),
                "generationReady": generation_status["generationReady"],
                "generationReadinessIssues": generation_status["generationReadinessIssues"],
                "readyBuildCount": generation_status["readyBuildCount"],
                "activeDefinitionCount": generation_status["activeDefinitionCount"],
                "missingCoverityCount": missing_coverity_count,
                "failedBuildCount": failed_build_count,
                "warningTags": warning_tags,
                "metadataWarningTags": warning_tags,
                "needsAttention": bool(warning_tags),
                "jiraProjectKey": project.project_key,
                "bitbucketProjectKey": representative_repo_key,
            }
        )
    return summaries


def get_project_detail(project_key: str, *, ci_provider: str | None = None) -> dict | None:
    queryset = _project_queryset()
    if ci_provider:
        queryset = queryset.filter(ci_provider=ci_provider)
    try:
        project = queryset.get(project_key=project_key)
    except MultipleObjectsReturned:
        project = queryset.filter(project_key=project_key).order_by("ci_provider", "project_key").first()
        if project is None:
            return None
    except ObjectDoesNotExist:
        return None

    repositories = list(project.repositories.all())
    build_units = list(project.build_units.all())
    generation_status = _build_generation_status(project, repositories, build_units)
    representative_repo_slug = project.representative_repository.repo_slug if project.representative_repository_id else ""
    representative_repo_key = project.representative_repository.repo_key if project.representative_repository_id else ""

    return {
        "projectKey": project.project_key,
        "name": project.name,
        "description": project.description,
        "ownerTeam": project.owner_team,
        "serviceType": project.service_type,
        "ciProvider": project.ci_provider,
        "status": project.status,
        "updatedAt": project.updated_at,
        "representativeRepoSlug": representative_repo_slug,
        "generation": generation_status,
        "repositories": [
            {
                "repoSlug": repo.repo_slug,
                "repositoryType": repo.repository_type,
                "repositoryProvider": repo.repository_provider,
                "repoType": repo.repo_type,
                "repoKey": repo.repo_key,
                "cloneUrl": repo.clone_url,
                "defaultBranch": repo.default_branch,
                "coverityProject": repo.coverity_project,
                "coverityStream": repo.coverity_stream,
                "isRepresentative": repo.is_representative,
            }
            for repo in sorted(repositories, key=lambda item: item.repo_slug)
        ],
        "buildUnits": [_serialize_build_unit(build_unit) for build_unit in sorted(build_units, key=lambda item: item.display_name)],
        "jiraProjectKey": project.project_key,
        "bitbucketProjectKey": representative_repo_key,
        "builds": [_serialize_legacy_build(build_unit) for build_unit in sorted(build_units, key=lambda item: item.display_name)],
    }


def _serialize_build_unit(build_unit: BuildUnit) -> dict:
    provider_details: dict = {}
    if build_unit.ci_provider == Project.PROVIDER_BAMBOO and hasattr(build_unit, "bamboo"):
        provider_details = {
            "planKey": build_unit.bamboo.plan_key,
            "buildId": build_unit.bamboo.build_id,
            "bambooProjectKey": build_unit.bamboo.bamboo_project_key,
        }
    elif build_unit.ci_provider == Project.PROVIDER_JENKINS and hasattr(build_unit, "jenkins"):
        provider_details = {
            "jobPath": build_unit.jenkins.job_path,
            "jobType": build_unit.jenkins.job_type,
            "folderPath": build_unit.jenkins.folder_path,
            "pipelineKind": build_unit.jenkins.pipeline_kind,
        }
    return {
        "externalKey": build_unit.external_key,
        "displayName": build_unit.display_name,
        "description": build_unit.description,
        "unitType": build_unit.unit_type,
        "repositorySlug": build_unit.repository.repo_slug if build_unit.repository_id else "",
        "language": build_unit.language,
        "compiler": build_unit.compiler,
        "runtimeStack": build_unit.runtime_stack,
        "lifecycleStatus": build_unit.lifecycle_status,
        "isEnabled": build_unit.is_enabled,
        "latestVersion": build_unit.latest_version.version_text if build_unit.latest_version_id else "",
        "latestSuccess": build_unit.latest_version.latest_success if build_unit.latest_version_id else None,
        "providerDetails": provider_details,
    }


def _serialize_legacy_build(build_unit: BuildUnit) -> dict:
    provider_details = _serialize_build_unit(build_unit)["providerDetails"]
    detail_url = ""
    if build_unit.ci_provider == Project.PROVIDER_JENKINS:
        detail_url = f"/projects/{build_unit.project.project_key}/jenkins-jobs/{provider_details.get('jobPath', build_unit.external_key)}/"
    else:
        detail_url = f"/projects/{build_unit.project.project_key}/builds/{provider_details.get('planKey', build_unit.external_key)}/"
    return {
        "buildName": build_unit.display_name,
        "buildType": build_unit.compiler,
        "runtimeStack": build_unit.runtime_stack,
        "repositorySlug": build_unit.repository.repo_slug if build_unit.repository_id else "",
        "planKey": provider_details.get("planKey", build_unit.external_key),
        "buildId": provider_details.get("buildId", build_unit.external_key),
        "jobPath": provider_details.get("jobPath", build_unit.external_key),
        "jobType": provider_details.get("jobType", ""),
        "folderPath": provider_details.get("folderPath", ""),
        "pipelineKind": provider_details.get("pipelineKind", ""),
        "externalKey": build_unit.external_key,
        "generationReady": True,
        "activeDefinitionYear": "",
        "staticAnalysisToolVersion": getattr(getattr(build_unit, "bamboo", None), "static_analysis_tool_version", ""),
        "coverityProject": getattr(getattr(build_unit, "bamboo", None), "coverity_project", ""),
        "repositoryLinkageModeOverride": getattr(getattr(build_unit, "bamboo", None), "repository_linkage_mode", ""),
        "buildInfoCount": getattr(getattr(build_unit, "bamboo", None), "build_infos", []).count() if hasattr(getattr(build_unit, "bamboo", None), "build_infos") else 0,
        "latestVersion": build_unit.latest_version.version_text if build_unit.latest_version_id else "",
        "latestSuccess": build_unit.latest_version.latest_success if build_unit.latest_version_id else None,
        "buildInfoUrl": "",
        "detailUrl": detail_url,
        "ciProvider": build_unit.ci_provider,
    }


def _build_generation_status(project: Project, repositories: list, build_units: list) -> dict:
    issues: list[str] = []
    if not repositories:
        issues.append("저장소 없음")
    if not build_units:
        issues.append("빌드 단위 없음")
    if not project.representative_repository_id:
        issues.append("대표 저장소 메타데이터 불일치" if repositories else "대표 저장소 없음")

    unlinked_build_count = sum(1 for build_unit in build_units if build_unit.repository_id is None)
    if project.ci_provider == Project.PROVIDER_BAMBOO:
        builds_without_definition = sum(
            1
            for build_unit in build_units
            if not hasattr(build_unit, "bamboo") or not build_unit.bamboo.build_infos.exists()
        )
        missing_message = "빌드 정보 없음"
    else:
        builds_without_definition = sum(1 for build_unit in build_units if not build_unit.definitions.filter(is_active=True).exists())
        missing_message = "활성 정의 없음"
    if unlinked_build_count:
        issues.append(f"저장소 연결 없는 빌드 단위 {unlinked_build_count}")
    if builds_without_definition:
        issues.append(f"{missing_message} {builds_without_definition}")

    return {
        "generationReady": bool(build_units) and not issues,
        "generationReadinessIssues": issues,
        "readyBuildCount": len(build_units) - unlinked_build_count - builds_without_definition,
        "activeDefinitionCount": sum(build_unit.definitions.filter(is_active=True).count() for build_unit in build_units),
        "totalBuildCount": len(build_units),
    }
