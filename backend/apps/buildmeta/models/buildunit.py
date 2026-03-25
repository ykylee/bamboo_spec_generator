from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

from .core import TimestampedModel


class Project(TimestampedModel):
    PROVIDER_BAMBOO = "bamboo"
    PROVIDER_JENKINS = "jenkins"
    PROVIDER_CHOICES = [
        (PROVIDER_BAMBOO, "Bamboo"),
        (PROVIDER_JENKINS, "Jenkins"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "active"),
        (STATUS_INACTIVE, "inactive"),
        (STATUS_ARCHIVED, "archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_key = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner_team = models.CharField(max_length=255, blank=True)
    service_type = models.CharField(max_length=64, blank=True)
    ci_provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    representative_repository = models.ForeignKey(
        "buildmeta.Repository",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "buildmeta_project"
        constraints = [
            models.UniqueConstraint(fields=["ci_provider", "project_key"], name="uq_project_provider_key"),
        ]

    def __str__(self) -> str:
        return f"{self.ci_provider}:{self.project_key}"

    @property
    def jira_project_key(self) -> str:
        return self.project_key

    @property
    def bitbucket_project_key(self) -> str:
        if self.representative_repository_id:
            return self.representative_repository.repo_key
        representative = self.repositories.order_by("-is_representative", "repo_slug").first()
        return representative.repo_key if representative else ""

    @property
    def representative_repo_slug(self) -> str:
        return self.representative_repository.repo_slug if self.representative_repository_id else ""


class Repository(TimestampedModel):
    TYPE_BITBUCKET = "bitbucket"
    TYPE_GIT = "git"
    TYPE_CHOICES = [
        (TYPE_BITBUCKET, "bitbucket"),
        (TYPE_GIT, "git"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="repositories")
    repo_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_BITBUCKET)
    repo_key = models.CharField(max_length=128, blank=True)
    repo_slug = models.CharField(max_length=255)
    clone_url = models.TextField(blank=True)
    default_branch = models.CharField(max_length=255, blank=True)
    is_representative = models.BooleanField(default=False)
    coverity_project = models.CharField(max_length=255, blank=True)
    coverity_stream = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "buildmeta_repository"
        constraints = [
            models.UniqueConstraint(fields=["project", "repo_slug"], name="uq_repository_project_slug"),
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(is_representative=True),
                name="uq_repository_representative",
            ),
        ]

    def __str__(self) -> str:
        return self.repo_slug


class BuildUnit(TimestampedModel):
    PROVIDER_BAMBOO = "bamboo"
    PROVIDER_JENKINS = "jenkins"
    PROVIDER_CHOICES = [
        (PROVIDER_BAMBOO, "Bamboo"),
        (PROVIDER_JENKINS, "Jenkins"),
    ]

    TYPE_BUILD = "build"
    TYPE_PIPELINE = "pipeline"
    TYPE_ANALYSIS = "analysis"
    TYPE_DEPLOY = "deploy"
    TYPE_CHOICES = [
        (TYPE_BUILD, "build"),
        (TYPE_PIPELINE, "pipeline"),
        (TYPE_ANALYSIS, "analysis"),
        (TYPE_DEPLOY, "deploy"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_DISABLED = "disabled"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "active"),
        (STATUS_DISABLED, "disabled"),
        (STATUS_ARCHIVED, "archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="build_units")
    repository = models.ForeignKey(
        Repository,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="build_units",
    )
    ci_provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    unit_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_BUILD)
    external_key = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    language = models.CharField(max_length=64, blank=True)
    compiler = models.CharField(max_length=128, blank=True)
    runtime_stack = models.CharField(max_length=128, blank=True)
    lifecycle_status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_enabled = models.BooleanField(default=True)
    latest_version = models.ForeignKey(
        "buildmeta.BuildVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "buildmeta_build_unit"
        constraints = [
            models.UniqueConstraint(fields=["ci_provider", "external_key"], name="uq_build_unit_provider_key"),
        ]

    def __str__(self) -> str:
        return f"{self.ci_provider}:{self.external_key}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        bamboo_update_fields: list[str] = []
        if update_fields:
            update_fields = set(update_fields)
            if "repository_linkage_mode_override" in update_fields:
                update_fields.remove("repository_linkage_mode_override")
                bamboo_update_fields.append("repository_linkage_mode")
            if "static_analysis_tool_version" in update_fields:
                update_fields.remove("static_analysis_tool_version")
                bamboo_update_fields.append("static_analysis_tool_version")
            if "coverity_project" in update_fields:
                update_fields.remove("coverity_project")
                bamboo_update_fields.append("coverity_project")
            kwargs["update_fields"] = list(update_fields)
        super().save(*args, **kwargs)
        if bamboo_update_fields and hasattr(self, "bamboo"):
            if update_fields and "updated_at" in update_fields:
                bamboo_update_fields.append("updated_at")
            self.bamboo.save(update_fields=bamboo_update_fields)

    @property
    def plan_key(self) -> str:
        return self.bamboo.plan_key if hasattr(self, "bamboo") else self.external_key

    @property
    def build_id(self) -> str:
        return self.bamboo.build_id if hasattr(self, "bamboo") else self.external_key

    @property
    def static_analysis_tool_version(self) -> str:
        return self.bamboo.static_analysis_tool_version if hasattr(self, "bamboo") else ""

    @property
    def coverity_project(self) -> str:
        return self.bamboo.coverity_project if hasattr(self, "bamboo") else ""

    @coverity_project.setter
    def coverity_project(self, value: str) -> None:
        if hasattr(self, "bamboo"):
            self.bamboo.coverity_project = value or ""

    @property
    def repository_linkage_mode_override(self) -> str:
        return self.bamboo.repository_linkage_mode if hasattr(self, "bamboo") else ""

    @repository_linkage_mode_override.setter
    def repository_linkage_mode_override(self, value: str) -> None:
        if hasattr(self, "bamboo"):
            self.bamboo.repository_linkage_mode = value or ""

    @static_analysis_tool_version.setter
    def static_analysis_tool_version(self, value: str) -> None:
        if hasattr(self, "bamboo"):
            self.bamboo.static_analysis_tool_version = value or ""

    @property
    def build_infos(self):
        return self.bamboo.build_infos if hasattr(self, "bamboo") else BambooBuildInfo.objects.none()


class BuildUnitDefinition(TimestampedModel):
    SOURCE_KIND_JSON = "json"
    SOURCE_KIND_DB = "api"
    SOURCE_KIND_IMPORT = "import"
    SOURCE_JSON = "json"
    SOURCE_API = "api"
    SOURCE_UI = "ui"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = [
        (SOURCE_JSON, "json"),
        (SOURCE_API, "api"),
        (SOURCE_UI, "ui"),
        (SOURCE_IMPORT, "import"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="definitions")
    version = models.PositiveIntegerField(default=1)
    year = models.CharField(max_length=16, blank=True)
    source_kind = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    definition_hash = models.CharField(max_length=128)
    definition_json = models.JSONField()
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "buildmeta_build_unit_definition"
        constraints = [
            models.UniqueConstraint(
                fields=["build_unit", "definition_hash"],
                name="uq_build_unit_definition_hash",
            ),
            models.UniqueConstraint(
                fields=["build_unit"],
                condition=Q(is_active=True),
                name="uq_build_unit_definition_active",
            ),
        ]

    @property
    def build_plan(self) -> BuildUnit:
        return self.build_unit

    @property
    def project(self) -> Project:
        return self.build_unit.project


class BuildVersion(TimestampedModel):
    BRANCH_KIND_MASTER = "master"
    BRANCH_KIND_RELEASE = "release"
    BRANCH_KIND_DEV = "dev"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="versions")
    version_text = models.CharField(max_length=64)
    version_major = models.PositiveIntegerField(default=0)
    version_minor = models.PositiveIntegerField(default=0)
    version_patch = models.PositiveIntegerField(default=0)
    commit_hash = models.CharField(max_length=64, blank=True)
    branch_name = models.CharField(max_length=255, blank=True)
    branch_kind = models.CharField(max_length=64, blank=True)
    is_latest = models.BooleanField(default=False)
    latest_execution = models.ForeignKey(
        "buildmeta.BuildExecution",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    latest_success = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = "buildmeta_build_version"
        constraints = [
            models.UniqueConstraint(fields=["build_unit", "version_text"], name="uq_build_version_text"),
            models.UniqueConstraint(
                fields=["build_unit"],
                condition=Q(is_latest=True),
                name="uq_build_version_latest",
            ),
        ]

    @property
    def major(self) -> int:
        return self.version_major

    @property
    def minor(self) -> int:
        return self.version_minor

    @property
    def patch(self) -> int:
        return self.version_patch


class BuildExecution(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "queued"),
        (STATUS_RUNNING, "running"),
        (STATUS_SUCCESS, "success"),
        (STATUS_FAILED, "failed"),
        (STATUS_CANCELED, "canceled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(BuildUnit, on_delete=models.CASCADE, related_name="executions")
    build_version = models.ForeignKey(
        BuildVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="executions",
    )
    execution_number = models.CharField(max_length=64)
    external_execution_key = models.CharField(max_length=255, blank=True)
    trigger_type = models.CharField(max_length=64, blank=True)
    trigger_actor = models.CharField(max_length=255, blank=True)
    branch_name = models.CharField(max_length=255, blank=True)
    commit_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    summary = models.TextField(blank=True)
    stage_name = models.CharField(max_length=255, blank=True)
    job_name = models.CharField(max_length=255, blank=True)
    task_name = models.CharField(max_length=255, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buildmeta_build_execution"
        constraints = [
            models.UniqueConstraint(
                fields=["build_unit", "external_execution_key", "execution_number"],
                name="uq_build_execution_number",
            ),
        ]

    @property
    def build_plan(self) -> BuildUnit:
        return self.build_unit

    @property
    def build_number(self) -> str:
        return self.execution_number

    @property
    def result_status(self) -> str:
        return self.status

    @property
    def summary_message(self) -> str:
        return self.summary

    @property
    def success(self) -> bool:
        return self.status == self.STATUS_SUCCESS


class ExecutionArtifact(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_execution = models.ForeignKey(BuildExecution, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    path = models.TextField(blank=True)
    download_url = models.TextField(blank=True)
    checksum = models.CharField(max_length=128, blank=True)

    class Meta:
        db_table = "buildmeta_execution_artifact"


class StaticAnalysisResult(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_execution = models.ForeignKey(
        BuildExecution,
        on_delete=models.CASCADE,
        related_name="static_analysis_results",
    )
    tool_name = models.CharField(max_length=64)
    status = models.CharField(max_length=64)
    summary = models.TextField(blank=True)
    metrics_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "buildmeta_static_analysis_result"
        constraints = [
            models.UniqueConstraint(
                fields=["build_execution", "tool_name"],
                name="uq_static_analysis_result_tool",
            ),
        ]


class DeploymentTarget(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True)
    target_type = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, default="active")
    approval_required = models.BooleanField(default=False)

    class Meta:
        db_table = "buildmeta_deployment_target"


class DeploymentExecution(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_version = models.ForeignKey(BuildVersion, on_delete=models.CASCADE, related_name="deployments")
    deployment_target = models.ForeignKey(
        DeploymentTarget,
        on_delete=models.PROTECT,
        related_name="deployments",
    )
    status = models.CharField(max_length=32)
    requested_by = models.CharField(max_length=255, blank=True)
    approved_by = models.CharField(max_length=255, blank=True)
    rollback_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rollback_executions",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "buildmeta_deployment_execution"


class SystemStatusSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ci_provider = models.CharField(max_length=32)
    resource_type = models.CharField(max_length=64)
    resource_name = models.CharField(max_length=255)
    status = models.CharField(max_length=64)
    online = models.BooleanField(default=False)
    busy = models.BooleanField(default=False)
    queue_size = models.PositiveIntegerField(default=0)
    labels_json = models.JSONField(null=True, blank=True)
    payload_json = models.JSONField(null=True, blank=True)
    captured_at = models.DateTimeField()

    class Meta:
        db_table = "buildmeta_system_status_snapshot"


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.CharField(max_length=255, blank=True)
    event_type = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64)
    payload_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buildmeta_audit_event"


class BambooBuildUnit(TimestampedModel):
    build_unit = models.OneToOneField(
        BuildUnit,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="bamboo",
    )
    bamboo_project_key = models.CharField(max_length=64, blank=True)
    plan_key = models.CharField(max_length=64, unique=True)
    build_id = models.CharField(max_length=255, unique=True)
    repository_linkage_mode = models.CharField(max_length=32, blank=True)
    application_link = models.CharField(max_length=255, blank=True)
    static_analysis_tool_version = models.CharField(max_length=128, blank=True)
    coverity_project = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "buildmeta_bamboo_build_unit"


class BambooBuildInfo(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bamboo_build_unit = models.ForeignKey(
        BambooBuildUnit,
        on_delete=models.CASCADE,
        related_name="build_infos",
    )
    build_key = models.CharField(max_length=128)
    operating_system = models.CharField(max_length=64, blank=True)
    pre_process = models.TextField(blank=True)
    build_command = models.TextField(blank=True)
    clean_command = models.TextField(blank=True)
    language = models.CharField(max_length=64, blank=True)
    compiler = models.CharField(max_length=128, blank=True)
    analysis_excluded_files = models.TextField(blank=True)
    coverity_stream = models.CharField(max_length=255, blank=True)
    build_sub_path = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "buildmeta_bamboo_build_info"
        constraints = [
            models.UniqueConstraint(
                fields=["bamboo_build_unit", "build_key"],
                name="uq_bamboo_build_info_key",
            ),
        ]

    @property
    def build_plan(self) -> BuildUnit:
        return self.bamboo_build_unit.build_unit


class BambooPublishExecution(TimestampedModel):
    STATUS_SUCCESS = "successful"
    STATUS_FAILED = "failed"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_unit = models.ForeignKey(
        BuildUnit,
        on_delete=models.CASCADE,
        related_name="bamboo_publish_executions",
    )
    status = models.CharField(max_length=32)
    message = models.TextField(blank=True)
    output = models.TextField(blank=True)
    snapshot_preview_json = models.JSONField(null=True, blank=True)
    snapshot_export_draft_json = models.JSONField(null=True, blank=True)
    return_code = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "buildmeta_bamboo_publish_execution"

    @property
    def build_plan(self) -> BuildUnit:
        return self.build_unit


class JenkinsBuildUnit(TimestampedModel):
    build_unit = models.OneToOneField(
        BuildUnit,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="jenkins",
    )
    job_path = models.CharField(max_length=255, unique=True)
    job_type = models.CharField(max_length=64, blank=True)
    folder_path = models.CharField(max_length=255, blank=True)
    pipeline_kind = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "buildmeta_jenkins_build_unit"


class JenkinsNodeSnapshot(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource_name = models.CharField(max_length=255)
    labels_json = models.JSONField(null=True, blank=True)
    executor_count = models.PositiveIntegerField(default=0)
    busy_executors = models.PositiveIntegerField(default=0)
    offline_reason = models.TextField(blank=True)
    captured_at = models.DateTimeField()

    class Meta:
        db_table = "buildmeta_jenkins_node_snapshot"


class JenkinsQueueItemSnapshot(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue_item_key = models.CharField(max_length=128)
    job_path = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=64, blank=True)
    waiting_reason = models.TextField(blank=True)
    in_queue_since = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField()

    class Meta:
        db_table = "buildmeta_jenkins_queue_item_snapshot"
