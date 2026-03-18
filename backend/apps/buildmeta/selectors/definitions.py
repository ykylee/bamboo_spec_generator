from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.buildmeta.models import BuildPlan


def get_active_definition_by_plan_key(plan_key: str) -> dict | None:
    try:
        plan = BuildPlan.objects.select_related("active_definition").get(plan_key=plan_key)
    except ObjectDoesNotExist:
        return None
    if plan.active_definition is None:
        return None
    payload = dict(plan.active_definition.definition_json)
    return {
        "planKey": plan.plan_key,
        "buildId": plan.build_id,
        "year": str(payload.get("year", "")),
        "definitionVersion": plan.active_definition.definition_hash,
        "definition": payload,
    }


def get_prepare_context_by_plan_key(plan_key: str) -> dict | None:
    try:
        plan = (
            BuildPlan.objects.select_related("project_build__project", "active_definition")
            .prefetch_related("project_build__project__repositories")
            .get(plan_key=plan_key)
        )
    except ObjectDoesNotExist:
        return None

    if not hasattr(plan, "project_build"):
        return None

    project_build = plan.project_build
    project = project_build.project
    definition_payload = plan.active_definition.definition_json if plan.active_definition else {}
    repository_payload = definition_payload.get("repository", {})
    repo_slug = repository_payload.get("repoSlug", "")
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
            "REPRESENTATIVE_REPO_SLUG": project.representative_repo_slug,
            "COVERITY_PROJECT": current_repository.coverity_project if current_repository else "",
            "COVERITY_STREAM": current_repository.coverity_stream if current_repository else "",
            "PROJECT_BUILD_NAME": project_build.build_name,
            "PROJECT_BUILD_TYPE": project_build.build_type,
        },
    }
