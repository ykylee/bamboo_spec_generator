from __future__ import annotations

from ninja import Router

from apps.api.schemas import CoveritySystemSettingsIn
from apps.buildmeta.models import SystemSetting
from apps.buildmeta.services import (
    get_coverity_system_settings,
    initialize_specs_draft_data,
    initialize_specs_draft_for_plan,
    set_system_setting,
)


router = Router(tags=["system-settings"])


@router.get("/coverity")
def get_coverity_settings(request) -> dict:
    return get_coverity_system_settings()


@router.put("/coverity")
def put_coverity_settings(request, payload: CoveritySystemSettingsIn) -> dict:
    set_system_setting(
        key=SystemSetting.KEY_COVERITY_CONNECT_URL,
        value=payload.connectUrl.strip(),
        description="Coverity Connect URL",
    )
    set_system_setting(
        key=SystemSetting.KEY_COVERITY_ON_NEW_CERT,
        value=payload.onNewCert.strip(),
        description="Coverity on-new-cert policy",
    )
    set_system_setting(
        key=SystemSetting.KEY_COVERITY_COMMIT_ENABLED,
        value="true" if payload.commitEnabled else "false",
        description="Coverity commit enabled flag",
    )
    set_system_setting(
        key=SystemSetting.KEY_GIT_CLONE_URL_TEMPLATE,
        value=payload.gitCloneUrlTemplate.strip(),
        description="Git clone URL template",
    )
    linkage_mode = payload.repositoryLinkageMode.strip().lower()
    set_system_setting(
        key=SystemSetting.KEY_REPOSITORY_LINKAGE_MODE,
        value="create_if_missing" if linkage_mode == "create_if_missing" else "linked",
        description="Repository linkage mode",
    )
    return get_coverity_system_settings()


@router.post("/specs-drafts/initialize")
def post_initialize_specs_drafts(request, resetExisting: bool = False) -> dict:
    return initialize_specs_draft_data(reset_existing=resetExisting)


@router.post("/specs-drafts/initialize/{planKey}")
def post_initialize_specs_draft_for_plan(request, planKey: str, resetExisting: bool = False) -> dict:
    return initialize_specs_draft_for_plan(plan_key=planKey, reset_existing=resetExisting)
