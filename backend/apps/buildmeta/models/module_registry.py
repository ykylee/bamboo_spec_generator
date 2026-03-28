from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .core import TimestampedModel


class ModuleAsset(TimestampedModel):
    KIND_STAGE_MODULE = "stage_module"
    KIND_JOB_MODULE = "job_module"
    KIND_TASK_MODULE = "task_module"
    KIND_SCRIPT_TEMPLATE = "script_template"
    KIND_CHOICES = [
        (KIND_STAGE_MODULE, "stage_module"),
        (KIND_JOB_MODULE, "job_module"),
        (KIND_TASK_MODULE, "task_module"),
        (KIND_SCRIPT_TEMPLATE, "script_template"),
    ]

    PROVIDER_COMMON = "common"
    PROVIDER_BAMBOO = "bamboo"
    PROVIDER_JENKINS = "jenkins"
    PROVIDER_CHOICES = [
        (PROVIDER_COMMON, "common"),
        (PROVIDER_BAMBOO, "bamboo"),
        (PROVIDER_JENKINS, "jenkins"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_INVALID = "invalid"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "draft"),
        (STATUS_ACTIVE, "active"),
        (STATUS_INACTIVE, "inactive"),
        (STATUS_INVALID, "invalid"),
        (STATUS_ARCHIVED, "archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    provider_scope = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_COMMON)
    module_id = models.CharField(max_length=128)
    display_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    active_version = models.ForeignKey(
        "buildmeta.ModuleAssetVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    latest_version = models.ForeignKey(
        "buildmeta.ModuleAssetVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "buildmeta_module_asset"
        constraints = [
            models.UniqueConstraint(
                fields=["asset_kind", "provider_scope", "module_id"],
                name="uq_module_asset_kind_scope_id",
            ),
        ]
        indexes = [
            models.Index(fields=["asset_kind", "provider_scope"], name="ix_mod_asset_kind_scope"),
            models.Index(fields=["module_id"], name="ix_mod_asset_module_id"),
        ]

    def __str__(self) -> str:
        return f"{self.asset_kind}:{self.provider_scope}:{self.module_id}"


class ModuleAssetVersion(TimestampedModel):
    VALIDATION_PENDING = "pending"
    VALIDATION_VALID = "valid"
    VALIDATION_INVALID = "invalid"
    VALIDATION_CHOICES = [
        (VALIDATION_PENDING, "pending"),
        (VALIDATION_VALID, "valid"),
        (VALIDATION_INVALID, "invalid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(ModuleAsset, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    source_filename = models.CharField(max_length=255)
    storage_path = models.TextField()
    content_hash = models.CharField(max_length=128)
    schema_version = models.CharField(max_length=64, blank=True)
    validation_status = models.CharField(max_length=32, choices=VALIDATION_CHOICES, default=VALIDATION_PENDING)
    validation_message = models.TextField(blank=True)
    parsed_metadata_json = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_module_asset_versions",
    )

    class Meta:
        db_table = "buildmeta_module_asset_version"
        constraints = [
            models.UniqueConstraint(fields=["asset", "version_number"], name="uq_mod_asset_version_num"),
            models.UniqueConstraint(fields=["asset", "content_hash"], name="uq_mod_asset_content_hash"),
        ]
        indexes = [
            models.Index(fields=["validation_status"], name="ix_mod_asset_ver_validation"),
        ]

    def __str__(self) -> str:
        return f"{self.asset.module_id}@v{self.version_number}"


class ModuleActivation(TimestampedModel):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "active"),
        (STATUS_INACTIVE, "inactive"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.OneToOneField(ModuleAsset, on_delete=models.CASCADE, related_name="activation")
    activated_version = models.ForeignKey(
        ModuleAssetVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="activations",
    )
    activation_status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_INACTIVE)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="module_activations",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    active_path = models.TextField(blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "buildmeta_module_activation"


class ModuleLoadSnapshot(TimestampedModel):
    SOURCE_STARTUP = "startup"
    SOURCE_API = "api"
    SOURCE_COMMAND = "management_command"
    SOURCE_CHOICES = [
        (SOURCE_STARTUP, "startup"),
        (SOURCE_API, "api"),
        (SOURCE_COMMAND, "management_command"),
    ]

    STATUS_SUCCESS = "success"
    STATUS_PARTIAL_SUCCESS = "partial_success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "success"),
        (STATUS_PARTIAL_SUCCESS, "partial_success"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trigger_source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="module_load_snapshots",
    )
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    loaded_count = models.PositiveIntegerField(default=0)
    invalid_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    summary_message = models.TextField(blank=True)

    class Meta:
        db_table = "buildmeta_module_load_snapshot"
        indexes = [
            models.Index(fields=["started_at"], name="ix_mod_load_snapshot_started"),
        ]


class ModuleLoadEntry(TimestampedModel):
    STATUS_LOADED = "loaded"
    STATUS_INVALID = "invalid"
    STATUS_SKIPPED = "skipped"
    STATUS_CONFLICT = "conflict"
    STATUS_CHOICES = [
        (STATUS_LOADED, "loaded"),
        (STATUS_INVALID, "invalid"),
        (STATUS_SKIPPED, "skipped"),
        (STATUS_CONFLICT, "conflict"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(ModuleLoadSnapshot, on_delete=models.CASCADE, related_name="entries")
    asset = models.ForeignKey(
        ModuleAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="load_entries",
    )
    asset_version = models.ForeignKey(
        ModuleAssetVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="load_entries",
    )
    module_kind = models.CharField(max_length=32, blank=True)
    module_id = models.CharField(max_length=128, blank=True)
    source_path = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "buildmeta_module_load_entry"
        indexes = [
            models.Index(fields=["status"], name="ix_mod_load_entry_status"),
            models.Index(fields=["module_id"], name="ix_mod_load_entry_module_id"),
        ]
