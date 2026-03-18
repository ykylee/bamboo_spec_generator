from __future__ import annotations

from django.shortcuts import render

from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries


def project_list(request):
    return render(request, "ui/project_list.html", {"projects": list_project_summaries()})


def project_detail(request, jira_project_key: str):
    return render(request, "ui/project_detail.html", {"project": get_project_detail(jira_project_key)})
