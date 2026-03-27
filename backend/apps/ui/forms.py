from __future__ import annotations

from django import forms

from apps.buildmeta.models import Project, Repository


class ProjectRegistrationForm(forms.Form):
    ci_provider = forms.ChoiceField(
        label="CI Provider",
        choices=Project.PROVIDER_CHOICES,
        initial=Project.PROVIDER_BAMBOO,
        required=False,
    )
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
        required=False,
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
    repo_type = forms.ChoiceField(
        label="저장소 타입",
        choices=Repository.TYPE_CHOICES,
        initial=Repository.TYPE_BITBUCKET,
        required=False,
    )
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

    def clean_repo_type(self) -> str:
        value = (self.cleaned_data.get("repo_type") or "").strip()
        return value or Repository.TYPE_BITBUCKET


class BuildMetadataForm(forms.Form):
    REPOSITORY_LINKAGE_MODE_CHOICES = [
        ("linked", "linked"),
        ("create_if_missing", "create_if_missing"),
    ]

    build_name = forms.CharField(label="빌드 이름", max_length=255)
    build_type = forms.CharField(label="language", max_length=128)
    runtime_stack = forms.CharField(label="compiler", max_length=128, required=False)
    build_id = forms.CharField(label="Build ID", max_length=255)
    plan_key = forms.CharField(label="Plan Key", max_length=64)
    repository_linkage_mode = forms.ChoiceField(
        label="Bamboo 저장소 연결 방식",
        choices=REPOSITORY_LINKAGE_MODE_CHOICES,
        required=False,
        initial="linked",
    )
    build_repository_slug = forms.CharField(
        label="연결 저장소 Slug",
        max_length=255,
        widget=forms.TextInput(attrs={"list": "repository-slug-options"}),
    )


class BuildPlanMetadataForm(forms.Form):
    REPOSITORY_LINKAGE_MODE_OVERRIDE_CHOICES = [
        ("", "시스템 기본값 사용"),
        ("linked", "linked"),
        ("create_if_missing", "create_if_missing"),
    ]

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
    repository_linkage_mode_override = forms.ChoiceField(
        label="Repository Linkage Mode Override",
        choices=REPOSITORY_LINKAGE_MODE_OVERRIDE_CHOICES,
        required=False,
        initial="",
    )


class BuildInfoMetadataForm(forms.Form):
    build_key = forms.CharField(label="빌드키", max_length=128)
    operating_system = forms.CharField(label="OS", max_length=32, required=False)
    pre_process = forms.CharField(label="Pre Process", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    build_command = forms.CharField(label="빌드 명령어", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    clean_command = forms.CharField(label="클린 명령어", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    language = forms.CharField(label="language", max_length=64, required=False)
    compiler = forms.CharField(label="compiler", max_length=128, required=False)
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


class CoveritySystemSettingsForm(forms.Form):
    REPOSITORY_LINKAGE_MODE_CHOICES = [
        ("linked", "linked"),
        ("create_if_missing", "create_if_missing"),
    ]

    connect_url = forms.CharField(label="Coverity Connect URL", required=False)
    on_new_cert = forms.CharField(label="on-new-cert", max_length=64, required=False, initial="trust")
    commit_enabled = forms.BooleanField(label="Commit Enabled", required=False)
    repository_linkage_mode = forms.ChoiceField(
        label="Repository Linkage Mode",
        choices=REPOSITORY_LINKAGE_MODE_CHOICES,
        required=False,
        initial="linked",
    )
    git_clone_url_template = forms.CharField(
        label="Git Clone URL Template",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "https://git.example.com/scm/{project_key_lower}/{repo_slug}.git"}
        ),
    )
    svn_checkout_url_template = forms.CharField(
        label="SVN Checkout URL Template",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "https://svn.example.com/repos/{project_key_lower}/{repo_slug}"}
        ),
    )
    github_base_url = forms.CharField(
        label="GitHub Base URL",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "https://github.example.com"}),
    )
    github_token = forms.CharField(
        label="GitHub Token",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "optional"}),
    )
    bitbucket_base_url = forms.CharField(
        label="Bitbucket Base URL",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "https://bitbucket.example.com"}),
    )
    bitbucket_token = forms.CharField(
        label="Bitbucket Token",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "optional"}),
    )
    gitea_base_url = forms.CharField(
        label="Gitea Base URL",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "https://gitea.example.com"}),
    )
    gitea_token = forms.CharField(
        label="Gitea Token",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "optional"}),
    )
    bamboo_server_url = forms.CharField(
        label="Bamboo Server URL",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "https://bamboo.example.com"}
        ),
    )


class BambooRunForm(forms.Form):
    stage = forms.CharField(label="Stage", required=False, max_length=255)
    execute_all_stages = forms.BooleanField(label="Execute All Stages", required=False, initial=True)
    custom_revision = forms.CharField(
        label="Custom Revision",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "branch name, tag, or commit hash"}),
    )
    variables_text = forms.CharField(
        label="Variables",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "bamboo.variable.example=value"}),
    )

    def clean_variables_text(self) -> str:
        value = self.cleaned_data["variables_text"]
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        for line in lines:
            if "=" not in line:
                raise forms.ValidationError("변수는 `key=value` 형식으로 입력해야 합니다.")
            key, _sep, _rest = line.partition("=")
            if not key.strip():
                raise forms.ValidationError("변수 키는 비워둘 수 없습니다.")
        return value
