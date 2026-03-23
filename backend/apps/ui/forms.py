from __future__ import annotations

from django import forms


class ProjectRegistrationForm(forms.Form):
    jira_project_key = forms.CharField(
        label="Jira Project Key",
        max_length=64,
        widget=forms.TextInput(attrs={"list": "jira-project-key-options"}),
    )
    bitbucket_project_key = forms.CharField(
        label="Bitbucket Project Key",
        max_length=64,
        widget=forms.TextInput(attrs={"list": "bitbucket-project-key-options"}),
    )
    representative_repo_slug = forms.CharField(
        label="대표 저장소",
        max_length=255,
        widget=forms.TextInput(attrs={"list": "repository-slug-options"}),
    )


class ProjectMetadataForm(forms.Form):
    bitbucket_project_key = forms.CharField(
        label="Bitbucket Project Key",
        max_length=64,
        widget=forms.TextInput(attrs={"list": "bitbucket-project-key-options"}),
    )
    representative_repo_slug = forms.CharField(
        label="대표 저장소",
        max_length=255,
        widget=forms.TextInput(attrs={"list": "repository-slug-options"}),
    )


class RepositoryMetadataForm(forms.Form):
    repo_slug = forms.CharField(
        label="저장소 Slug",
        max_length=255,
        widget=forms.TextInput(attrs={"list": "repository-slug-options"}),
    )
    coverity_project = forms.CharField(
        label="Coverity Project",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"list": "coverity-project-options"}),
    )
    coverity_stream = forms.CharField(
        label="Coverity Stream",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"list": "coverity-stream-options"}),
    )


class BuildMetadataForm(forms.Form):
    build_name = forms.CharField(label="빌드 이름", max_length=255)
    build_type = forms.CharField(label="Build Type", max_length=128)
    runtime_stack = forms.CharField(label="Runtime Stack", max_length=128, required=False)
    build_id = forms.CharField(label="Build ID", max_length=255)
    plan_key = forms.CharField(label="Plan Key", max_length=64)
    build_repository_slug = forms.CharField(
        label="연결 저장소 Slug",
        max_length=255,
        widget=forms.TextInput(attrs={"list": "repository-slug-options"}),
    )


class BuildPlanMetadataForm(forms.Form):
    static_analysis_tool_version = forms.CharField(
        label="정적분석 도구 버전",
        max_length=128,
        required=False,
        widget=forms.TextInput(attrs={"list": "static-analysis-tool-version-options"}),
    )
    coverity_project = forms.CharField(
        label="Coverity Project",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"list": "coverity-project-options"}),
    )


class BuildInfoMetadataForm(forms.Form):
    build_key = forms.CharField(label="빌드키", max_length=128)
    pre_process = forms.CharField(label="Pre Process", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    build_command = forms.CharField(label="빌드 명령어", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    clean_command = forms.CharField(label="클린 명령어", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    language = forms.CharField(label="언어", max_length=64, required=False)
    compiler = forms.CharField(label="컴파일러", max_length=128, required=False)
    analysis_excluded_files = forms.CharField(
        label="분석 제외 파일",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    coverity_stream = forms.CharField(
        label="Coverity Stream",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"list": "coverity-stream-options"}),
    )
    build_sub_path = forms.CharField(label="빌드 Sub Path", max_length=255, required=False)
