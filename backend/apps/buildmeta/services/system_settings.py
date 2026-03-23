from __future__ import annotations

from collections import defaultdict

from apps.buildmeta.models import SystemSetting


def get_system_setting(key: str, default: str = "") -> str:
    setting = SystemSetting.objects.filter(key=key).first()
    if setting is None:
        return default
    return setting.value


def set_system_setting(*, key: str, value: str, description: str = "") -> SystemSetting:
    setting, _ = SystemSetting.objects.update_or_create(
        key=key.strip(),
        defaults={
            "value": value,
            "description": description,
        },
    )
    return setting


def get_coverity_system_settings() -> dict[str, str | bool]:
    commit_enabled = get_system_setting(SystemSetting.KEY_COVERITY_COMMIT_ENABLED, "false").strip().lower()
    return {
        "connectUrl": get_system_setting(SystemSetting.KEY_COVERITY_CONNECT_URL),
        "onNewCert": get_system_setting(SystemSetting.KEY_COVERITY_ON_NEW_CERT, "trust"),
        "commitEnabled": commit_enabled in {"1", "true", "yes", "on"},
        "gitCloneUrlTemplate": get_system_setting(SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE),
    }


def build_git_clone_url(*, project_key: str, repo_slug: str) -> str:
    template = get_system_setting(SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE).strip()
    if not template:
        return ""

    values = defaultdict(
        str,
        {
            "project_key": project_key,
            "repo_slug": repo_slug,
            "project_key_lower": project_key.lower(),
            "repo_slug_lower": repo_slug.lower(),
        },
    )
    return template.format_map(values).strip()
