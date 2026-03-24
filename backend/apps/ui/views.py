from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from apps.buildmeta.models import BuildPlan, BuildPlanBuildInfo, Project, ProjectRepository
from apps.buildmeta.selectors.definitions import get_build_plan_export_draft, get_build_plan_preview
from apps.buildmeta.selectors.executions import (
    list_build_plan_summaries,
    list_executions_by_plan_key,
    list_latest_failed_builds,
    list_publish_executions_by_plan_key,
)
from apps.buildmeta.selectors.projects import get_project_detail, list_project_summaries
from apps.buildmeta.services import (
    BambooOperationError,
    create_project,
    get_bamboo_plan_details,
    get_bamboo_plan_status,
    get_bamboo_system_settings,
    get_coverity_system_settings,
    initialize_specs_draft_data,
    initialize_specs_draft_for_plan,
    publish_bamboo_specs,
    queue_bamboo_plan_with_options,
    set_system_setting,
    update_build_plan_metadata,
    update_project,
    upsert_build_info,
)

from .forms import (
    BuildMetadataForm,
    BambooRunForm,
    BuildInfoMetadataForm,
    BuildPlanMetadataForm,
    CoveritySystemSettingsForm,
    ProjectMetadataForm,
    ProjectRegistrationForm,
    RepositoryMetadataForm,
)


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
        "navProjectSearchItems": _build_nav_project_search_items(all_projects),
    }
    if _is_partial_project_list_request(request):
        return render(request, "ui/_project_list_panel.html", context)
    return render(request, "ui/project_list.html", context)


def build_plan_list(request):
    plans = list_build_plan_summaries()
    query = request.GET.get("q", "").strip().lower()
    status_filter = request.GET.get("status", "all").strip().lower()

    if query:
        plans = [
            plan
            for plan in plans
            if query in plan["projectKey"].lower()
            or query in plan["buildName"].lower()
            or query in plan["planKey"].lower()
            or query in plan["buildId"].lower()
            or query in (plan["staticAnalysisToolVersion"] or "").lower()
            or query in (plan["coverityProject"] or "").lower()
            or query in (plan["repositorySlug"] or "").lower()
        ]

    if status_filter == "attention":
        plans = [
            plan
            for plan in plans
            if not plan["repositorySlug"]
            or plan["latestSuccess"] is False
            or not plan["staticAnalysisToolVersion"]
            or not plan["coverityProject"]
        ]
    elif status_filter == "failed":
        plans = [plan for plan in plans if plan["latestSuccess"] is False]

    failed_count = sum(1 for plan in plans if plan["latestSuccess"] is False)
    linked_count = sum(1 for plan in plans if plan["repositorySlug"])
    context = {
        "plans": plans,
        "statusFilter": status_filter,
        "query": request.GET.get("q", "").strip(),
        "summary": {
            "totalPlans": len(plans),
            "linkedPlans": linked_count,
            "failedPlans": failed_count,
        },
        "failedBuilds": list_latest_failed_builds(),
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
    }
    return render(request, "ui/build_plan_list.html", context)


def coverity_settings(request):
    settings_payload = get_coverity_system_settings()
    bamboo_settings = get_bamboo_system_settings()
    form = CoveritySystemSettingsForm(
        initial={
                "connect_url": settings_payload["connectUrl"],
                "on_new_cert": settings_payload["onNewCert"],
                "commit_enabled": settings_payload["commitEnabled"],
                "repository_linkage_mode": settings_payload["repositoryLinkageMode"],
                "git_clone_url_template": settings_payload["gitCloneUrlTemplate"],
                "bamboo_server_url": bamboo_settings["serverUrl"],
            }
        )
    message = ""
    error = ""
    init_summary = None

    if request.method == "POST":
        form_kind = request.POST.get("form_kind", "").strip()
        if form_kind == "system_settings":
            form = CoveritySystemSettingsForm(request.POST)
            if form.is_valid():
                set_system_setting(
                    key="coverity.connect.url",
                    value=form.cleaned_data["connect_url"].strip(),
                    description="Coverity Connect URL",
                )
                set_system_setting(
                    key="coverity.connect.on_new_cert",
                    value=form.cleaned_data["on_new_cert"].strip() or "trust",
                    description="Coverity on-new-cert policy",
                )
                set_system_setting(
                    key="coverity.commit.enabled",
                    value="true" if form.cleaned_data["commit_enabled"] else "false",
                    description="Coverity commit enabled flag",
                )
                set_system_setting(
                    key="repository.git.clone_url_template",
                    value=form.cleaned_data["git_clone_url_template"].strip(),
                    description="Git clone URL template",
                )
                set_system_setting(
                    key="repository.linkage_mode",
                    value=form.cleaned_data["repository_linkage_mode"].strip() or "linked",
                    description="Repository linkage mode",
                )
                set_system_setting(
                    key="bamboo.server.url",
                    value=form.cleaned_data["bamboo_server_url"].strip(),
                    description="Bamboo server URL",
                )
                message = "운영 설정을 저장했습니다."
            else:
                error = "시스템 설정 입력값을 다시 확인해 주세요."
        elif form_kind == "init_specs_drafts":
            init_summary = initialize_specs_draft_data(reset_existing=True)
            message = "등록된 샘플의 Specs 초안 데이터를 현재 기준으로 다시 초기화했습니다."

    context = {
        "form": form,
        "message": message,
        "error": error,
        "initSummary": init_summary,
        "bambooSettings": get_bamboo_system_settings(),
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
    }
    return render(request, "ui/coverity_settings.html", context)


def project_detail(request, jira_project_key: str):
    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/project_detail.html", {"project": None})

    edit_form = ProjectMetadataForm(initial=_build_project_metadata_initial(project))
    repository_add_form = RepositoryMetadataForm()
    build_add_form = BuildMetadataForm()
    edit_error = ""
    repository_add_error = ""
    build_add_error = ""
    edit_open = request.GET.get("edit", "").lower() in {"1", "true", "open"}
    repository_add_open = request.GET.get("add_repository", "").lower() in {"1", "true", "open"}
    build_add_open = request.GET.get("add_build", "").lower() in {"1", "true", "open"}

    if request.method == "POST":
        form_kind = request.POST.get("form_kind", "").strip()
        if form_kind == "project":
            edit_form = ProjectMetadataForm(request.POST)
            edit_open = True
            if edit_form.is_valid():
                try:
                    payload = _build_project_metadata_payload(project, edit_form)
                    project = update_project(jira_project_key, payload)
                except ValueError as exc:
                    edit_error = str(exc)
                else:
                    if project is None:
                        return render(request, "ui/project_detail.html", {"project": None})
                    return redirect("project-detail", jira_project_key=project["jiraProjectKey"])
        elif form_kind == "repository":
            repository_add_form = RepositoryMetadataForm(request.POST)
            repository_add_open = True
            if repository_add_form.is_valid():
                try:
                    payload = _build_repository_append_payload(project, repository_add_form)
                    update_project(jira_project_key, payload)
                except ValueError as exc:
                    repository_add_error = str(exc)
                else:
                    return redirect(
                        "project-repository-detail",
                        jira_project_key=jira_project_key,
                        repo_slug=repository_add_form.cleaned_data["repo_slug"].strip(),
                    )
        elif form_kind == "build":
            build_add_form = BuildMetadataForm(request.POST)
            build_add_open = True
            if build_add_form.is_valid():
                try:
                    payload = _build_plan_append_payload(project, build_add_form)
                    update_project(jira_project_key, payload)
                except ValueError as exc:
                    build_add_error = str(exc)
                else:
                    return redirect(
                        "project-build-detail",
                        jira_project_key=jira_project_key,
                        plan_key=build_add_form.cleaned_data["plan_key"].strip(),
                    )

    context = {
        "project": project,
        "editForm": edit_form,
        "editError": edit_error,
        "editOpen": edit_open,
        "repositoryAddForm": repository_add_form,
        "repositoryAddError": repository_add_error,
        "repositoryAddOpen": repository_add_open,
        "buildAddForm": build_add_form,
        "buildAddError": build_add_error,
        "buildAddOpen": build_add_open,
        "registrationSuggestions": _build_registration_suggestions(),
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
        "repositoryEntries": _build_repository_entries(project),
    }
    return render(request, "ui/project_detail.html", context)


def project_repository_detail(request, jira_project_key: str, repo_slug: str):
    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/repository_detail.html", {"project": None, "repository": None})

    repository = next((item for item in project["repositories"] if item["repoSlug"] == repo_slug), None)
    if repository is None:
        return render(request, "ui/repository_detail.html", {"project": project, "repository": None})

    linked_builds = [
        build
        for build in project["builds"]
        if build["repositorySlug"] == repo_slug
    ]
    context = {
        "project": project,
        "repository": repository,
        "linkedBuilds": linked_builds,
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
    }
    return render(request, "ui/repository_detail.html", context)


def project_build_detail(request, jira_project_key: str, plan_key: str):
    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/build_detail.html", {"project": None, "build": None})

    build = next((item for item in project["builds"] if item["planKey"] == plan_key), None)
    if build is None:
        return render(request, "ui/build_detail.html", {"project": project, "build": None})

    metadata_form = BuildPlanMetadataForm(initial=_build_build_plan_metadata_initial(build))
    build_info_form = BuildInfoMetadataForm()
    metadata_error = ""
    build_info_error = ""
    draft_refresh_message = ""
    draft_refresh_error = ""
    bamboo_message = ""
    bamboo_error = ""
    bamboo_run_form = BambooRunForm(initial={"execute_all_stages": True})
    metadata_open = request.GET.get("edit", "").lower() in {"1", "true", "open"}
    build_info_open = request.GET.get("add_build_info", "").lower() in {"1", "true", "open"}

    if request.method == "POST":
        form_kind = request.POST.get("form_kind", "").strip()
        if form_kind == "build_plan_metadata":
            metadata_form = BuildPlanMetadataForm(request.POST)
            metadata_open = True
            if metadata_form.is_valid():
                update_build_plan_metadata(
                    plan_key=plan_key,
                    static_analysis_tool_version=metadata_form.cleaned_data["static_analysis_tool_version"],
                    coverity_project=metadata_form.cleaned_data["coverity_project"],
                )
                return redirect("project-build-detail", jira_project_key=jira_project_key, plan_key=plan_key)
            metadata_error = "빌드 플랜 메타데이터를 다시 확인해 주세요."
        elif form_kind == "build_info":
            build_info_form = BuildInfoMetadataForm(request.POST)
            build_info_open = True
            if build_info_form.is_valid():
                upsert_build_info(
                    plan_key=plan_key,
                    build_key=build_info_form.cleaned_data["build_key"],
                    operating_system=build_info_form.cleaned_data["operating_system"],
                    pre_process=build_info_form.cleaned_data["pre_process"],
                    build_command=build_info_form.cleaned_data["build_command"],
                    clean_command=build_info_form.cleaned_data["clean_command"],
                    language=build_info_form.cleaned_data["language"],
                    compiler=build_info_form.cleaned_data["compiler"],
                    analysis_excluded_files=build_info_form.cleaned_data["analysis_excluded_files"],
                    coverity_stream=build_info_form.cleaned_data["coverity_stream"],
                    build_sub_path=build_info_form.cleaned_data["build_sub_path"],
                )
                return redirect("project-build-detail", jira_project_key=jira_project_key, plan_key=plan_key)
            build_info_error = "빌드 정보 입력값을 다시 확인해 주세요."
        elif form_kind == "refresh_specs_draft":
            refresh_summary = initialize_specs_draft_for_plan(plan_key=plan_key, reset_existing=False)
            if refresh_summary["initializedCount"] or refresh_summary["updatedCount"]:
                draft_refresh_message = "이 플랜의 Specs 초안 데이터를 현재 기준으로 다시 채웠습니다."
            else:
                draft_refresh_error = "다시 채울 초안 데이터가 없어 기존 상태를 유지했습니다."
        elif form_kind == "bamboo_publish":
            try:
                result = publish_bamboo_specs(plan_key)
            except BambooOperationError as exc:
                bamboo_error = str(exc)
            else:
                if result["success"]:
                    bamboo_message = result["message"]
                else:
                    bamboo_error = result["output"] or result["message"]
        elif form_kind == "bamboo_run":
            bamboo_run_form = BambooRunForm(request.POST)
            if bamboo_run_form.is_valid():
                try:
                    result = queue_bamboo_plan_with_options(
                        plan_key,
                        stage=bamboo_run_form.cleaned_data["stage"],
                        execute_all_stages=bamboo_run_form.cleaned_data["execute_all_stages"],
                        custom_revision=bamboo_run_form.cleaned_data["custom_revision"],
                        variables=_parse_bamboo_variables_text(bamboo_run_form.cleaned_data["variables_text"]),
                    )
                except BambooOperationError as exc:
                    bamboo_error = str(exc)
                else:
                    bamboo_message = f"{result['message']} ({result['fullPlanKey']})"
            else:
                bamboo_error = "Bamboo 실행 입력값을 다시 확인해 주세요."

    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/build_detail.html", {"project": None, "build": None})

    build = next((item for item in project["builds"] if item["planKey"] == plan_key), None)
    if build is None:
        return render(request, "ui/build_detail.html", {"project": project, "build": None})

    repository = next(
        (item for item in project["repositories"] if item["repoSlug"] == build["repositorySlug"]),
        None,
    )
    bamboo_status = get_bamboo_plan_status(plan_key)
    context = {
        "project": project,
        "build": build,
        "repository": repository,
        "metadataForm": metadata_form,
        "metadataError": metadata_error,
        "metadataOpen": metadata_open,
        "buildInfoForm": build_info_form,
        "buildInfoError": build_info_error,
        "buildInfoOpen": build_info_open,
        "buildInfoEntries": _list_build_info_entries(plan_key),
        "buildPlanExportDraft": get_build_plan_export_draft(plan_key),
        "buildPlanPreview": get_build_plan_preview(plan_key),
        "draftRefreshMessage": draft_refresh_message,
        "draftRefreshError": draft_refresh_error,
        "bambooStatus": bamboo_status,
        "bambooMessage": bamboo_message,
        "bambooError": bamboo_error,
        "bambooRunForm": bamboo_run_form,
        "bambooPublishExecutions": list_publish_executions_by_plan_key(plan_key),
        "registrationSuggestions": _build_registration_suggestions(),
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
    }
    return render(request, "ui/build_detail.html", context)


def project_bamboo_plan_detail(request, jira_project_key: str, plan_key: str):
    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/bamboo_plan_detail.html", {"project": None, "build": None, "bambooPlan": None})

    build = next((item for item in project["builds"] if item["planKey"] == plan_key), None)
    if build is None:
        return render(request, "ui/bamboo_plan_detail.html", {"project": project, "build": None, "bambooPlan": None})

    try:
        bamboo_plan = get_bamboo_plan_details(plan_key)
        bamboo_error = ""
    except BambooOperationError as exc:
        bamboo_plan = None
        bamboo_error = str(exc)

    context = {
        "project": project,
        "build": build,
        "bambooPlan": bamboo_plan,
        "bambooError": bamboo_error,
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
    }
    return render(request, "ui/bamboo_plan_detail.html", context)


def project_build_info_list(request, jira_project_key: str, plan_key: str):
    return redirect(f"/projects/{jira_project_key}/builds/{plan_key}/?add_build_info=open")


def project_build_info_detail(request, jira_project_key: str, plan_key: str, build_key: str):
    project = get_project_detail(jira_project_key)
    if project is None:
        return render(request, "ui/build_info_detail.html", {"project": None, "build": None, "buildInfo": None})

    build = next((item for item in project["builds"] if item["planKey"] == plan_key), None)
    if build is None:
        return render(request, "ui/build_info_detail.html", {"project": project, "build": None, "buildInfo": None})

    build_info = BuildPlanBuildInfo.objects.filter(build_plan__plan_key=plan_key, build_key=build_key).first()
    if build_info is None:
        return render(request, "ui/build_info_detail.html", {"project": project, "build": build, "buildInfo": None})

    form = BuildInfoMetadataForm(initial=_build_info_initial(build_info))
    error = ""
    if request.method == "POST":
        form = BuildInfoMetadataForm(request.POST)
        if form.is_valid():
            upsert_build_info(
                plan_key=plan_key,
                build_key=form.cleaned_data["build_key"],
                operating_system=form.cleaned_data["operating_system"],
                pre_process=form.cleaned_data["pre_process"],
                build_command=form.cleaned_data["build_command"],
                clean_command=form.cleaned_data["clean_command"],
                language=form.cleaned_data["language"],
                compiler=form.cleaned_data["compiler"],
                analysis_excluded_files=form.cleaned_data["analysis_excluded_files"],
                coverity_stream=form.cleaned_data["coverity_stream"],
                build_sub_path=form.cleaned_data["build_sub_path"],
            )
            return redirect(
                "project-build-info-detail",
                jira_project_key=jira_project_key,
                plan_key=plan_key,
                build_key=form.cleaned_data["build_key"].strip(),
            )
        error = "빌드 정보 입력값을 다시 확인해 주세요."

    repository = next(
        (item for item in project["repositories"] if item["repoSlug"] == build["repositorySlug"]),
        None,
    )
    context = {
        "project": project,
        "build": build,
        "repository": repository,
        "buildInfo": _serialize_build_info(build_info),
        "buildInfoForm": form,
        "buildInfoError": error,
        "executionGroups": _list_execution_groups(plan_key),
        "navProjectSearchItems": _build_nav_project_search_items(list_project_summaries()),
    }
    return render(request, "ui/build_info_detail.html", context)


def _build_pagination_base_query(request) -> str:
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    if not encoded:
        return ""
    return f"{encoded}&"


def _is_partial_project_list_request(request) -> bool:
    return (
        request.method == "GET"
        and request.GET.get("partial") == "project-list"
        and request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


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
        "staticAnalysisToolVersions": list(
            BuildPlan.objects.exclude(static_analysis_tool_version="")
            .order_by("static_analysis_tool_version")
            .values_list("static_analysis_tool_version", flat=True)
            .distinct()
        ),
        "coverityStreams": list(
            ProjectRepository.objects.exclude(coverity_stream="")
            .order_by("coverity_stream")
            .values_list("coverity_stream", flat=True)
            .distinct()
        ),
    }


def _build_nav_project_search_items(projects: list[dict]) -> list[dict]:
    return [
        {
            "jiraProjectKey": project["jiraProjectKey"],
            "bitbucketProjectKey": project["bitbucketProjectKey"],
            "representativeRepoSlug": project.get("representativeRepoSlug") or "",
            "searchText": " ".join(
                filter(
                    None,
                    [
                        project["jiraProjectKey"].lower(),
                        project["bitbucketProjectKey"].lower(),
                        (project.get("representativeRepoSlug") or "").lower(),
                    ],
                )
            ),
        }
        for project in projects
    ]


def _build_project_metadata_initial(project: dict) -> dict:
    return {
        "bitbucket_project_key": project["bitbucketProjectKey"],
        "representative_repo_slug": project["representativeRepoSlug"],
    }


def _build_build_plan_metadata_initial(build: dict) -> dict:
    return {
        "static_analysis_tool_version": build["staticAnalysisToolVersion"],
        "coverity_project": build["coverityProject"],
    }


def _build_info_initial(build_info: BuildPlanBuildInfo) -> dict:
    return {
        "build_key": build_info.build_key,
        "operating_system": build_info.operating_system,
        "pre_process": build_info.pre_process,
        "build_command": build_info.build_command,
        "clean_command": build_info.clean_command,
        "language": build_info.language,
        "compiler": build_info.compiler,
        "analysis_excluded_files": build_info.analysis_excluded_files,
        "coverity_stream": build_info.coverity_stream,
        "build_sub_path": build_info.build_sub_path,
    }


def _build_project_payload_from_detail(project: dict) -> dict:
    return {
        "jiraProjectKey": project["jiraProjectKey"],
        "bitbucketProjectKey": project["bitbucketProjectKey"],
        "representativeRepoSlug": project["representativeRepoSlug"],
        "repositories": [
            {
                "repoSlug": repository["repoSlug"],
                "coverityProject": repository["coverityProject"],
                "coverityStream": repository["coverityStream"],
                "isRepresentative": repository["isRepresentative"],
            }
            for repository in project["repositories"]
        ],
        "builds": [
            {
                "buildName": build["buildName"],
                "buildType": build["buildType"],
                "runtimeStack": build["runtimeStack"],
                "buildId": build["buildId"],
                "planKey": build["planKey"],
                "repositorySlug": build["repositorySlug"],
            }
            for build in project["builds"]
        ],
    }


def _build_project_metadata_payload(project: dict, edit_form: ProjectMetadataForm) -> dict:
    payload = _build_project_payload_from_detail(project)
    representative_repo_slug = edit_form.cleaned_data["representative_repo_slug"].strip()
    repository_slugs = {repository["repoSlug"] for repository in payload["repositories"]}
    if representative_repo_slug not in repository_slugs:
        raise ValueError("대표 저장소는 등록한 저장소 목록 중 하나여야 합니다.")

    payload["bitbucketProjectKey"] = edit_form.cleaned_data["bitbucket_project_key"].strip()
    payload["representativeRepoSlug"] = representative_repo_slug
    for repository in payload["repositories"]:
        repository["isRepresentative"] = repository["repoSlug"] == representative_repo_slug
    return payload


def _build_repository_append_payload(project: dict, add_form: RepositoryMetadataForm) -> dict:
    payload = _build_project_payload_from_detail(project)
    payload["repositories"].append(
        {
            "repoSlug": add_form.cleaned_data["repo_slug"].strip(),
            "coverityProject": add_form.cleaned_data["coverity_project"].strip(),
            "coverityStream": add_form.cleaned_data["coverity_stream"].strip(),
            "isRepresentative": False,
        }
    )
    return payload


def _build_plan_append_payload(project: dict, add_form: BuildMetadataForm) -> dict:
    payload = _build_project_payload_from_detail(project)
    payload["builds"].append(
        {
            "buildName": add_form.cleaned_data["build_name"].strip(),
            "buildType": add_form.cleaned_data["build_type"].strip(),
            "runtimeStack": add_form.cleaned_data["runtime_stack"].strip(),
            "buildId": add_form.cleaned_data["build_id"].strip(),
            "planKey": add_form.cleaned_data["plan_key"].strip(),
            "repositorySlug": add_form.cleaned_data["build_repository_slug"].strip(),
        }
    )
    return payload


def _build_repository_linked_build_counts(project: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for build in project["builds"]:
        counts[build["repositorySlug"]] = counts.get(build["repositorySlug"], 0) + 1
    return counts


def _build_repository_entries(project: dict) -> list[dict]:
    linked_build_counts = _build_repository_linked_build_counts(project)
    return [
        {**repository, "linkedBuildCount": linked_build_counts.get(repository["repoSlug"], 0)}
        for repository in project["repositories"]
    ]


def _serialize_build_info(build_info: BuildPlanBuildInfo) -> dict:
    return {
        "buildKey": build_info.build_key,
        "operatingSystem": build_info.operating_system,
        "preProcess": build_info.pre_process,
        "buildCommand": build_info.build_command,
        "cleanCommand": build_info.clean_command,
        "language": build_info.language,
        "compiler": build_info.compiler,
        "analysisExcludedFiles": build_info.analysis_excluded_files,
        "coverityStream": build_info.coverity_stream,
        "buildSubPath": build_info.build_sub_path,
        "executionCount": build_info.executions.count(),
    }


def _list_build_info_entries(plan_key: str) -> list[dict]:
    return [
        _serialize_build_info(build_info)
        for build_info in BuildPlanBuildInfo.objects.filter(build_plan__plan_key=plan_key)
        .prefetch_related("executions")
        .order_by("build_key")
    ]


def _list_execution_groups(plan_key: str) -> list[dict]:
    executions = list_executions_by_plan_key(plan_key) or []
    grouped: dict[str, dict] = {}
    for execution in executions:
        build_key = execution["buildKey"] or "미분류"
        bucket = grouped.setdefault(
            build_key,
            {
                "buildKey": build_key,
                "executionCount": 0,
                "latestResult": "",
                "latestVersion": "",
                "toolNames": set(),
            },
        )
        bucket["executionCount"] += 1
        if not bucket["latestResult"]:
            bucket["latestResult"] = execution["resultStatus"] or "미기록"
            bucket["latestVersion"] = execution["version"]
        for result in execution["staticAnalysisResults"]:
            bucket["toolNames"].add(result["toolName"])
    return [
        {
            **bucket,
            "toolNames": sorted(bucket["toolNames"]),
        }
        for bucket in grouped.values()
    ]


def _parse_bamboo_variables_text(value: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, _sep, remainder = line.partition("=")
        variables[key.strip()] = remainder.strip()
    return variables
