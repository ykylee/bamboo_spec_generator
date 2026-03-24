from __future__ import annotations

from django.contrib import admin

from .models import (
    BambooPublishExecution,
    BuildDefinitionHistory,
    BuildExecution,
    BuildPlan,
    BuildPlanDefinition,
    BuildVersion,
    Project,
    ProjectBuild,
    ProjectRepository,
    StaticAnalysisResult,
    SystemSetting,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("jira_project_key", "bitbucket_project_key", "representative_repo_slug")


@admin.register(ProjectRepository)
class ProjectRepositoryAdmin(admin.ModelAdmin):
    list_display = ("project", "repo_slug", "coverity_project", "coverity_stream", "is_representative")


@admin.register(ProjectBuild)
class ProjectBuildAdmin(admin.ModelAdmin):
    list_display = ("project", "build_name", "build_type", "runtime_stack", "build_plan")


@admin.register(BuildPlan)
class BuildPlanAdmin(admin.ModelAdmin):
    list_display = ("plan_key", "build_id", "latest_version")


@admin.register(BuildPlanDefinition)
class BuildPlanDefinitionAdmin(admin.ModelAdmin):
    list_display = ("build_plan", "project", "year", "source_kind", "definition_hash", "is_active", "created_at")


@admin.register(BuildVersion)
class BuildVersionAdmin(admin.ModelAdmin):
    list_display = ("build_plan", "version_text", "branch_kind", "commit_hash", "is_latest", "latest_success")


@admin.register(BuildExecution)
class BuildExecutionAdmin(admin.ModelAdmin):
    list_display = ("build_plan", "build_number", "result_status", "success", "started_at", "finished_at")


@admin.register(BambooPublishExecution)
class BambooPublishExecutionAdmin(admin.ModelAdmin):
    list_display = ("build_plan", "status", "return_code", "trigger_source", "created_at")


@admin.register(StaticAnalysisResult)
class StaticAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("build_execution", "tool_name", "status", "created_at")


@admin.register(BuildDefinitionHistory)
class BuildDefinitionHistoryAdmin(admin.ModelAdmin):
    list_display = ("build_plan", "change_type", "created_at")


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "value", "description")
