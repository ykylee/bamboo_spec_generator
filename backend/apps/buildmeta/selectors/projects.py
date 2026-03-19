from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import Project


def list_project_summaries() -> list[dict]:
    summaries = []
    projects = (
        Project.objects.prefetch_related(
            "repositories",
            "builds__build_plan__latest_version",
        )
        .all()
        .order_by("jira_project_key")
    )
    for project in projects:
        repositories = list(project.repositories.all())
        builds = list(project.builds.all())
        repository_count = len(repositories)
        build_count = len(builds)
        representative_repo_slug = project.representative_repo_slug
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
                "buildCount": build_count,
                "missingCoverityCount": missing_coverity_count,
                "failedBuildCount": failed_build_count,
                "warningTags": warning_tags,
                "metadataWarningTags": [tag for tag in warning_tags if not tag.startswith("마지막 빌드 실패")],
                "needsAttention": bool(warning_tags),
            }
        )
    return summaries


def get_project_detail(jira_project_key: str) -> dict | None:
    try:
        project = Project.objects.prefetch_related("repositories", "builds__build_plan").get(jira_project_key=jira_project_key)
    except ObjectDoesNotExist:
        return None
    return {
        "jiraProjectKey": project.jira_project_key,
        "bitbucketProjectKey": project.bitbucket_project_key,
        "representativeRepoSlug": project.representative_repo_slug,
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
                "planKey": build.build_plan.plan_key,
            }
            for build in project.builds.all().order_by("build_name")
        ],
    }
