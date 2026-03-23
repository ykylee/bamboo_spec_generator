from __future__ import annotations

from django.urls import path

from .views import (
    build_plan_list,
    project_build_detail,
    project_build_info_detail,
    project_build_info_list,
    project_detail,
    project_list,
    project_repository_detail,
)


urlpatterns = [
    path("", project_list, name="project-list"),
    path("build-plans/", build_plan_list, name="build-plan-list"),
    path("projects/<str:jira_project_key>/", project_detail, name="project-detail"),
    path(
        "projects/<str:jira_project_key>/repositories/<str:repo_slug>/",
        project_repository_detail,
        name="project-repository-detail",
    ),
    path(
        "projects/<str:jira_project_key>/builds/<str:plan_key>/",
        project_build_detail,
        name="project-build-detail",
    ),
    path(
        "projects/<str:jira_project_key>/builds/<str:plan_key>/infos/",
        project_build_info_list,
        name="project-build-info-list",
    ),
    path(
        "projects/<str:jira_project_key>/builds/<str:plan_key>/infos/<str:build_key>/",
        project_build_info_detail,
        name="project-build-info-detail",
    ),
]
