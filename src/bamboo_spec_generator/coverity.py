from __future__ import annotations

from pathlib import Path

from .model import BuildDefinition


REPO_ROOT = Path(__file__).resolve().parents[2]
COVERITY_TEMPLATE_PATH = REPO_ROOT / "docs" / "templates" / "coverity.yaml.template"


def generate_coverity_yaml(
    build: BuildDefinition,
    *,
    clean_command: str = "",
    coverity_project: str = "",
    coverity_stream: str = "",
    exclude_files_regex: str = "",
    connect_url: str = "",
    on_new_cert: str = "trust",
    commit_enabled: bool = False,
) -> str:
    template = COVERITY_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "<fill-build-command>": _escape_yaml(build.build.build_command),
        "<optional-clean-command>": _escape_yaml(clean_command),
        "<exclude_files_regex>": _escape_yaml(exclude_files_regex),
        "<coverity-project>": _escape_yaml(coverity_project),
        "<coverity-stream>": _escape_yaml(coverity_stream),
        "<optional-coverity-connect-url>": _escape_yaml(connect_url),
        "<coverity-on-new-cert>": _escape_yaml(on_new_cert),
        "<coverity-commit-enabled>": "true" if commit_enabled else "false",
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def coverity_language(language: str) -> str:
    mapping = {
        "java": "java",
        "nodejs": "javascript",
        "node.js": "javascript",
        "javascript": "javascript",
        "python": "python",
    }
    return mapping.get(language.lower(), language.lower())


def _escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
