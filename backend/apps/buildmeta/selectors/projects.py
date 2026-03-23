from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from apps.buildmeta.models import Project


def _project_queryset():
    return Project.objects.prefetch_related(
        "repositories",
        "builds__repository",
        "builds__build_plan__build_infos",
        "builds__build_plan__latest_version__latest_execution",
    )


def list_project_summaries() -> list[dict]:
    summaries = []
    projects = _project_queryset().all().order_by("jira_project_key")
    for project in projects:
        repositories = list(project.repositories.all())
        builds = list(project.builds.all())
        repository_count = len(repositories)
        build_count = len(builds)
        representative_repo_slug = project.representative_repo_slug
        generation_status = _build_generation_status(project, repositories, builds)
        missing_coverity_count = sum(
            1
            for repo in repositories
            if not repo.coverity_project or not repo.coverity_stream
        )
        failed_build_count = sum(
            1
            for build in builds
            if build.build_plan.latest_version is not None and build.build_plan.latest_version.latest_success is False
        )

        warning_tags = []
        if not representative_repo_slug:
            warning_tags.append("대표 저장소 없음")
        if repository_count == 0:
            warning_tags.append("저장소 없음")
        if build_count == 0:
            warning_tags.append("빌드 없음")
        for issue in generation_status["generationReadinessIssues"]:
            if issue not in warning_tags:
                warning_tags.append(issue)
        if missing_coverity_count:
            warning_tags.append(f"Coverity 미지정 {missing_coverity_count}")
        if failed_build_count:
            warning_tags.append(f"마지막 빌드 실패 {failed_build_count}")

        summaries.append(
            {
                "jiraProjectKey": project.jira_project_key,
                "bitbucketProjectKey": project.bitbucket_project_key,
                "representativeRepoSlug": representative_repo_slug,
                "repositoryCount": repository_count,
                "repositorySlugs": [repo.repo_slug for repo in sorted(repositories, key=lambda item: item.repo_slug)],
                "buildCount": build_count,
                "readyBuildCount": generation_status["readyBuildCount"],
                "generationReady": generation_status["generationReady"],
                "generationReadinessIssues": generation_status["generationReadinessIssues"],
                "missingCoverityCount": missing_coverity_count,
                "failedBuildCount": failed_build_count,
                "warningTags": warning_tags,
                "metadataWarningTags": [
                    tag
                    for tag in warning_tags
                    if not tag.startswith("마지막 빌드 실패")
                ],
                "needsAttention": bool(warning_tags),
            }
        )
    return summaries


def get_project_detail(jira_project_key: str) -> dict | None:
    try:
        project = _project_queryset().get(jira_project_key=jira_project_key)
    except ObjectDoesNotExist:
        return None
    repositories = list(project.repositories.all())
    builds = list(project.builds.all())
    generation_status = _build_generation_status(project, repositories, builds)
    return {
        "jiraProjectKey": project.jira_project_key,
        "bitbucketProjectKey": project.bitbucket_project_key,
        "representativeRepoSlug": project.representative_repo_slug,
        "updatedAt": project.updated_at,
        "generation": generation_status,
        "repositories": [
            {
                "repoSlug": repo.repo_slug,
                "coverityProject": repo.coverity_project,
                "coverityStream": repo.coverity_stream,
                "isRepresentative": repo.is_representative,
            }
            for repo in project.repositories.all().order_by("repo_slug")
        ],
        "builds": [
            {
                "buildName": build.build_name,
                "buildType": build.build_type,
                "runtimeStack": build.runtime_stack,
                "repositorySlug": build.repository.repo_slug if build.repository_id else "",
                "planKey": build.build_plan.plan_key,
                "buildId": build.build_plan.build_id,
                "generationReady": bool(build.repository_id),
                "staticAnalysisToolVersion": build.build_plan.static_analysis_tool_version,
                "coverityProject": build.build_plan.coverity_project,
                "buildInfoCount": build.build_plan.build_infos.count(),
                "latestVersion": (
                    build.build_plan.latest_version.version_text
                    if build.build_plan.latest_version is not None
                    else ""
                ),
                "latestSuccess": (
                    build.build_plan.latest_version.latest_success
                    if build.build_plan.latest_version is not None
                    else None
                ),
                "buildInfoUrl": f"/projects/{project.jira_project_key}/builds/{build.build_plan.plan_key}/infos/",
            }
            for build in sorted(builds, key=lambda item: item.build_name)
        ],
    }


def _build_generation_status(project: Project, repositories: list, builds: list) -> dict:
    issues: list[str] = []
    if not repositories:
        issues.append("저장소 없음")
    if not builds:
        issues.append("빌드 없음")
    if not project.representative_repo_slug:
        issues.append("대표 저장소 없음")
    elif all(repo.repo_slug != project.representative_repo_slug for repo in repositories):
        issues.append("대표 저장소 메타데이터 불일치")

    unlinked_build_count = 0
    for build in builds:
        if build.repository_id is None:
            unlinked_build_count += 1
    if unlinked_build_count:
        issues.append(f"저장소 연결 없는 빌드 {unlinked_build_count}")

    return {
        "generationReady": bool(builds) and not issues,
        "generationReadinessIssues": issues,
        "readyBuildCount": len(builds) - unlinked_build_count,
        "totalBuildCount": len(builds),
    }
