from __future__ import annotations

from django.contrib import admin

from .models import (
    AuditEvent,
    BambooBuildInfo,
    BambooBuildUnit,
    BambooPublishExecution,
    BuildExecution,
    BuildUnit,
    BuildUnitDefinition,
    BuildVersion,
    DeploymentExecution,
    DeploymentTarget,
    ExecutionArtifact,
    JenkinsBuildUnit,
    JenkinsNodeSnapshot,
    JenkinsQueueItemSnapshot,
    Project,
    Repository,
    StaticAnalysisResult,
    SystemSetting,
    SystemStatusSnapshot,
)


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "value", "description")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("ci_provider", "project_key", "name", "status", "owner_team")
    list_filter = ("ci_provider", "status")
    search_fields = ("project_key", "name", "owner_team")


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("project", "repo_slug", "repository_type", "repository_provider", "default_branch", "is_representative")
    list_filter = ("repository_type", "repository_provider", "is_representative")
    search_fields = ("repo_slug", "repo_key", "clone_url")


@admin.register(BuildUnit)
class BuildUnitAdmin(admin.ModelAdmin):
    list_display = ("ci_provider", "external_key", "display_name", "unit_type", "lifecycle_status", "is_enabled")
    list_filter = ("ci_provider", "unit_type", "lifecycle_status", "is_enabled")
    search_fields = ("external_key", "display_name", "language", "compiler")


@admin.register(BuildUnitDefinition)
class BuildUnitDefinitionAdmin(admin.ModelAdmin):
    list_display = ("build_unit", "version", "source_kind", "definition_hash", "is_active", "created_at")
    list_filter = ("source_kind", "is_active")
    search_fields = ("definition_hash",)


@admin.register(BuildVersion)
class BuildVersionAdmin(admin.ModelAdmin):
    list_display = ("build_unit", "version_text", "branch_name", "branch_kind", "is_latest", "latest_success")
    list_filter = ("is_latest", "latest_success")
    search_fields = ("version_text", "commit_hash", "branch_name")


@admin.register(BuildExecution)
class BuildExecutionAdmin(admin.ModelAdmin):
    list_display = ("build_unit", "execution_number", "status", "branch_name", "started_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("execution_number", "external_execution_key", "commit_hash", "branch_name")


@admin.register(ExecutionArtifact)
class ExecutionArtifactAdmin(admin.ModelAdmin):
    list_display = ("build_execution", "artifact_type", "name", "download_url")
    list_filter = ("artifact_type",)
    search_fields = ("name", "path", "download_url")


@admin.register(StaticAnalysisResult)
class StaticAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("build_execution", "tool_name", "status", "created_at")
    list_filter = ("tool_name", "status")
    search_fields = ("tool_name", "summary")


@admin.register(DeploymentTarget)
class DeploymentTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "target_type", "status", "approval_required")
    list_filter = ("target_type", "status", "approval_required")
    search_fields = ("name",)


@admin.register(DeploymentExecution)
class DeploymentExecutionAdmin(admin.ModelAdmin):
    list_display = ("build_version", "deployment_target", "status", "requested_by", "approved_by")
    list_filter = ("status",)
    search_fields = ("requested_by", "approved_by")


@admin.register(BambooBuildUnit)
class BambooBuildUnitAdmin(admin.ModelAdmin):
    list_display = ("build_unit", "plan_key", "build_id", "bamboo_project_key", "repository_linkage_mode")
    search_fields = ("plan_key", "build_id", "bamboo_project_key")


@admin.register(BambooBuildInfo)
class BambooBuildInfoAdmin(admin.ModelAdmin):
    list_display = ("bamboo_build_unit", "build_key", "operating_system", "language", "compiler")
    list_filter = ("operating_system", "language", "compiler")
    search_fields = ("build_key", "build_command", "clean_command")


@admin.register(BambooPublishExecution)
class BambooPublishExecutionAdmin(admin.ModelAdmin):
    list_display = ("build_unit", "status", "return_code", "created_at")
    list_filter = ("status",)
    search_fields = ("message", "output")


@admin.register(JenkinsBuildUnit)
class JenkinsBuildUnitAdmin(admin.ModelAdmin):
    list_display = ("build_unit", "job_path", "job_type", "folder_path", "pipeline_kind")
    list_filter = ("job_type", "pipeline_kind")
    search_fields = ("job_path", "folder_path")


@admin.register(JenkinsNodeSnapshot)
class JenkinsNodeSnapshotAdmin(admin.ModelAdmin):
    list_display = ("resource_name", "executor_count", "busy_executors", "captured_at")
    search_fields = ("resource_name", "offline_reason")


@admin.register(JenkinsQueueItemSnapshot)
class JenkinsQueueItemSnapshotAdmin(admin.ModelAdmin):
    list_display = ("queue_item_key", "job_path", "status", "captured_at")
    list_filter = ("status",)
    search_fields = ("queue_item_key", "job_path", "waiting_reason")


@admin.register(SystemStatusSnapshot)
class SystemStatusSnapshotAdmin(admin.ModelAdmin):
    list_display = ("ci_provider", "resource_type", "resource_name", "status", "online", "busy", "captured_at")
    list_filter = ("ci_provider", "resource_type", "status", "online", "busy")
    search_fields = ("resource_name",)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("actor", "event_type", "target_type", "target_id", "created_at")
    list_filter = ("event_type", "target_type")
    search_fields = ("actor", "target_id")
