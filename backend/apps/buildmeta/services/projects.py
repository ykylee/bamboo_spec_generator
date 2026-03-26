from __future__ import annotations

from dataclasses import asdict, is_dataclass

from django.db import transaction

from apps.buildmeta.models import (
    BambooBuildUnit,
    BuildUnit,
    JenkinsBuildUnit,
    Project,
    Repository,
)
from apps.buildmeta.selectors.projects import get_project_detail


def create_project(payload) -> dict:
    data = _coerce_payload(payload)
    project_key = _project_key(data)
    ci_provider = _ci_provider(data)
    if not project_key:
        raise ValueError("projectKey is required.")
    if Project.objects.filter(project_key=project_key, ci_provider=ci_provider).exists():
        raise ValueError(f"Project '{ci_provider}:{project_key}' already exists.")
    return _save_project(None, data)


def update_project(project_key: str, payload, *, ci_provider: str | None = None) -> dict | None:
    data = _coerce_payload(payload)
    provider = ci_provider or _ci_provider(data)
    project = Project.objects.filter(project_key=project_key, ci_provider=provider).first()
    if project is None:
        return None
    return _save_project(project, data)


def _save_project(existing_project: Project | None, data: dict) -> dict:
    repositories = _repositories(data)
    build_units = _build_units(data)
    _validate_repositories(repositories)
    _validate_build_units(build_units, repositories)

    with transaction.atomic():
        project = existing_project or Project(
            project_key=_project_key(data),
            ci_provider=_ci_provider(data),
        )
        project.name = _project_name(data)
        project.description = _value(data, "description")
        project.owner_team = _value(data, "ownerTeam")
        project.service_type = _value(data, "serviceType")
        project.status = _value(data, "status") or Project.STATUS_ACTIVE
        project.save()

        repository_map = _upsert_repositories(
            project,
            repositories,
            default_repo_key=_value(data, "bitbucketProjectKey"),
        )
        representative_repository = _resolve_representative_repository(project, repositories, repository_map)
        if project.representative_repository_id != getattr(representative_repository, "id", None):
            project.representative_repository = representative_repository
            project.save(update_fields=["representative_repository", "updated_at"])

        default_repo_key = _value(data, "bitbucketProjectKey").strip()
        if default_repo_key:
            for repository in repository_map.values():
                if repository.repo_key != default_repo_key:
                    repository.repo_key = default_repo_key
                    repository.save(update_fields=["repo_key", "updated_at"])

        _upsert_build_units(project, build_units, repository_map)
        _prune_removed_build_units(project, build_units)
        _prune_removed_repositories(project, repositories)

    payload = get_project_detail(project.project_key, ci_provider=project.ci_provider)
    if payload is None:
        raise ValueError(f"Project '{project.ci_provider}:{project.project_key}' could not be loaded after save.")
    return payload


def _coerce_payload(payload) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if is_dataclass(payload):
        return asdict(payload)
    return dict(payload)


def _project_key(data: dict) -> str:
    return (_value(data, "projectKey") or _value(data, "jiraProjectKey")).strip()


def _project_name(data: dict) -> str:
    return (_value(data, "name") or _project_key(data)).strip()


def _ci_provider(data: dict) -> str:
    provider = (_value(data, "ciProvider") or "").strip().lower()
    return provider or Project.PROVIDER_BAMBOO


def _repositories(data: dict) -> list[dict]:
    return list(data.get("repositories") or [])


def _build_units(data: dict) -> list[dict]:
    explicit = data.get("buildUnits")
    if explicit:
        return list(explicit)
    legacy = data.get("builds") or []
    units = []
    for build in legacy:
        provider_details = build.get("providerDetails") or {}
        plan_key = provider_details.get("planKey") or build.get("planKey", "")
        build_id = provider_details.get("buildId") or build.get("buildId", "")
        units.append(
            {
                "externalKey": build.get("externalKey", "") or plan_key,
                "displayName": build.get("buildName", ""),
                "unitType": "build",
                "repositorySlug": build.get("repositorySlug", ""),
                "language": build.get("runtimeStack", ""),
                "compiler": build.get("buildType", ""),
                "runtimeStack": build.get("runtimeStack", ""),
                "providerDetails": {
                    "planKey": plan_key,
                    "buildId": build_id,
                },
            }
        )
    return units


def _validate_repositories(repositories: list[dict]) -> None:
    seen_repo_slugs: set[str] = set()
    representative_count = 0
    for repository in repositories:
        repo_slug = _repo_slug(repository)
        if not repo_slug:
            raise ValueError("Repository repoSlug is required.")
        if repo_slug in seen_repo_slugs:
            raise ValueError(f"Repository '{repo_slug}' is duplicated in the request.")
        seen_repo_slugs.add(repo_slug)
        if bool(repository.get("isRepresentative")):
            representative_count += 1
    if representative_count > 1:
        raise ValueError("Only one representative repository can be provided per request.")


def _validate_build_units(build_units: list[dict], repositories: list[dict]) -> None:
    seen_external_keys: set[str] = set()
    seen_plan_keys: set[str] = set()
    seen_build_ids: set[str] = set()
    repository_slugs = {_repo_slug(repository) for repository in repositories}
    for build_unit in build_units:
        external_key = _value(build_unit, "externalKey").strip()
        display_name = _value(build_unit, "displayName").strip()
        repository_slug = _value(build_unit, "repositorySlug").strip()
        provider_details = build_unit.get("providerDetails") or {}
        plan_key = (_value(provider_details, "planKey") or external_key).strip()
        build_id = (_value(provider_details, "buildId") or external_key).strip()
        if not external_key:
            raise ValueError("Build externalKey is required.")
        if not display_name:
            raise ValueError("Build displayName is required.")
        if repository_slug and repository_slug not in repository_slugs:
            raise ValueError(f"Build repositorySlug '{repository_slug}' is not registered in repositories.")
        if external_key in seen_external_keys:
            raise ValueError(f"Build externalKey '{external_key}' is duplicated in the request.")
        if plan_key and plan_key in seen_plan_keys:
            raise ValueError(f"Build planKey '{plan_key}' is duplicated in the request.")
        if build_id and build_id in seen_build_ids:
            raise ValueError(f"Build buildId '{build_id}' is duplicated in the request.")
        seen_external_keys.add(external_key)
        seen_plan_keys.add(plan_key)
        seen_build_ids.add(build_id)


def _upsert_repositories(project: Project, repositories: list[dict], *, default_repo_key: str = "") -> dict[str, Repository]:
    repository_map: dict[str, Repository] = {}
    Repository.objects.filter(project=project, is_representative=True).update(is_representative=False)
    for repository in repositories:
        repo = Repository.objects.update_or_create(
            project=project,
            repo_slug=_repo_slug(repository),
            defaults={
                "repo_type": (_value(repository, "repoType") or Repository.TYPE_BITBUCKET).strip() or Repository.TYPE_BITBUCKET,
                "repo_key": (_value(repository, "repoKey") or _value(repository, "bitbucketProjectKey") or default_repo_key).strip(),
                "clone_url": _value(repository, "cloneUrl"),
                "default_branch": _value(repository, "defaultBranch"),
                "is_representative": bool(repository.get("isRepresentative")),
                "coverity_project": _value(repository, "coverityProject"),
                "coverity_stream": _value(repository, "coverityStream"),
            },
        )[0]
        repository_map[repo.repo_slug] = repo
    return repository_map


def _resolve_representative_repository(
    project: Project,
    repositories: list[dict],
    repository_map: dict[str, Repository],
) -> Repository | None:
    explicit_slug = (_value_from_any(repositories, "repoSlug", condition_key="isRepresentative") or "").strip()
    if explicit_slug:
        return repository_map.get(explicit_slug)
    if project.representative_repository_id:
        return project.representative_repository
    if repository_map:
        return next(iter(repository_map.values()))
    return None


def _upsert_build_units(
    project: Project,
    build_units: list[dict],
    repository_map: dict[str, Repository],
) -> None:
    for build_unit_data in build_units:
        external_key = _value(build_unit_data, "externalKey").strip()
        build_unit = BuildUnit.objects.filter(
            ci_provider=project.ci_provider,
            external_key=external_key,
        ).first()
        detached_project = None
        if build_unit is not None and build_unit.project_id != project.id:
            if _is_detached_placeholder_project(build_unit.project):
                detached_project = build_unit.project
            else:
                if project.ci_provider == Project.PROVIDER_BAMBOO:
                    raise ValueError(f"Build plan '{external_key}' is already linked to another project.")
                raise ValueError(f"BuildUnit '{project.ci_provider}:{external_key}' is already linked to another project.")
        if build_unit is None:
            build_unit = BuildUnit(project=project, ci_provider=project.ci_provider, external_key=external_key)

        repository_slug = _value(build_unit_data, "repositorySlug").strip()
        repository = repository_map.get(repository_slug) if repository_slug else None
        build_unit.project = project
        build_unit.repository = repository
        build_unit.unit_type = (_value(build_unit_data, "unitType") or BuildUnit.TYPE_BUILD).strip() or BuildUnit.TYPE_BUILD
        build_unit.display_name = _value(build_unit_data, "displayName").strip()
        build_unit.description = _value(build_unit_data, "description")
        build_unit.language = _value(build_unit_data, "language")
        build_unit.compiler = _value(build_unit_data, "compiler")
        build_unit.runtime_stack = _value(build_unit_data, "runtimeStack")
        build_unit.lifecycle_status = (_value(build_unit_data, "lifecycleStatus") or BuildUnit.STATUS_ACTIVE).strip() or BuildUnit.STATUS_ACTIVE
        build_unit.is_enabled = bool(build_unit_data.get("isEnabled", True))
        build_unit.save()

        provider_details = build_unit_data.get("providerDetails") or {}
        if project.ci_provider == Project.PROVIDER_JENKINS:
            JenkinsBuildUnit.objects.update_or_create(
                build_unit=build_unit,
                defaults={
                    "job_path": (_value(provider_details, "jobPath") or external_key).strip(),
                    "job_type": _value(provider_details, "jobType"),
                    "folder_path": _value(provider_details, "folderPath"),
                    "pipeline_kind": _value(provider_details, "pipelineKind"),
                },
            )
        elif project.ci_provider == Project.PROVIDER_BAMBOO:
            requested_plan_key = (_value(provider_details, "planKey") or external_key).strip()
            requested_build_id = (_value(provider_details, "buildId") or external_key).strip()
            try:
                current_bamboo = build_unit.bamboo
            except BambooBuildUnit.DoesNotExist:
                current_bamboo = None
            conflicting_bamboo_by_build_id = BambooBuildUnit.objects.filter(build_id=requested_build_id).exclude(build_unit=build_unit).first()
            if current_bamboo is not None and current_bamboo.plan_key == requested_plan_key and current_bamboo.build_id != requested_build_id:
                if conflicting_bamboo_by_build_id is not None:
                    raise ValueError(f"Build plan '{requested_plan_key}' and buildId '{requested_build_id}' refer to different existing build plans.")
                raise ValueError(f"Build plan '{requested_plan_key}' already exists with a different buildId.")
            if current_bamboo is not None and current_bamboo.build_id == requested_build_id and current_bamboo.plan_key != requested_plan_key:
                raise ValueError(f"Build buildId '{requested_build_id}' already exists with a different planKey.")
            conflicting_bamboo = BambooBuildUnit.objects.filter(plan_key=requested_plan_key).exclude(build_unit=build_unit).first()
            if conflicting_bamboo is not None:
                if conflicting_bamboo.build_id != requested_build_id:
                    raise ValueError(f"Build plan '{requested_plan_key}' and buildId '{requested_build_id}' refer to different existing build plans.")
                raise ValueError(f"Build plan '{requested_plan_key}' is already linked to another project.")
            conflicting_bamboo = conflicting_bamboo_by_build_id
            if conflicting_bamboo is not None:
                if conflicting_bamboo.plan_key != requested_plan_key:
                    raise ValueError(f"Build buildId '{requested_build_id}' already exists with a different planKey.")
                raise ValueError(f"Build plan '{requested_plan_key}' is already linked to another project.")
            BambooBuildUnit.objects.update_or_create(
                build_unit=build_unit,
                defaults={
                    "bamboo_project_key": _value(provider_details, "bambooProjectKey"),
                    "plan_key": requested_plan_key,
                    "build_id": requested_build_id,
                    "repository_linkage_mode": _value(provider_details, "repositoryLinkageMode"),
                    "application_link": _value(provider_details, "applicationLink"),
                    "static_analysis_tool_version": _value(provider_details, "staticAnalysisToolVersion"),
                    "coverity_project": _value(provider_details, "coverityProject"),
                },
            )
        if detached_project is not None and not detached_project.build_units.exclude(pk=build_unit.pk).exists():
            detached_project.delete()


def _is_detached_placeholder_project(project: Project) -> bool:
    return project.project_key.startswith("DETACHED-") and not project.repositories.exists()


def _prune_removed_build_units(project: Project, build_units: list[dict]) -> None:
    incoming_external_keys = {_value(build_unit, "externalKey").strip() for build_unit in build_units}
    stale_units = BuildUnit.objects.filter(project=project)
    if incoming_external_keys:
        stale_units = stale_units.exclude(external_key__in=incoming_external_keys)
    stale_units.delete()


def _prune_removed_repositories(project: Project, repositories: list[dict]) -> None:
    incoming_repo_slugs = {_repo_slug(repository) for repository in repositories}
    if project.representative_repository_id and project.representative_repository.repo_slug not in incoming_repo_slugs:
        project.representative_repository = None
        project.save(update_fields=["representative_repository", "updated_at"])
    stale_repositories = Repository.objects.filter(project=project)
    if incoming_repo_slugs:
        stale_repositories = stale_repositories.exclude(repo_slug__in=incoming_repo_slugs)
    stale_repositories.delete()


def _repo_slug(repository: dict) -> str:
    return _value(repository, "repoSlug").strip()


def _value(data: dict, key: str) -> str:
    value = data.get(key, "")
    return value.strip() if isinstance(value, str) else ("" if value is None else str(value))


def _value_from_any(items: list[dict], key: str, *, condition_key: str) -> str:
    for item in items:
        if item.get(condition_key):
            return _value(item, key)
    return ""
