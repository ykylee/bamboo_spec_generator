from __future__ import annotations

import uuid

from apps.buildmeta.models import (
    AuditEvent,
    BambooBuildInfo,
    BambooBuildUnit,
    BambooPublishExecution as BambooPublishExecutionModel,
    BuildUnit as BuildUnitModel,
    BuildUnitDefinition as BuildUnitDefinitionModel,
    Project as ProjectModel,
    Repository as RepositoryModel,
)


def _translate_lookup(key: str) -> str:
    replacements = {
        "jira_project_key": "project_key",
        "project__jira_project_key": "project__project_key",
        "build_plan__plan_key": "build_unit__bamboo__plan_key",
        "build_plan__build_id": "build_unit__bamboo__build_id",
        "build_plan": "build_unit",
        "plan_key": "bamboo__plan_key",
        "build_id": "bamboo__build_id",
        "build_plan_definition": "target_id",
        "change_type": "event_type",
    }
    if key in replacements:
        return replacements[key]
    for source, target in replacements.items():
        if key.startswith(source + "__"):
            return target + key[len(source):]
    return key


def _translate_kwargs(kwargs: dict) -> dict:
    return {_translate_lookup(key): value for key, value in kwargs.items()}


def _translate_project_build_kwargs(kwargs: dict) -> dict:
    translated = {}
    for key, value in kwargs.items():
        if key == "build_plan":
            translated["pk"] = getattr(value, "pk", value)
        elif key == "build_plan__plan_key":
            translated["bamboo__plan_key"] = value
        else:
            translated[_translate_lookup(key)] = value
    return translated


def _translate_build_info_kwargs(kwargs: dict) -> dict:
    translated = {}
    for key, value in kwargs.items():
        if key == "build_plan":
            translated["bamboo_build_unit__build_unit"] = value
        elif key == "build_plan__plan_key":
            translated["bamboo_build_unit__plan_key"] = value
        else:
            translated[_translate_lookup(key)] = value
    return translated


def _translate_publish_execution_kwargs(kwargs: dict) -> dict:
    translated = {}
    for key, value in kwargs.items():
        if key == "build_plan":
            translated["build_unit"] = value
        else:
            translated[_translate_lookup(key)] = value
    return translated


def _placeholder_project() -> ProjectModel:
    project = ProjectModel.objects.create(
        project_key=f"DETACHED-{uuid.uuid4().hex[:8].upper()}",
        name="Detached",
        ci_provider=ProjectModel.PROVIDER_BAMBOO,
        status=ProjectModel.STATUS_ACTIVE,
    )
    return project


class _ProjectManager:
    def create(self, **kwargs):
        project = ProjectModel.objects.create(
            project_key=kwargs.get("jira_project_key", kwargs.get("project_key", "")),
            name=kwargs.get("jira_project_key", kwargs.get("project_key", "")),
            ci_provider=kwargs.get("ci_provider", ProjectModel.PROVIDER_BAMBOO),
            status=kwargs.get("status", ProjectModel.STATUS_ACTIVE),
        )
        project._legacy_representative_repo_slug = kwargs.get("representative_repo_slug", "")
        return project

    def get(self, **kwargs):
        return ProjectModel.objects.get(**_translate_kwargs(kwargs))

    def filter(self, **kwargs):
        return ProjectModel.objects.filter(**_translate_kwargs(kwargs))

    def all(self):
        return ProjectModel.objects.all()

    def count(self):
        return ProjectModel.objects.count()


class ProjectProxy:
    objects = _ProjectManager()


class _RepositoryManager:
    def create(self, **kwargs):
        is_representative = kwargs.get("is_representative", False)
        legacy_slug = getattr(kwargs["project"], "_legacy_representative_repo_slug", "")
        if legacy_slug and legacy_slug == kwargs["repo_slug"]:
            is_representative = True
        repository = RepositoryModel.objects.create(
            project=kwargs["project"],
            repo_type=kwargs.get("repo_type", RepositoryModel.TYPE_BITBUCKET),
            repo_key=kwargs.get("repo_key", kwargs.get("project").project_key),
            repo_slug=kwargs["repo_slug"],
            clone_url=kwargs.get("clone_url", ""),
            default_branch=kwargs.get("default_branch", ""),
            is_representative=is_representative,
            coverity_project=kwargs.get("coverity_project", ""),
            coverity_stream=kwargs.get("coverity_stream", ""),
        )
        if repository.is_representative:
            project = repository.project
            project.representative_repository = repository
            project.save(update_fields=["representative_repository", "updated_at"])
        return repository

    def get(self, **kwargs):
        return RepositoryModel.objects.get(**_translate_kwargs(kwargs))

    def filter(self, **kwargs):
        return RepositoryModel.objects.filter(**_translate_kwargs(kwargs))

    def all(self):
        queryset = RepositoryModel.objects.all()
        original_delete = queryset.delete

        def delete():
            project_ids = list(queryset.values_list("project_id", flat=True).distinct())
            ProjectModel.objects.filter(id__in=project_ids).update(representative_repository=None)
            return original_delete()

        queryset.delete = delete
        return queryset

    def count(self):
        return RepositoryModel.objects.count()


class ProjectRepositoryProxy:
    objects = _RepositoryManager()


class _BuildPlanManager:
    def create(self, **kwargs):
        project = kwargs.pop("project", None) or _placeholder_project()
        build_unit = BuildUnitModel.objects.create(
            project=project,
            repository=kwargs.pop("repository", None),
            ci_provider=ProjectModel.PROVIDER_BAMBOO,
            external_key=kwargs["plan_key"],
            display_name=kwargs.get("build_id", kwargs["plan_key"]),
            unit_type=BuildUnitModel.TYPE_BUILD,
            lifecycle_status=BuildUnitModel.STATUS_ACTIVE,
            is_enabled=True,
        )
        BambooBuildUnit.objects.create(
            build_unit=build_unit,
            bamboo_project_key=kwargs.get("bamboo_project_key", ""),
            plan_key=kwargs["plan_key"],
            build_id=kwargs["build_id"],
            repository_linkage_mode=kwargs.get("repository_linkage_mode_override", ""),
            static_analysis_tool_version=kwargs.get("static_analysis_tool_version", ""),
            coverity_project=kwargs.get("coverity_project", ""),
        )
        return build_unit

    def get(self, **kwargs):
        return BuildUnitModel.objects.get(**_translate_project_build_kwargs(kwargs))

    def filter(self, **kwargs):
        return BuildUnitModel.objects.filter(**_translate_project_build_kwargs(kwargs))

    def all(self):
        return BuildUnitModel.objects.all()

    def count(self):
        return BuildUnitModel.objects.count()

    def count(self):
        return BuildUnitModel.objects.count()


class BuildPlanProxy:
    objects = _BuildPlanManager()


class _ProjectBuildManager:
    def create(self, **kwargs):
        build_unit: BuildUnitModel = kwargs["build_plan"]
        previous_project = build_unit.project
        build_unit.project = kwargs["project"]
        build_unit.repository = kwargs.get("repository")
        build_unit.display_name = kwargs.get("build_name", build_unit.display_name)
        build_unit.compiler = kwargs.get("build_type", "")
        build_unit.runtime_stack = kwargs.get("runtime_stack", "")
        build_unit.language = kwargs.get("runtime_stack", "")
        build_unit.save()
        if previous_project.project_key.startswith("DETACHED-") and not previous_project.build_units.exclude(pk=build_unit.pk).exists():
            previous_project.delete()
        return build_unit

    def get(self, **kwargs):
        return BuildUnitModel.objects.get(**_translate_project_build_kwargs(kwargs))

    def filter(self, **kwargs):
        return BuildUnitModel.objects.filter(**_translate_project_build_kwargs(kwargs))

    def all(self):
        return BuildUnitModel.objects.all()

    def count(self):
        return BuildUnitModel.objects.count()


class ProjectBuildProxy:
    objects = _ProjectBuildManager()


class _BuildInfoManager:
    def create(self, **kwargs):
        build_plan: BuildUnitModel = kwargs["build_plan"]
        bamboo_unit = build_plan.bamboo
        return BambooBuildInfo.objects.create(
            bamboo_build_unit=bamboo_unit,
            build_key=kwargs["build_key"],
            operating_system=kwargs.get("operating_system", ""),
            pre_process=kwargs.get("pre_process", ""),
            build_command=kwargs.get("build_command", ""),
            clean_command=kwargs.get("clean_command", ""),
            language=kwargs.get("language", ""),
            compiler=kwargs.get("compiler", ""),
            analysis_excluded_files=kwargs.get("analysis_excluded_files", ""),
            coverity_stream=kwargs.get("coverity_stream", ""),
            build_sub_path=kwargs.get("build_sub_path", ""),
        )

    def get(self, **kwargs):
        return BambooBuildInfo.objects.get(**_translate_build_info_kwargs(kwargs))

    def filter(self, **kwargs):
        return BambooBuildInfo.objects.filter(**_translate_build_info_kwargs(kwargs))

    def all(self):
        return BambooBuildInfo.objects.all()


class BuildPlanBuildInfoProxy:
    objects = _BuildInfoManager()


class _DefinitionManager:
    SOURCE_KIND_JSON = BuildUnitDefinitionModel.SOURCE_JSON
    SOURCE_KIND_DB = BuildUnitDefinitionModel.SOURCE_API
    SOURCE_KIND_IMPORT = BuildUnitDefinitionModel.SOURCE_IMPORT

    def create(self, **kwargs):
        build_plan: BuildUnitModel = kwargs["build_plan"]
        return BuildUnitDefinitionModel.objects.create(
            build_unit=build_plan,
            version=kwargs.get("version", build_plan.definitions.count() + 1),
            year=kwargs.get("year", ""),
            source_kind=kwargs.get("source_kind", BuildUnitDefinitionModel.SOURCE_JSON),
            definition_json=kwargs.get("definition_json", {}),
            definition_hash=kwargs.get("definition_hash", ""),
            is_active=kwargs.get("is_active", False),
        )

    def get(self, **kwargs):
        return BuildUnitDefinitionModel.objects.get(**_translate_kwargs(kwargs))

    def filter(self, **kwargs):
        return BuildUnitDefinitionModel.objects.filter(**_translate_kwargs(kwargs))

    def all(self):
        return BuildUnitDefinitionModel.objects.all()

    def count(self):
        return BuildUnitDefinitionModel.objects.count()


class BuildPlanDefinitionProxy:
    SOURCE_KIND_JSON = BuildUnitDefinitionModel.SOURCE_JSON
    SOURCE_KIND_DB = BuildUnitDefinitionModel.SOURCE_API
    SOURCE_KIND_IMPORT = BuildUnitDefinitionModel.SOURCE_IMPORT
    objects = _DefinitionManager()


class _DefinitionHistoryManager:
    def filter(self, **kwargs):
        return AuditEvent.objects.filter(**_translate_kwargs(kwargs))

    def all(self):
        return AuditEvent.objects.all()

    def count(self):
        return AuditEvent.objects.count()


class BuildDefinitionHistoryProxy:
    objects = _DefinitionHistoryManager()


class _BambooPublishExecutionManager:
    STATUS_SUCCESS = BambooPublishExecutionModel.STATUS_SUCCESS
    STATUS_FAILED = BambooPublishExecutionModel.STATUS_FAILED

    def create(self, **kwargs):
        translated = _translate_publish_execution_kwargs(kwargs)
        return BambooPublishExecutionModel.objects.create(
            build_unit=translated["build_unit"],
            status=translated.get("status", ""),
            message=translated.get("message", ""),
            output=translated.get("output", ""),
            snapshot_preview_json=translated.get("snapshot_preview_json"),
            snapshot_export_draft_json=translated.get("snapshot_export_draft_json"),
            return_code=translated.get("return_code"),
        )

    def get(self, **kwargs):
        return BambooPublishExecutionModel.objects.get(**_translate_publish_execution_kwargs(kwargs))

    def filter(self, **kwargs):
        return BambooPublishExecutionModel.objects.filter(**_translate_publish_execution_kwargs(kwargs))


class BambooPublishExecutionProxy:
    STATUS_SUCCESS = BambooPublishExecutionModel.STATUS_SUCCESS
    STATUS_FAILED = BambooPublishExecutionModel.STATUS_FAILED
    objects = _BambooPublishExecutionManager()


Project = ProjectProxy
ProjectRepository = ProjectRepositoryProxy
BuildPlan = BuildPlanProxy
ProjectBuild = ProjectBuildProxy
BuildPlanBuildInfo = BuildPlanBuildInfoProxy
BuildPlanDefinition = BuildPlanDefinitionProxy
BuildDefinitionHistory = BuildDefinitionHistoryProxy
BambooPublishExecution = BambooPublishExecutionProxy
