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
