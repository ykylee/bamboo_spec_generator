from __future__ import annotations

from ninja import File, Form, Router
from ninja.files import UploadedFile

from apps.api.schemas import ModuleActivateIn, ModuleReloadIn
from apps.buildmeta.models import ModuleAsset, ModuleAssetVersion
from apps.buildmeta.services import (
    activate_module_asset_version,
    deactivate_module_asset,
    get_module_asset_detail,
    get_module_load_status,
    list_module_assets,
    reload_module_assets,
    upload_module_asset,
)


router = Router(tags=["module-registry"])


@router.get("/")
def get_modules(request, assetKind: str = "", providerScope: str = "", status: str = "") -> list[dict]:
    return list_module_assets(asset_kind=assetKind, provider_scope=providerScope, status=status)


@router.get("/load-status")
def get_modules_load_status(request) -> dict:
    return get_module_load_status()


@router.post("/uploads")
def post_module_upload(
    request,
    assetKind: str = Form(...),
    providerScope: str = Form(ModuleAsset.PROVIDER_COMMON),
    moduleId: str = Form(...),
    activateAfterUpload: bool = Form(False),
    file: UploadedFile = File(...),
) -> dict:
    return upload_module_asset(
        asset_kind=assetKind,
        provider_scope=providerScope,
        module_id=moduleId,
        upload=file,
        uploaded_by=getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else None,
        activate_after_upload=activateAfterUpload,
    )


@router.post("/reload")
def post_module_reload(request, payload: ModuleReloadIn) -> dict:
    return reload_module_assets(
        triggered_by=getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else None,
    )


@router.get("/{asset_id}")
def get_module_detail(request, asset_id: str) -> dict:
    return get_module_asset_detail(asset_id=asset_id)


@router.post("/{asset_id}/activate")
def post_module_activate(request, asset_id: str, payload: ModuleActivateIn) -> dict:
    asset = ModuleAsset.objects.get(pk=asset_id)
    version = ModuleAssetVersion.objects.get(pk=payload.versionId, asset=asset)
    return activate_module_asset_version(
        asset=asset,
        version=version,
        activated_by=getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else None,
    )


@router.post("/{asset_id}/deactivate")
def post_module_deactivate(request, asset_id: str) -> dict:
    asset = ModuleAsset.objects.get(pk=asset_id)
    return deactivate_module_asset(asset=asset)
