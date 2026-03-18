from __future__ import annotations

from django.urls import path

from .views import project_detail, project_list


urlpatterns = [
    path("", project_list, name="project-list"),
    path("projects/<str:jira_project_key>/", project_detail, name="project-detail"),
]
