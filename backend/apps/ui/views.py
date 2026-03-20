from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from apps.buildmeta.models import Project, ProjectRepository
from apps.buildmeta.selectors.executions import list_latest_failed_builds
from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries
from apps.buildmeta.services import create_project, update_project

from .forms import ProjectRegistrationForm


def project_list(request):
    registration_form = ProjectRegistrationForm()
    registration_error = ""
    repository_rows = [_blank_repository_row()]
    build_rows = [_blank_build_row()]
    registration_open = request.GET.get("register", "").lower() in {"1", "true", "open"}

    if request.method == "POST":
        registration_form = ProjectRegistrationForm(request.POST)
        repository_rows = _extract_repository_rows(request.POST)
        build_rows = _extract_build_rows(request.POST)
        registration_open = True
        if registration_form.is_valid():
            try:
                payload = _build_project_payload(registration_form, repository_rows, build_rows)
                payload = create_project(payload)
            except ValueError as exc:
                registration_error = str(exc)
            else:
                return redirect("project-detail", jira_project_key=payload["jiraProjectKey"])

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
        },
        "attentionProjects": attention_projects[:5],
        "failedBuilds": list_latest_failed_builds(),
        "paginationBaseQuery": _build_pagination_base_query(request),
        "registrationForm": registration_form,
        "registrationError": registration_error,
        "repositoryRows": repository_rows,
        "buildRows": build_rows,
        "registrationOpen": registration_open,
        "registrationSuggestions": _build_registration_suggestions(),
    }
    return render(request, "ui/project_list.html", context)


def project_detail(request, jira_project_key: str):
    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/project_detail.html", {"project": None})

    edit_form = ProjectRegistrationForm(initial=_build_form_initial(project))
    edit_error = ""
    repository_rows = project["repositories"] or [_blank_repository_row()]
    build_rows = project["builds"] or [_blank_build_row()]
    edit_open = request.GET.get("edit", "").lower() in {"1", "true", "open"}

    if request.method == "POST":
        edit_form = ProjectRegistrationForm(request.POST)
        repository_rows = _extract_repository_rows(request.POST)
        build_rows = _extract_build_rows(request.POST)
        edit_open = True
        if edit_form.is_valid():
            try:
                payload = _build_project_payload(edit_form, repository_rows, build_rows)
                project = update_project(jira_project_key, payload)
            except ValueError as exc:
                edit_error = str(exc)
            else:
                if project is None:
                    return render(request, "ui/project_detail.html", {"project": None})
                return redirect("project-detail", jira_project_key=project["jiraProjectKey"])

    context = {
        "project": project,
        "editForm": edit_form,
        "editError": edit_error,
        "repositoryRows": repository_rows,
        "buildRows": build_rows,
        "editOpen": edit_open,
        "registrationSuggestions": _build_registration_suggestions(),
    }
    return render(request, "ui/project_detail.html", context)


def _build_pagination_base_query(request) -> str:
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    if not encoded:
        return ""
    return f"{encoded}&"


def _build_project_payload(registration_form: ProjectRegistrationForm, repository_rows: list[dict], build_rows: list[dict]) -> dict:
    repositories = [
        {
            "repoSlug": row["repoSlug"].strip(),
            "coverityProject": row["coverityProject"].strip(),
            "coverityStream": row["coverityStream"].strip(),
        }
        for row in repository_rows
        if any(value.strip() for value in row.values())
    ]
    builds = [
        {
            "buildName": row["buildName"].strip(),
            "buildType": row["buildType"].strip(),
            "runtimeStack": row["runtimeStack"].strip(),
            "buildId": row["buildId"].strip(),
            "planKey": row["planKey"].strip(),
            "repositorySlug": row["repositorySlug"].strip(),
        }
        for row in build_rows
        if any(value.strip() for value in row.values())
    ]
    if not repositories:
        raise ValueError("최소 1개 저장소를 입력해 주세요.")
    if not builds:
        raise ValueError("최소 1개 빌드를 입력해 주세요.")

    representative_repo_slug = registration_form.cleaned_data["representative_repo_slug"].strip()
    repository_slugs = {repository["repoSlug"] for repository in repositories}
    if representative_repo_slug not in repository_slugs:
        raise ValueError("대표 저장소는 등록한 저장소 목록 중 하나여야 합니다.")

    for repository in repositories:
        repository["isRepresentative"] = repository["repoSlug"] == representative_repo_slug
    for build in builds:
        if build["repositorySlug"] not in repository_slugs:
            raise ValueError(f"빌드 연결 저장소 '{build['repositorySlug']}' 가 저장소 목록에 없습니다.")

    return {
        "jiraProjectKey": registration_form.cleaned_data["jira_project_key"].strip(),
        "bitbucketProjectKey": registration_form.cleaned_data["bitbucket_project_key"].strip(),
        "representativeRepoSlug": representative_repo_slug,
        "repositories": repositories,
        "builds": builds,
    }


def _extract_repository_rows(post_data) -> list[dict]:
    repo_slugs = post_data.getlist("repo_slug")
    coverity_projects = post_data.getlist("coverity_project")
    coverity_streams = post_data.getlist("coverity_stream")
    row_count = max(len(repo_slugs), len(coverity_projects), len(coverity_streams), 1)
    rows = []
    for index in range(row_count):
        rows.append(
            {
                "repoSlug": repo_slugs[index] if index < len(repo_slugs) else "",
                "coverityProject": coverity_projects[index] if index < len(coverity_projects) else "",
                "coverityStream": coverity_streams[index] if index < len(coverity_streams) else "",
            }
        )
    return rows


def _extract_build_rows(post_data) -> list[dict]:
    build_names = post_data.getlist("build_name")
    build_types = post_data.getlist("build_type")
    runtime_stacks = post_data.getlist("runtime_stack")
    build_ids = post_data.getlist("build_id")
    plan_keys = post_data.getlist("plan_key")
    repository_slugs = post_data.getlist("build_repository_slug")
    row_count = max(
        len(build_names),
        len(build_types),
        len(runtime_stacks),
        len(build_ids),
        len(plan_keys),
        len(repository_slugs),
        1,
    )
    rows = []
    for index in range(row_count):
        rows.append(
            {
                "buildName": build_names[index] if index < len(build_names) else "",
                "buildType": build_types[index] if index < len(build_types) else "",
                "runtimeStack": runtime_stacks[index] if index < len(runtime_stacks) else "",
                "buildId": build_ids[index] if index < len(build_ids) else "",
                "planKey": plan_keys[index] if index < len(plan_keys) else "",
                "repositorySlug": repository_slugs[index] if index < len(repository_slugs) else "",
            }
        )
    return rows


def _blank_repository_row() -> dict:
    return {"repoSlug": "", "coverityProject": "", "coverityStream": ""}


def _blank_build_row() -> dict:
    return {
        "buildName": "",
        "buildType": "",
        "runtimeStack": "",
        "buildId": "",
        "planKey": "",
        "repositorySlug": "",
    }


def _build_registration_suggestions() -> dict:
    return {
        "jiraProjectKeys": list(
            Project.objects.order_by("jira_project_key").values_list("jira_project_key", flat=True).distinct()
        ),
        "bitbucketProjectKeys": list(
            Project.objects.order_by("bitbucket_project_key").values_list("bitbucket_project_key", flat=True).distinct()
        ),
        "repositorySlugs": list(
            ProjectRepository.objects.order_by("repo_slug").values_list("repo_slug", flat=True).distinct()
        ),
        "coverityProjects": list(
            ProjectRepository.objects.exclude(coverity_project="")
            .order_by("coverity_project")
            .values_list("coverity_project", flat=True)
            .distinct()
        ),
        "coverityStreams": list(
            ProjectRepository.objects.exclude(coverity_stream="")
            .order_by("coverity_stream")
            .values_list("coverity_stream", flat=True)
            .distinct()
        ),
    }


def _build_form_initial(project: dict) -> dict:
    return {
        "jira_project_key": project["jiraProjectKey"],
        "bitbucket_project_key": project["bitbucketProjectKey"],
        "representative_repo_slug": project["representativeRepoSlug"],
    }
