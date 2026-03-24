from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SystemSetting(TimestampedModel):
    KEY_COVERITY_CONNECT_URL = "coverity.connect.url"
    KEY_COVERITY_ON_NEW_CERT = "coverity.connect.on_new_cert"
    KEY_COVERITY_COMMIT_ENABLED = "coverity.commit.enabled"
    KEY_GIT_CLONE_URL_TEMPLATE = "repository.git.clone_url_template"
    KEY_REPOSITORY_LINKAGE_MODE = "repository.linkage_mode"
    KEY_BAMBOO_SERVER_URL = "bamboo.server.url"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=128, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["key"], name="ix_system_setting_key"),
        ]

    def __str__(self) -> str:
        return self.key


class Project(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jira_project_key = models.CharField(max_length=64, unique=True)
    bitbucket_project_key = models.CharField(max_length=64)
    representative_repo_slug = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return self.jira_project_key


class BuildPlan(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_id = models.CharField(max_length=255, unique=True)
    plan_key = models.CharField(max_length=64, unique=True)
    static_analysis_tool_version = models.CharField(max_length=128, blank=True)
    coverity_project = models.CharField(max_length=255, blank=True)
    latest_version = models.ForeignKey(
        "buildmeta.BuildVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    def __str__(self) -> str:
        return self.plan_key


class BuildPlanBuildInfo(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_plan = models.ForeignKey(BuildPlan, on_delete=models.CASCADE, related_name="build_infos")
    build_key = models.CharField(max_length=128)
    operating_system = models.CharField(max_length=32, blank=True)
    pre_process = models.TextField(blank=True)
    build_command = models.TextField(blank=True)
    clean_command = models.TextField(blank=True)
    language = models.CharField(max_length=64, blank=True)
    compiler = models.CharField(max_length=128, blank=True)
    analysis_excluded_files = models.TextField(blank=True)
    coverity_stream = models.CharField(max_length=255, blank=True)
    build_sub_path = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_plan", "build_key"], name="uq_plan_build_info_key"),
        ]
        indexes = [
            models.Index(fields=["build_plan", "build_key"], name="ix_plan_build_info_key"),
        ]

    def __str__(self) -> str:
        return f"{self.build_plan.plan_key}:{self.build_key}"


class ProjectRepository(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="repositories")
    repo_slug = models.CharField(max_length=255)
    coverity_project = models.CharField(max_length=255, blank=True)
    coverity_stream = models.CharField(max_length=255, blank=True)
    is_representative = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "repo_slug"], name="uq_project_repo_slug"),
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(is_representative=True),
                name="uq_project_representative_repo",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "is_representative"], name="ix_project_repo_repr"),
        ]


class ProjectBuild(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="builds")
    repository = models.ForeignKey(
        ProjectRepository,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="builds",
    )
    build_plan = models.OneToOneField(BuildPlan, on_delete=models.CASCADE, related_name="project_build")
    build_name = models.CharField(max_length=255)
    build_type = models.CharField(max_length=128)
    runtime_stack = models.CharField(max_length=128, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "build_name"], name="uq_project_build_name"),
        ]
        indexes = [
            models.Index(fields=["project", "build_name"], name="ix_project_build_name"),
        ]


class BuildPlanDefinition(models.Model):
    SOURCE_KIND_JSON = "json"
    SOURCE_KIND_DB = "db"
    SOURCE_KIND_IMPORT = "import"
    SOURCE_KIND_CHOICES = [
        (SOURCE_KIND_JSON, "JSON"),
        (SOURCE_KIND_DB, "DB"),
        (SOURCE_KIND_IMPORT, "Import"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_plan = models.ForeignKey(BuildPlan, on_delete=models.CASCADE, related_name="definitions")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="definitions")
    year = models.CharField(max_length=16)
    source_kind = models.CharField(max_length=32, choices=SOURCE_KIND_CHOICES)
    definition_json = models.JSONField()
    definition_hash = models.CharField(max_length=128)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_plan", "definition_hash"], name="uq_plan_definition_hash"),
            models.UniqueConstraint(
                fields=["build_plan"],
                condition=Q(is_active=True),
                name="uq_plan_active_definition",
            ),
        ]
        indexes = [
            models.Index(fields=["build_plan", "is_active"], name="ix_definition_active"),
        ]


class BuildVersion(TimestampedModel):
    BRANCH_KIND_MASTER = "master"
    BRANCH_KIND_RELEASE = "release"
    BRANCH_KIND_DEV = "dev"
    BRANCH_KIND_CHOICES = [
        (BRANCH_KIND_MASTER, "master"),
        (BRANCH_KIND_RELEASE, "release"),
        (BRANCH_KIND_DEV, "dev"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_plan = models.ForeignKey(BuildPlan, on_delete=models.CASCADE, related_name="versions")
    version_text = models.CharField(max_length=32)
    major = models.PositiveIntegerField()
    minor = models.PositiveIntegerField()
    patch = models.PositiveIntegerField()
    branch_kind = models.CharField(max_length=16, choices=BRANCH_KIND_CHOICES)
    commit_hash = models.CharField(max_length=64)
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
        constraints = [
            models.UniqueConstraint(fields=["build_plan", "version_text"], name="uq_build_version_text"),
            models.UniqueConstraint(fields=["build_plan", "commit_hash"], name="uq_build_version_commit"),
            models.UniqueConstraint(
                fields=["build_plan"],
                condition=Q(is_latest=True),
                name="uq_build_version_latest",
            ),
        ]
        indexes = [
            models.Index(fields=["build_plan", "is_latest"], name="ix_build_version_latest"),
            models.Index(fields=["build_plan", "commit_hash"], name="ix_build_version_commit"),
        ]


class BuildExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_plan = models.ForeignKey(BuildPlan, on_delete=models.CASCADE, related_name="executions")
    build_info = models.ForeignKey(
        BuildPlanBuildInfo,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="executions",
    )
    build_version = models.ForeignKey(BuildVersion, on_delete=models.CASCADE, related_name="executions")
    build_number = models.CharField(max_length=64)
    commit_hash = models.CharField(max_length=64)
    success = models.BooleanField(default=False)
    result_status = models.CharField(max_length=64)
    summary_message = models.TextField(blank=True)
    stage_name = models.CharField(max_length=255, blank=True)
    job_name = models.CharField(max_length=255, blank=True)
    task_name = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["build_plan", "build_info", "build_number"],
                name="uq_build_execution_number_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["build_version", "-created_at"], name="ix_execution_version_created"),
            models.Index(fields=["build_plan", "-build_number"], name="ix_execution_plan_number"),
            models.Index(fields=["build_info", "-created_at"], name="ix_exec_build_info_created"),
        ]


class BambooPublishExecution(TimestampedModel):
    STATUS_SUCCESS = "successful"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "successful"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_plan = models.ForeignKey(BuildPlan, on_delete=models.CASCADE, related_name="publish_executions")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    output = models.TextField(blank=True)
    return_code = models.IntegerField(null=True, blank=True)
    trigger_source = models.CharField(max_length=64, blank=True)
    requested_by = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["build_plan", "-created_at"], name="ix_publish_exec_plan_created"),
        ]


class StaticAnalysisResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_execution = models.ForeignKey(BuildExecution, on_delete=models.CASCADE, related_name="static_analysis_results")
    tool_name = models.CharField(max_length=64)
    status = models.CharField(max_length=64)
    summary = models.TextField(blank=True)
    metrics_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["build_execution", "tool_name"], name="uq_static_analysis_tool"),
        ]
        indexes = [
            models.Index(fields=["build_execution", "tool_name"], name="ix_static_analysis_tool"),
        ]


class BuildDefinitionHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    build_plan = models.ForeignKey(BuildPlan, on_delete=models.CASCADE, related_name="definition_history")
    build_plan_definition = models.ForeignKey(
        BuildPlanDefinition,
        on_delete=models.CASCADE,
        related_name="history_entries",
    )
    change_type = models.CharField(max_length=64)
    change_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
