from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from apps.buildmeta.models import (
    AuditEvent,
    BambooBuildUnit,
    BuildUnitDefinition,
    BuildUnit,
    Project,
    Repository,
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
def import_definition_records(
    records: list[DefinitionImportRecord],
    *,
    source_kind: str = BuildUnitDefinition.SOURCE_JSON,
) -> dict:
    imported_count = 0
    activated_count = 0

    for record in records:
        project = _upsert_project(record)
        repository = _upsert_repository(project, record)
        build_unit, _ = _upsert_build_unit(project, repository, record)
        changed_active, _definition = _activate_definition(
            build_unit=build_unit,
            record=record,
            source_kind=source_kind,
        )
        if changed_active:
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
    source_kind: str = BuildUnitDefinition.SOURCE_JSON,
    deactivate_missing: bool = False,
) -> dict:
    imported_count = 0
    activated_count = 0
    unchanged_count = 0
    deactivated_count = 0
    synced_external_keys: set[str] = set()

    for record in records:
        project = _upsert_project(record)
        repository = _upsert_repository(project, record)
        build_unit, external_key = _upsert_build_unit(project, repository, record)
        synced_external_keys.add(external_key)
        changed_active, _definition = _activate_definition(
            build_unit=build_unit,
            record=record,
            source_kind=source_kind,
        )
        if changed_active:
            activated_count += 1
        else:
            unchanged_count += 1
        imported_count += 1

    if deactivate_missing:
        active_definitions = (
            BuildUnitDefinition.objects.select_related("build_unit")
            .filter(is_active=True, source_kind=source_kind, build_unit__ci_provider=Project.PROVIDER_BAMBOO)
            .exclude(build_unit__external_key__in=synced_external_keys)
        )
        for definition in active_definitions:
            definition.is_active = False
            definition.save(update_fields=["is_active", "updated_at"])
            AuditEvent.objects.create(
                actor="system",
                event_type="deactivate",
                target_type="build_unit_definition",
                target_id=str(definition.id),
                payload_json={"buildUnit": definition.build_unit.external_key},
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
    project, _created = Project.objects.get_or_create(
        project_key=build.repository.project_key,
        ci_provider=Project.PROVIDER_BAMBOO,
        defaults={
            "name": build.repository.project_key,
            "description": "",
            "status": Project.STATUS_ACTIVE,
        },
    )
    return project


def _upsert_repository(project: Project, record: DefinitionImportRecord) -> Repository:
    build = record.build_definition
    repository, _created = Repository.objects.update_or_create(
        project=project,
        repo_slug=build.repository.repo_slug,
        defaults={
            "repo_type": Repository.TYPE_BITBUCKET,
            "repo_key": build.repository.project_key,
            "clone_url": build.repository.clone_url or "",
            "default_branch": "dev",
            "is_representative": project.representative_repository_id is None or (
                project.representative_repository is not None
                and project.representative_repository.repo_slug == build.repository.repo_slug
            ),
        },
    )
    if project.representative_repository_id is None:
        project.representative_repository = repository
        project.save(update_fields=["representative_repository", "updated_at"])
    return repository


def _upsert_build_unit(
    project: Project,
    repository: Repository,
    record: DefinitionImportRecord,
) -> tuple[BuildUnit, str]:
    build = record.build_definition
    external_key = build.plan_key
    build_unit, _created = BuildUnit.objects.update_or_create(
        ci_provider=Project.PROVIDER_BAMBOO,
        external_key=external_key,
        defaults={
            "project": project,
            "repository": repository,
            "unit_type": BuildUnit.TYPE_BUILD,
            "display_name": build.name,
            "description": build.name,
            "language": build.language,
            "compiler": build.compiler,
            "runtime_stack": build.language,
            "lifecycle_status": BuildUnit.STATUS_ACTIVE,
            "is_enabled": True,
        },
    )
    BambooBuildUnit.objects.update_or_create(
        build_unit=build_unit,
        defaults={
            "bamboo_project_key": build.repository.project_key,
            "plan_key": build.plan_key,
            "build_id": build.build_id,
            "repository_linkage_mode": build.repository.linkage_mode,
            "application_link": build.repository.application_link or "",
            "static_analysis_tool_version": "",
            "coverity_project": repository.coverity_project,
        },
    )
    return build_unit, external_key


def _activate_definition(
    *,
    build_unit: BuildUnit,
    record: DefinitionImportRecord,
    source_kind: str,
) -> tuple[bool, BuildUnitDefinition]:
    build = record.build_definition
    active_definition = build_unit.definitions.filter(is_active=True).first()
    definition = build_unit.definitions.filter(definition_hash=record.definition_hash).first()

    if definition is None:
        if active_definition is not None:
            active_definition.is_active = False
            active_definition.save(update_fields=["is_active", "updated_at"])
        definition = BuildUnitDefinition.objects.create(
            build_unit=build_unit,
            version=(build_unit.definitions.count() + 1),
            year=build.year,
            source_kind=source_kind,
            definition_json=record.raw_definition,
            definition_hash=record.definition_hash,
            is_active=True,
        )
        AuditEvent.objects.create(
            actor="system",
            event_type="sync",
            target_type="build_unit_definition",
            target_id=str(definition.id),
            payload_json={"buildUnit": build_unit.external_key},
        )
        return True, definition

    updated_fields: list[str] = []
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
            active_definition.save(update_fields=["is_active", "updated_at"])
        if not definition.is_active:
            definition.is_active = True
            updated_fields.append("is_active")

    if updated_fields:
        definition.save(update_fields=updated_fields + ["updated_at"])
    if changed_active:
        AuditEvent.objects.create(
            actor="system",
            event_type="sync",
            target_type="build_unit_definition",
            target_id=str(definition.id),
            payload_json={"buildUnit": build_unit.external_key},
        )

    return changed_active, definition


def _definition_hash(year: str, raw_definition: dict) -> str:
    payload = json.dumps({"year": year, "definition": raw_definition}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
