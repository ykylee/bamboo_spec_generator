from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import Project


def list_project_summaries() -> list[dict]:
    return [
        {
            "jiraProjectKey": project.jira_project_key,
            "bitbucketProjectKey": project.bitbucket_project_key,
            "representativeRepoSlug": project.representative_repo_slug,
            "repositoryCount": project.repositories.count(),
            "buildCount": project.builds.count(),
        }
        for project in Project.objects.prefetch_related("repositories", "builds").all().order_by("jira_project_key")
    ]


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
