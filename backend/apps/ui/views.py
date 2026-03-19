from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import render

from apps.buildmeta.selectors.executions import list_latest_failed_builds
from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries


def project_list(request):
    all_projects = list_project_summaries()
    projects = all_projects
    query = request.GET.get("q", "").strip().lower()
    status_filter = request.GET.get("status", "all").strip().lower()

    if query:
        projects = [
            project
            for project in projects
            if query in project["jiraProjectKey"].lower()
            or query in project["bitbucketProjectKey"].lower()
            or query in (project["representativeRepoSlug"] or "").lower()
        ]

    if status_filter == "attention":
        projects = [project for project in projects if project["needsAttention"]]
    elif status_filter == "healthy":
        projects = [project for project in projects if not project["needsAttention"]]

    paginator = Paginator(projects, 10)
    page_number = request.GET.get("page", "1")
    page_obj = paginator.get_page(page_number)
    attention_projects = [project for project in all_projects if project["needsAttention"]]
    context = {
        "projects": page_obj.object_list,
        "pageObj": page_obj,
        "query": request.GET.get("q", "").strip(),
        "statusFilter": status_filter,
        "summary": {
            "totalProjects": len(all_projects),
            "totalBuildPlans": sum(project["buildCount"] for project in all_projects),
            "attentionProjects": len(attention_projects),
            "missingRepresentativeRepos": sum(
                1 for project in all_projects if not project["representativeRepoSlug"]
            ),
            "generationReadyProjects": sum(1 for project in all_projects if project["generationReady"]),
        },
        "attentionProjects": attention_projects[:5],
        "failedBuilds": list_latest_failed_builds(),
        "paginationBaseQuery": _build_pagination_base_query(request),
    }
    return render(request, "ui/project_list.html", context)


def project_detail(request, jira_project_key: str):
    return render(request, "ui/project_detail.html", {"project": get_project_detail(jira_project_key)})


def _build_pagination_base_query(request) -> str:
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    if not encoded:
        return ""
    return f"{encoded}&"
