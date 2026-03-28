from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from apps.buildmeta.models import ModuleActivation, ModuleAsset, ModuleAssetVersion, ModuleLoadEntry, ModuleLoadSnapshot
from src.bamboo_spec_generator.module_loader import load_active_module_registry


REPO_ROOT = Path(__file__).resolve().parents[4]
MANAGED_MODULES_ROOT = REPO_ROOT / "managed_modules"

MODULE_KIND_TO_ACTIVE_SUBDIR = {
    ModuleAsset.KIND_STAGE_MODULE: "stages",
    ModuleAsset.KIND_JOB_MODULE: "jobs",
    ModuleAsset.KIND_TASK_MODULE: "tasks",
    ModuleAsset.KIND_SCRIPT_TEMPLATE: "script_templates",
}

ALLOWED_SUFFIXES = {
    ModuleAsset.KIND_STAGE_MODULE: {".yaml", ".yml", ".json"},
    ModuleAsset.KIND_JOB_MODULE: {".yaml", ".yml", ".json"},
    ModuleAsset.KIND_TASK_MODULE: {".yaml", ".yml", ".json"},
    ModuleAsset.KIND_SCRIPT_TEMPLATE: {".yaml", ".yml", ".json", ".py", ".sh", ".bat", ".ps1", ".template", ".txt"},
}

EXPECTED_KIND = {
    ModuleAsset.KIND_STAGE_MODULE: "StageModule",
    ModuleAsset.KIND_JOB_MODULE: "JobModule",
}

EXPECTED_PROVIDER_KIND = {
    (ModuleAsset.KIND_TASK_MODULE, ModuleAsset.PROVIDER_BAMBOO): "BambooTaskModule",
    (ModuleAsset.KIND_TASK_MODULE, ModuleAsset.PROVIDER_JENKINS): "JenkinsTaskModule",
}


@dataclass
class ValidationResult:
    status: str
    message: str
    parsed_metadata: dict[str, Any]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "module"


def _module_storage_dir(*, asset_kind: str, provider_scope: str, module_id: str, version_number: int) -> Path:
    return (
        MANAGED_MODULES_ROOT
        / "uploads"
        / asset_kind
        / provider_scope
        / _safe_name(module_id)
        / f"v{version_number}"
    )


def _module_active_path(*, asset_kind: str, provider_scope: str, module_id: str, suffix: str) -> Path:
    subdir = MODULE_KIND_TO_ACTIVE_SUBDIR[asset_kind]
    provider_segment = provider_scope if asset_kind == ModuleAsset.KIND_TASK_MODULE else "common"
    return MANAGED_MODULES_ROOT / "active" / subdir / provider_segment / f"{_safe_name(module_id)}{suffix}"


def _read_uploaded_file(upload: UploadedFile) -> bytes:
    upload.seek(0)
    return upload.read()


def _parse_declared_payload(*, suffix: str, content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8")
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError:
            return {}
        payload = yaml.safe_load(text)
        return payload if isinstance(payload, dict) else {}
    return {}


def _validate_asset_content(*, asset_kind: str, provider_scope: str, suffix: str, content: bytes) -> ValidationResult:
    if suffix not in ALLOWED_SUFFIXES[asset_kind]:
        return ValidationResult(
            status=ModuleAssetVersion.VALIDATION_INVALID,
            message=f"Unsupported file extension: {suffix}",
            parsed_metadata={},
        )
    if asset_kind == ModuleAsset.KIND_SCRIPT_TEMPLATE:
        return ValidationResult(
            status=ModuleAssetVersion.VALIDATION_VALID,
            message="Script template accepted",
            parsed_metadata={},
        )

    try:
        payload = _parse_declared_payload(suffix=suffix, content=content)
    except Exception as exc:
        return ValidationResult(
            status=ModuleAssetVersion.VALIDATION_INVALID,
            message=f"Failed to parse module definition: {exc}",
            parsed_metadata={},
        )

    if not payload:
        text = content.decode("utf-8", errors="ignore")
        if "apiVersion:" in text and "kind:" in text and "metadata:" in text:
            return ValidationResult(
                status=ModuleAssetVersion.VALIDATION_VALID,
                message="Basic YAML structure accepted without parser support",
                parsed_metadata={},
            )
        return ValidationResult(
            status=ModuleAssetVersion.VALIDATION_INVALID,
            message="Module definition could not be parsed",
            parsed_metadata={},
        )

    kind = str(payload.get("kind", "")).strip()
    metadata = payload.get("metadata") or {}
    module_id = str(metadata.get("id", "")).strip()
    if not module_id:
        return ValidationResult(
            status=ModuleAssetVersion.VALIDATION_INVALID,
            message="metadata.id is required",
            parsed_metadata=payload,
        )
    expected_kind = EXPECTED_KIND.get(asset_kind) or EXPECTED_PROVIDER_KIND.get((asset_kind, provider_scope))
    if expected_kind and kind != expected_kind:
        return ValidationResult(
            status=ModuleAssetVersion.VALIDATION_INVALID,
            message=f"Unexpected kind: {kind}",
            parsed_metadata=payload,
        )
    return ValidationResult(
        status=ModuleAssetVersion.VALIDATION_VALID,
        message="Validation succeeded",
        parsed_metadata=payload,
    )


@transaction.atomic
def upload_module_asset(
    *,
    asset_kind: str,
    provider_scope: str,
    module_id: str,
    upload: UploadedFile,
    uploaded_by=None,
    activate_after_upload: bool = False,
) -> dict[str, Any]:
    asset, _ = ModuleAsset.objects.get_or_create(
        asset_kind=asset_kind,
        provider_scope=provider_scope,
        module_id=module_id.strip(),
        defaults={"display_name": module_id.strip()},
    )
    version_number = (asset.versions.order_by("-version_number").values_list("version_number", flat=True).first() or 0) + 1
    content = _read_uploaded_file(upload)
    suffix = Path(upload.name).suffix.lower()
    content_hash = hashlib.sha256(content).hexdigest()
    validation = _validate_asset_content(
        asset_kind=asset_kind,
        provider_scope=provider_scope,
        suffix=suffix,
        content=content,
    )
    storage_dir = _module_storage_dir(
        asset_kind=asset_kind,
        provider_scope=provider_scope,
        module_id=module_id,
        version_number=version_number,
    )
    _ensure_dir(storage_dir)
    storage_path = storage_dir / upload.name
    storage_path.write_bytes(content)
    version = ModuleAssetVersion.objects.create(
        asset=asset,
        version_number=version_number,
        source_filename=upload.name,
        storage_path=str(storage_path),
        content_hash=content_hash,
        schema_version=str(validation.parsed_metadata.get("apiVersion", "")),
        validation_status=validation.status,
        validation_message=validation.message,
        parsed_metadata_json=validation.parsed_metadata,
        uploaded_by=uploaded_by,
    )
    asset.latest_version = version
    asset.display_name = (
        str(validation.parsed_metadata.get("metadata", {}).get("name", "")).strip()
        or asset.display_name
        or module_id.strip()
    )
    asset.status = ModuleAsset.STATUS_INVALID if validation.status == ModuleAssetVersion.VALIDATION_INVALID else asset.status
    asset.save(update_fields=["latest_version", "display_name", "status", "updated_at"])
    if activate_after_upload and validation.status == ModuleAssetVersion.VALIDATION_VALID:
        activate_module_asset_version(asset=asset, version=version, activated_by=uploaded_by)
    return {
        "assetId": str(asset.id),
        "versionId": str(version.id),
        "validationStatus": version.validation_status,
        "message": version.validation_message,
        "activated": bool(activate_after_upload and validation.status == ModuleAssetVersion.VALIDATION_VALID),
    }


@transaction.atomic
def activate_module_asset_version(*, asset: ModuleAsset, version: ModuleAssetVersion, activated_by=None) -> dict[str, Any]:
    source_path = Path(version.storage_path)
    target_path = _module_active_path(
        asset_kind=asset.asset_kind,
        provider_scope=asset.provider_scope,
        module_id=asset.module_id,
        suffix=source_path.suffix.lower(),
    )
    _ensure_dir(target_path.parent)
    shutil.copy2(source_path, target_path)
    activation, _ = ModuleActivation.objects.get_or_create(asset=asset)
    activation.activated_version = version
    activation.activation_status = ModuleActivation.STATUS_ACTIVE
    activation.activated_by = activated_by
    activation.activated_at = datetime.now(timezone.utc)
    activation.active_path = str(target_path)
    activation.last_error = ""
    activation.save()
    asset.active_version = version
    asset.status = ModuleAsset.STATUS_ACTIVE
    asset.save(update_fields=["active_version", "status", "updated_at"])
    return {"assetId": str(asset.id), "versionId": str(version.id), "activePath": str(target_path)}


@transaction.atomic
def deactivate_module_asset(*, asset: ModuleAsset) -> dict[str, Any]:
    activation = getattr(asset, "activation", None)
    if activation and activation.active_path:
        active_path = Path(activation.active_path)
        if active_path.exists():
            active_path.unlink()
        activation.activation_status = ModuleActivation.STATUS_INACTIVE
        activation.active_path = ""
        activation.save(update_fields=["activation_status", "active_path", "updated_at"])
    asset.active_version = None
    asset.status = ModuleAsset.STATUS_INACTIVE
    asset.save(update_fields=["active_version", "status", "updated_at"])
    return {"assetId": str(asset.id), "status": asset.status}


@transaction.atomic
def reload_module_assets(*, triggered_by=None, trigger_source: str = ModuleLoadSnapshot.SOURCE_API) -> dict[str, Any]:
    snapshot = ModuleLoadSnapshot.objects.create(
        trigger_source=trigger_source,
        triggered_by=triggered_by,
        started_at=datetime.now(timezone.utc),
        status=ModuleLoadSnapshot.STATUS_SUCCESS,
    )
    loaded_count = 0
    invalid_count = 0
    skipped_count = 0
    active_assets = {
        activation.active_path: activation.asset
        for activation in ModuleActivation.objects.select_related("asset", "activated_version")
        if activation.active_path
    }
    for asset in ModuleAsset.objects.select_related("active_version").order_by("asset_kind", "provider_scope", "module_id"):
        if asset.active_version_id:
            continue
        skipped_count += 1
        ModuleLoadEntry.objects.create(
            snapshot=snapshot,
            asset=asset,
            module_kind=asset.asset_kind,
            module_id=asset.module_id,
            status=ModuleLoadEntry.STATUS_SKIPPED,
            error_code="inactive",
            error_message="No active version",
        )

    registry = load_active_module_registry(MANAGED_MODULES_ROOT / "active")
    loaded_paths: set[str] = set()

    for stage in registry.stages.values():
        asset = active_assets.get(str(stage.source_path))
        version = asset.active_version if asset else None
        loaded_paths.add(str(stage.source_path))
        loaded_count += 1
        ModuleLoadEntry.objects.create(
            snapshot=snapshot,
            asset=asset,
            asset_version=version,
            module_kind=ModuleAsset.KIND_STAGE_MODULE,
            module_id=stage.module_id,
            source_path=str(stage.source_path),
            status=ModuleLoadEntry.STATUS_LOADED,
        )

    for job in registry.jobs.values():
        asset = active_assets.get(str(job.source_path))
        version = asset.active_version if asset else None
        loaded_paths.add(str(job.source_path))
        loaded_count += 1
        ModuleLoadEntry.objects.create(
            snapshot=snapshot,
            asset=asset,
            asset_version=version,
            module_kind=ModuleAsset.KIND_JOB_MODULE,
            module_id=job.module_id,
            source_path=str(job.source_path),
            status=ModuleLoadEntry.STATUS_LOADED,
        )

    for task in registry.tasks.values():
        asset = active_assets.get(str(task.source_path))
        version = asset.active_version if asset else None
        loaded_paths.add(str(task.source_path))
        loaded_count += 1
        ModuleLoadEntry.objects.create(
            snapshot=snapshot,
            asset=asset,
            asset_version=version,
            module_kind=ModuleAsset.KIND_TASK_MODULE,
            module_id=task.module_id,
            source_path=str(task.source_path),
            status=ModuleLoadEntry.STATUS_LOADED,
        )

    for issue in registry.issues:
        asset = active_assets.get(str(issue.source_path))
        version = asset.active_version if asset else None
        loaded_paths.add(str(issue.source_path))
        invalid_count += 1
        ModuleLoadEntry.objects.create(
            snapshot=snapshot,
            asset=asset,
            asset_version=version,
            module_kind=issue.module_kind,
            module_id=issue.module_id,
            source_path=str(issue.source_path),
            status=ModuleLoadEntry.STATUS_INVALID,
            error_code=issue.error_code,
            error_message=issue.error_message,
        )

    for active_path, asset in active_assets.items():
        if active_path in loaded_paths:
            continue
        invalid_count += 1
        ModuleLoadEntry.objects.create(
            snapshot=snapshot,
            asset=asset,
            asset_version=asset.active_version,
            module_kind=asset.asset_kind,
            module_id=asset.module_id,
            source_path=active_path,
            status=ModuleLoadEntry.STATUS_INVALID,
            error_code="unscanned_active_path",
            error_message="Active path was not scanned by the module loader",
        )
    if invalid_count and loaded_count:
        status = ModuleLoadSnapshot.STATUS_PARTIAL_SUCCESS
    elif invalid_count and not loaded_count:
        status = ModuleLoadSnapshot.STATUS_FAILED
    else:
        status = ModuleLoadSnapshot.STATUS_SUCCESS
    snapshot.finished_at = datetime.now(timezone.utc)
    snapshot.status = status
    snapshot.loaded_count = loaded_count
    snapshot.invalid_count = invalid_count
    snapshot.skipped_count = skipped_count
    snapshot.summary_message = f"loaded={loaded_count} invalid={invalid_count} skipped={skipped_count}"
    snapshot.save(
        update_fields=[
            "finished_at",
            "status",
            "loaded_count",
            "invalid_count",
            "skipped_count",
            "summary_message",
            "updated_at",
        ]
    )
    return {
        "snapshotId": str(snapshot.id),
        "status": snapshot.status,
        "loadedCount": loaded_count,
        "invalidCount": invalid_count,
        "skippedCount": skipped_count,
    }


def list_module_assets(*, asset_kind: str = "", provider_scope: str = "", status: str = "") -> list[dict[str, Any]]:
    queryset = ModuleAsset.objects.select_related("active_version", "latest_version").order_by("asset_kind", "provider_scope", "module_id")
    if asset_kind:
        queryset = queryset.filter(asset_kind=asset_kind)
    if provider_scope:
        queryset = queryset.filter(provider_scope=provider_scope)
    if status:
        queryset = queryset.filter(status=status)
    return [
        {
            "assetId": str(asset.id),
            "assetKind": asset.asset_kind,
            "providerScope": asset.provider_scope,
            "moduleId": asset.module_id,
            "displayName": asset.display_name,
            "status": asset.status,
            "activeVersionId": str(asset.active_version_id) if asset.active_version_id else "",
            "latestVersionId": str(asset.latest_version_id) if asset.latest_version_id else "",
            "detailPath": f"/settings/modules/{asset.id}/",
        }
        for asset in queryset
    ]


def _infer_preview_language(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".sh"}:
        return "shell"
    if suffix in {".bat"}:
        return "batch"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    return "text"


def _read_version_content(version: ModuleAssetVersion | None) -> str:
    if not version:
        return ""
    source_path = Path(version.storage_path)
    if not source_path.exists():
        return ""
    return source_path.read_text(encoding="utf-8", errors="replace")


def _build_version_diff(*, older: ModuleAssetVersion | None, newer: ModuleAssetVersion | None) -> str:
    if not older or not newer:
        return ""
    older_lines = _read_version_content(older).splitlines()
    newer_lines = _read_version_content(newer).splitlines()
    return "\n".join(
        difflib.unified_diff(
            older_lines,
            newer_lines,
            fromfile=f"{older.source_filename}@v{older.version_number}",
            tofile=f"{newer.source_filename}@v{newer.version_number}",
            lineterm="",
        )
    )


def get_module_asset_detail(*, asset_id: str, version_id: str = "", compare_version_id: str = "") -> dict[str, Any]:
    asset = ModuleAsset.objects.select_related("active_version", "latest_version").get(pk=asset_id)
    selected_version = None
    if version_id:
        selected_version = asset.versions.get(pk=version_id)
    elif asset.active_version_id:
        selected_version = asset.active_version
    else:
        selected_version = asset.latest_version

    preview_content = ""
    preview_language = "text"
    selected_version_id = ""
    if selected_version:
        preview_content = _read_version_content(selected_version)
        preview_language = _infer_preview_language(selected_version.source_filename)
        selected_version_id = str(selected_version.id)

    compare_version = None
    compare_version_id_value = ""
    if compare_version_id:
        compare_version = asset.versions.get(pk=compare_version_id)
        compare_version_id_value = str(compare_version.id)

    diff_content = _build_version_diff(older=compare_version, newer=selected_version)
    recent_issues = [
        {
            "status": entry.status,
            "errorCode": entry.error_code,
            "errorMessage": entry.error_message,
            "sourcePath": entry.source_path,
            "recordedAt": entry.created_at.isoformat(),
        }
        for entry in asset.load_entries.select_related("snapshot").exclude(error_code="").order_by("-created_at")[:10]
    ]

    return {
        "assetId": str(asset.id),
        "assetKind": asset.asset_kind,
        "providerScope": asset.provider_scope,
        "moduleId": asset.module_id,
        "displayName": asset.display_name,
        "status": asset.status,
        "selectedVersionId": selected_version_id,
        "compareVersionId": compare_version_id_value,
        "previewContent": preview_content,
        "previewLanguage": preview_language,
        "diffContent": diff_content,
        "diffLanguage": "diff",
        "recentIssues": recent_issues,
        "versions": [
            {
                "versionId": str(version.id),
                "versionNumber": version.version_number,
                "sourceFilename": version.source_filename,
                "validationStatus": version.validation_status,
                "validationMessage": version.validation_message,
                "uploadedAt": version.created_at.isoformat(),
                "isActive": version.id == asset.active_version_id,
                "isLatest": version.id == asset.latest_version_id,
            }
            for version in asset.versions.order_by("-version_number")
        ],
    }


def get_module_load_status() -> dict[str, Any]:
    snapshot = ModuleLoadSnapshot.objects.order_by("-started_at").first()
    if not snapshot:
        return {
            "lastSnapshot": None,
            "activeAssetCount": ModuleAsset.objects.filter(status=ModuleAsset.STATUS_ACTIVE).count(),
            "recentFailures": [],
        }
    return {
        "lastSnapshot": {
            "snapshotId": str(snapshot.id),
            "status": snapshot.status,
            "loadedCount": snapshot.loaded_count,
            "invalidCount": snapshot.invalid_count,
            "skippedCount": snapshot.skipped_count,
            "startedAt": snapshot.started_at.isoformat(),
            "finishedAt": snapshot.finished_at.isoformat() if snapshot.finished_at else "",
            "summaryMessage": snapshot.summary_message,
        },
        "activeAssetCount": ModuleAsset.objects.filter(status=ModuleAsset.STATUS_ACTIVE).count(),
        "recentFailures": [
            {
                "moduleId": entry.module_id,
                "status": entry.status,
                "errorCode": entry.error_code,
                "errorMessage": entry.error_message,
            }
            for entry in snapshot.entries.filter(status=ModuleLoadEntry.STATUS_INVALID).order_by("module_id")[:20]
        ],
    }
