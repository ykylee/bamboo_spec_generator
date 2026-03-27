from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path

from apps.buildmeta.models import SystemSetting


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BAMBOO_TOKEN_PATH = REPO_ROOT / "ops" / "credentials" / ".credentials"
DEFAULT_JENKINS_TOKEN_PATH = REPO_ROOT / "ops" / "credentials" / ".jenkins_credentials"


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
        "repositoryLinkageMode": get_repository_linkage_mode(),
    }


def get_repository_system_settings() -> dict[str, str]:
    return {
        "gitCloneUrlTemplate": get_system_setting(SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE).strip(),
        "svnCheckoutUrlTemplate": get_system_setting(SystemSetting.KEY_SVN_CHECKOUT_URL_TEMPLATE).strip(),
        "githubBaseUrl": get_system_setting(SystemSetting.KEY_GITHUB_BASE_URL).strip(),
        "githubToken": get_system_setting(SystemSetting.KEY_GITHUB_TOKEN).strip(),
        "bitbucketBaseUrl": get_system_setting(SystemSetting.KEY_BITBUCKET_BASE_URL).strip(),
        "bitbucketToken": get_system_setting(SystemSetting.KEY_BITBUCKET_TOKEN).strip(),
        "giteaBaseUrl": get_system_setting(SystemSetting.KEY_GITEA_BASE_URL).strip(),
        "giteaToken": get_system_setting(SystemSetting.KEY_GITEA_TOKEN).strip(),
    }


def get_infra_readiness() -> dict[str, dict[str, str | bool]]:
    bamboo = get_bamboo_system_settings()
    jenkins = get_jenkins_system_settings()
    coverity = get_coverity_system_settings()
    repository = get_repository_system_settings()
    return {
        "bamboo": {
            "ready": bool(bamboo["serverUrl"]),
            "reason": "Bamboo Server URL이 설정되지 않았습니다.",
        },
        "jenkins": {
            "ready": bool(jenkins["serverUrl"]),
            "reason": "Jenkins Server URL이 설정되지 않았습니다.",
        },
        "coverity": {
            "ready": bool(coverity["connectUrl"]),
            "reason": "Coverity Connect URL이 설정되지 않았습니다.",
        },
        "repository_git": {
            "ready": bool(repository["gitCloneUrlTemplate"]),
            "reason": "Git Clone URL Template이 설정되지 않았습니다.",
        },
        "repository_svn": {
            "ready": bool(repository["svnCheckoutUrlTemplate"]),
            "reason": "SVN Checkout URL Template이 설정되지 않았습니다.",
        },
        "repository_github": {
            "ready": bool(repository["githubBaseUrl"]),
            "reason": "GitHub Base URL이 설정되지 않았습니다.",
        },
        "repository_bitbucket": {
            "ready": bool(repository["bitbucketBaseUrl"]),
            "reason": "Bitbucket Base URL이 설정되지 않았습니다.",
        },
        "repository_gitea": {
            "ready": bool(repository["giteaBaseUrl"]),
            "reason": "Gitea Base URL이 설정되지 않았습니다.",
        },
    }


def get_bamboo_system_settings() -> dict[str, str | bool]:
    env_declared = "BAMBOO_SERVER_TOKEN" in os.environ
    env_token = os.environ.get("BAMBOO_SERVER_TOKEN", "").strip()
    file_token = ""
    if not env_declared and DEFAULT_BAMBOO_TOKEN_PATH.is_file():
        file_token = DEFAULT_BAMBOO_TOKEN_PATH.read_text(encoding="utf-8").strip()
    return {
        "serverUrl": get_system_setting(SystemSetting.KEY_BAMBOO_SERVER_URL).strip(),
        "tokenConfigured": bool(env_token or file_token),
        "tokenSource": "env" if env_token else "file" if file_token else "",
        "tokenFilePath": str(DEFAULT_BAMBOO_TOKEN_PATH),
    }


def get_jenkins_system_settings() -> dict[str, str | bool]:
    env_token = os.environ.get("JENKINS_TOKEN", "").strip()
    settings_token = get_system_setting(SystemSetting.KEY_JENKINS_TOKEN).strip()
    file_token = ""
    if not env_token and not settings_token and DEFAULT_JENKINS_TOKEN_PATH.is_file():
        file_token = DEFAULT_JENKINS_TOKEN_PATH.read_text(encoding="utf-8").strip()
    effective_token = env_token or settings_token or file_token
    return {
        "serverUrl": get_system_setting(SystemSetting.KEY_JENKINS_SERVER_URL).strip(),
        "tokenConfigured": bool(effective_token),
        "tokenSource": "env" if env_token else "settings" if settings_token else "file" if file_token else "",
        "tokenValue": settings_token,
        "tokenFilePath": str(DEFAULT_JENKINS_TOKEN_PATH),
    }


def get_repository_linkage_mode() -> str:
    value = get_system_setting(SystemSetting.KEY_REPOSITORY_LINKAGE_MODE, "linked").strip().lower()
    if value == "create_if_missing":
        return "create_if_missing"
    return "linked"


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
