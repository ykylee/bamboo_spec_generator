from __future__ import annotations

from dataclasses import asdict, is_dataclass

from django.db import transaction

from apps.buildmeta.models import BuildPlan, Project, ProjectBuild, ProjectRepository
from apps.buildmeta.selectors.projects import get_project_detail


def create_project(payload) -> dict:
    data = _coerce_payload(payload)
    jira_project_key = data["jiraProjectKey"].strip()
    if not jira_project_key:
        raise ValueError("jiraProjectKey is required.")
    if Project.objects.filter(jira_project_key=jira_project_key).exists():
        raise ValueError(f"Project '{jira_project_key}' already exists.")
    return _save_project(None, data)


def update_project(jira_project_key: str, payload) -> dict | None:
    data = _coerce_payload(payload)
    if not Project.objects.filter(jira_project_key=jira_project_key).exists():
        return None
    return _save_project(jira_project_key, data)


def _save_project(existing_jira_project_key: str | None, data: dict) -> dict:
    _validate_repositories(data["repositories"])
    _validate_builds(data["builds"])

    with transaction.atomic():
        project, _ = Project.objects.get_or_create(
            jira_project_key=existing_jira_project_key or data["jiraProjectKey"].strip(),
            defaults={
                "bitbucket_project_key": data["bitbucketProjectKey"].strip(),
                "representative_repo_slug": _resolve_representative_repo_slug(data),
            },
        )
        project.bitbucket_project_key = data["bitbucketProjectKey"].strip()
        project.representative_repo_slug = _resolve_representative_repo_slug(data, current_value=project.representative_repo_slug)
        project.save(update_fields=["bitbucket_project_key", "representative_repo_slug", "updated_at"])

        _upsert_repositories(project, data["repositories"])
        _upsert_builds(project, data["builds"])

    payload = get_project_detail(project.jira_project_key)
    if payload is None:
        raise ValueError(f"Project '{project.jira_project_key}' could not be loaded after save.")
    return payload


def _coerce_payload(payload) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if is_dataclass(payload):
        return asdict(payload)
    return dict(payload)


def _resolve_representative_repo_slug(data: dict, current_value: str = "") -> str:
    explicit_value = data["representativeRepoSlug"].strip()
    if explicit_value:
        return explicit_value
    representative_repositories = [repo["repoSlug"].strip() for repo in data["repositories"] if repo["isRepresentative"]]
    if representative_repositories:
        return representative_repositories[0]
    return current_value


def _validate_repositories(repositories: list[dict]) -> None:
    seen_repo_slugs: set[str] = set()
    representative_count = 0
    for repository in repositories:
        repo_slug = repository["repoSlug"].strip()
        if not repo_slug:
            raise ValueError("Repository repoSlug is required.")
        if repo_slug in seen_repo_slugs:
            raise ValueError(f"Repository '{repo_slug}' is duplicated in the request.")
        seen_repo_slugs.add(repo_slug)
        if repository["isRepresentative"]:
            representative_count += 1
    if representative_count > 1:
        raise ValueError("Only one representative repository can be provided per request.")


def _validate_builds(builds: list[dict]) -> None:
    seen_plan_keys: set[str] = set()
    seen_build_ids: set[str] = set()
    for build in builds:
        build_name = build["buildName"].strip()
        build_id = build["buildId"].strip()
        plan_key = build["planKey"].strip()
        if not build_name:
            raise ValueError("Build buildName is required.")
        if not build_id:
            raise ValueError("Build buildId is required.")
        if not plan_key:
            raise ValueError("Build planKey is required.")
        if plan_key in seen_plan_keys:
            raise ValueError(f"Build planKey '{plan_key}' is duplicated in the request.")
        if build_id in seen_build_ids:
            raise ValueError(f"Build buildId '{build_id}' is duplicated in the request.")
        seen_plan_keys.add(plan_key)
        seen_build_ids.add(build_id)


def _upsert_repositories(project: Project, repositories: list[dict]) -> None:
    for repository in repositories:
        ProjectRepository.objects.update_or_create(
            project=project,
            repo_slug=repository["repoSlug"].strip(),
            defaults={
                "coverity_project": repository["coverityProject"].strip(),
                "coverity_stream": repository["coverityStream"].strip(),
                "is_representative": repository["isRepresentative"],
            },
        )


def _upsert_builds(project: Project, builds: list[dict]) -> None:
    for build in builds:
        build_id = build["buildId"].strip()
        plan_key = build["planKey"].strip()
        plan = BuildPlan.objects.filter(plan_key=plan_key).first()
        if plan is not None and plan.build_id != build_id:
            raise ValueError(f"Build plan '{plan_key}' already exists with a different buildId.")
        if plan is None:
            plan = BuildPlan.objects.create(build_id=build_id, plan_key=plan_key)

        project_build = ProjectBuild.objects.filter(build_plan=plan).first()
        if project_build is not None and project_build.project_id != project.id:
            raise ValueError(f"Build plan '{plan_key}' is already linked to another project.")

        if project_build is None:
            project_build = ProjectBuild(project=project, build_plan=plan)

        project_build.project = project
        project_build.build_name = build["buildName"].strip()
        project_build.build_type = build["buildType"].strip()
        project_build.runtime_stack = build["runtimeStack"].strip()
        project_build.save()
