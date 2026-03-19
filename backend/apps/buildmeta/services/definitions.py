from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from apps.buildmeta.models import (
    BuildDefinitionHistory,
    BuildPlan,
    BuildPlanDefinition,
    Project,
    ProjectBuild,
    ProjectRepository,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bamboo_spec_generator.parser import discover_input_files, parse_build_definition  # noqa: E402
from src.bamboo_spec_generator.validator import validate_build_definitions  # noqa: E402


@dataclass(frozen=True)
class DefinitionImportRecord:
    source_path: Path
    raw_definition: dict
    build_definition: object
    definition_hash: str


def load_definition_import_records(input_root: Path) -> list[DefinitionImportRecord]:
    input_files = discover_input_files(input_root)
    records: list[DefinitionImportRecord] = []
    parsed_builds = []

    for path in input_files:
        raw_definition = json.loads(path.read_text(encoding="utf-8"))
        build_definition = parse_build_definition(path)
        parsed_builds.append(build_definition)
        records.append(
            DefinitionImportRecord(
                source_path=path,
                raw_definition=raw_definition,
                build_definition=build_definition,
                definition_hash=_definition_hash(build_definition.year, raw_definition),
            )
        )

    validate_build_definitions(parsed_builds)
    return records


@transaction.atomic
def import_definition_records(records: list[DefinitionImportRecord], *, source_kind: str = BuildPlanDefinition.SOURCE_KIND_JSON) -> dict:
    imported_count = 0
    activated_count = 0

    for record in records:
        build = record.build_definition
        project = _upsert_project(record)
        repository = _upsert_repository(project, record)
        plan = _upsert_build_plan(record)
        _upsert_project_build(project, repository, plan, record)
        changed_active, definition = _activate_definition(
            plan=plan,
            project=project,
            record=record,
            source_kind=source_kind,
        )

        if changed_active:
            BuildDefinitionHistory.objects.create(
                build_plan=plan,
                build_plan_definition=definition,
                change_type="import",
                change_summary=f"Imported from {_display_source_path(record.source_path)}",
            )
            activated_count += 1

        imported_count += 1

    return {
        "importedCount": imported_count,
        "activatedCount": activated_count,
    }


@transaction.atomic
def sync_definition_records(
    records: list[DefinitionImportRecord],
    *,
    source_kind: str = BuildPlanDefinition.SOURCE_KIND_JSON,
    deactivate_missing: bool = False,
) -> dict:
    imported_count = 0
    activated_count = 0
    unchanged_count = 0
    deactivated_count = 0
    synced_plan_keys: set[str] = set()

    for record in records:
        build = record.build_definition
        project = _upsert_project(record)
        repository = _upsert_repository(project, record)
        plan = _upsert_build_plan(record)
        _upsert_project_build(project, repository, plan, record)
        synced_plan_keys.add(plan.plan_key)

        changed_active, definition = _activate_definition(
            plan=plan,
            project=project,
            record=record,
            source_kind=source_kind,
        )
        if changed_active:
            BuildDefinitionHistory.objects.create(
                build_plan=plan,
                build_plan_definition=definition,
                change_type="sync",
                change_summary=f"Synchronized from {_display_source_path(record.source_path)}",
            )
            activated_count += 1
        else:
            unchanged_count += 1
        imported_count += 1

    if deactivate_missing:
        active_definitions = (
            BuildPlanDefinition.objects.select_related("build_plan")
            .filter(is_active=True, source_kind=source_kind)
            .exclude(build_plan__plan_key__in=synced_plan_keys)
        )
        for definition in active_definitions:
            definition.is_active = False
            definition.save(update_fields=["is_active"])
            BuildDefinitionHistory.objects.create(
                build_plan=definition.build_plan,
                build_plan_definition=definition,
                change_type="deactivate",
                change_summary="Deactivated because the definition was missing from the latest sync input.",
            )
            deactivated_count += 1

    return {
        "importedCount": imported_count,
        "activatedCount": activated_count,
        "unchangedCount": unchanged_count,
        "deactivatedCount": deactivated_count,
    }


def _upsert_project(record: DefinitionImportRecord) -> Project:
    build = record.build_definition
    defaults = {
        "bitbucket_project_key": build.repository.project_key,
        "representative_repo_slug": build.repository.repo_slug,
    }
    project, created = Project.objects.get_or_create(
        jira_project_key=build.repository.project_key,
        defaults=defaults,
    )
    updated_fields: list[str] = []
    if not created and project.bitbucket_project_key != build.repository.project_key:
        project.bitbucket_project_key = build.repository.project_key
        updated_fields.append("bitbucket_project_key")
    if not project.representative_repo_slug:
        project.representative_repo_slug = build.repository.repo_slug
        updated_fields.append("representative_repo_slug")
    if updated_fields:
        project.save(update_fields=updated_fields + ["updated_at"])
    return project


def _upsert_repository(project: Project, record: DefinitionImportRecord) -> ProjectRepository:
    build = record.build_definition
    repository, created = ProjectRepository.objects.get_or_create(
        project=project,
        repo_slug=build.repository.repo_slug,
        defaults={"is_representative": project.representative_repo_slug == build.repository.repo_slug},
    )
    if not created and project.representative_repo_slug == build.repository.repo_slug and not repository.is_representative:
        repository.is_representative = True
        repository.save(update_fields=["is_representative", "updated_at"])
    return repository


def _upsert_build_plan(record: DefinitionImportRecord) -> BuildPlan:
    build = record.build_definition
    plan, created = BuildPlan.objects.get_or_create(
        build_id=build.build_id,
        defaults={"plan_key": build.plan_key},
    )
    if not created and plan.plan_key != build.plan_key:
        plan.plan_key = build.plan_key
        plan.save(update_fields=["plan_key", "updated_at"])
    return plan


def _upsert_project_build(project: Project, repository: ProjectRepository, plan: BuildPlan, record: DefinitionImportRecord) -> ProjectBuild:
    build = record.build_definition
    project_build, created = ProjectBuild.objects.get_or_create(
        build_plan=plan,
        defaults={
            "project": project,
            "repository": repository,
            "build_name": build.name,
            "build_type": build.compiler,
            "runtime_stack": build.language,
        },
    )
    if created:
        return project_build

    project_build.project = project
    project_build.repository = repository
    project_build.build_name = build.name
    project_build.build_type = build.compiler
    project_build.runtime_stack = build.language
    project_build.save(update_fields=["project", "repository", "build_name", "build_type", "runtime_stack", "updated_at"])
    return project_build


def _activate_definition(
    *,
    plan: BuildPlan,
    project: Project,
    record: DefinitionImportRecord,
    source_kind: str,
) -> tuple[bool, BuildPlanDefinition]:
    build = record.build_definition
    active_definition = BuildPlanDefinition.objects.filter(build_plan=plan, is_active=True).first()
    definition = BuildPlanDefinition.objects.filter(
        build_plan=plan,
        definition_hash=record.definition_hash,
    ).first()

    if definition is None:
        if active_definition is not None:
            active_definition.is_active = False
            active_definition.save(update_fields=["is_active"])
        definition = BuildPlanDefinition.objects.create(
            build_plan=plan,
            project=project,
            year=build.year,
            source_kind=source_kind,
            definition_json=record.raw_definition,
            definition_hash=record.definition_hash,
            is_active=True,
        )
        return True, definition

    updated_fields: list[str] = []
    if definition.project_id != project.id:
        definition.project = project
        updated_fields.append("project")
    if definition.year != build.year:
        definition.year = build.year
        updated_fields.append("year")
    if definition.source_kind != source_kind:
        definition.source_kind = source_kind
        updated_fields.append("source_kind")
    if definition.definition_json != record.raw_definition:
        definition.definition_json = record.raw_definition
        updated_fields.append("definition_json")

    changed_active = active_definition is None or active_definition.pk != definition.pk or not definition.is_active
    if changed_active:
        if active_definition is not None and active_definition.pk != definition.pk:
            active_definition.is_active = False
            active_definition.save(update_fields=["is_active"])
        if not definition.is_active:
            definition.is_active = True
            updated_fields.append("is_active")

    if updated_fields:
        definition.save(update_fields=updated_fields)

    return changed_active, definition


def _definition_hash(year: str, raw_definition: dict) -> str:
    payload = json.dumps({"year": year, "definition": raw_definition}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _display_source_path(source_path: Path) -> str:
    try:
        return str(source_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(source_path)
