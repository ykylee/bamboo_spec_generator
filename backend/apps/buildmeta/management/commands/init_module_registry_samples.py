from __future__ import annotations

import shutil
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand

from apps.buildmeta.models import ModuleActivation, ModuleAsset, ModuleAssetVersion, ModuleLoadEntry, ModuleLoadSnapshot
from apps.buildmeta.services import reload_module_assets, upload_module_asset
from apps.buildmeta.services.module_registry import MANAGED_MODULES_ROOT


SAMPLE_ROOT = Path(__file__).resolve().parents[2] / "sample_data" / "module_registry"

SAMPLE_ASSETS = [
    {
        "asset_kind": ModuleAsset.KIND_STAGE_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_COMMON,
        "module_id": "prepare",
        "path": SAMPLE_ROOT / "prepare-stage-v1.yaml",
        "activate": True,
    },
    {
        "asset_kind": ModuleAsset.KIND_STAGE_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_COMMON,
        "module_id": "prepare",
        "path": SAMPLE_ROOT / "prepare-stage-v2.yaml",
        "activate": True,
    },
    {
        "asset_kind": ModuleAsset.KIND_JOB_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_COMMON,
        "module_id": "prepare-linux",
        "path": SAMPLE_ROOT / "prepare-linux-job.yaml",
        "activate": True,
    },
    {
        "asset_kind": ModuleAsset.KIND_JOB_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_COMMON,
        "module_id": "verify-linux",
        "path": SAMPLE_ROOT / "verify-linux-job.yaml",
        "activate": True,
    },
    {
        "asset_kind": ModuleAsset.KIND_TASK_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_BAMBOO,
        "module_id": "bamboo-prepare-python",
        "path": SAMPLE_ROOT / "bamboo-prepare-python-task.yaml",
        "activate": True,
    },
    {
        "asset_kind": ModuleAsset.KIND_TASK_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_BAMBOO,
        "module_id": "bamboo-verify-python",
        "path": SAMPLE_ROOT / "bamboo-verify-python-task.yaml",
        "activate": True,
    },
    {
        "asset_kind": ModuleAsset.KIND_SCRIPT_TEMPLATE,
        "provider_scope": ModuleAsset.PROVIDER_COMMON,
        "module_id": "prepare-build",
        "path": SAMPLE_ROOT / "prepare-build.py",
        "activate": False,
    },
]

INVALID_SAMPLE_ASSETS = [
    {
        "asset_kind": ModuleAsset.KIND_STAGE_MODULE,
        "provider_scope": ModuleAsset.PROVIDER_COMMON,
        "module_id": "broken-stage",
        "path": SAMPLE_ROOT / "broken-stage.yaml",
        "activate": True,
    },
]


class Command(BaseCommand):
    help = "모듈 레지스트리 샘플 데이터를 업로드하고 필요 시 활성화 및 재로드를 수행한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset-existing",
            action="store_true",
            help="기존 모듈 자산과 managed_modules 디렉터리를 삭제한 뒤 다시 적재한다.",
        )
        parser.add_argument(
            "--include-invalid",
            action="store_true",
            help="로딩 오류 확인용 invalid stage 샘플도 함께 적재한다.",
        )

    def handle(self, *args, **options) -> None:
        if options["reset_existing"]:
            self._reset_existing_state()

        samples = list(SAMPLE_ASSETS)
        if options["include_invalid"]:
            samples.extend(INVALID_SAMPLE_ASSETS)

        uploaded_count = 0
        activated_count = 0
        for sample in samples:
            source_path = sample["path"]
            upload = SimpleUploadedFile(
                source_path.name,
                source_path.read_bytes(),
                content_type="application/octet-stream",
            )
            result = upload_module_asset(
                asset_kind=sample["asset_kind"],
                provider_scope=sample["provider_scope"],
                module_id=sample["module_id"],
                upload=upload,
                activate_after_upload=sample["activate"],
            )
            uploaded_count += 1
            activated_count += 1 if result["activated"] else 0

        reload_result = reload_module_assets(trigger_source=ModuleLoadSnapshot.SOURCE_COMMAND)

        self.stdout.write(f"Uploaded sample assets: {uploaded_count}")
        self.stdout.write(f"Activated sample assets: {activated_count}")
        self.stdout.write(
            "Reload result: "
            f"status={reload_result['status']} "
            f"loaded={reload_result['loadedCount']} "
            f"invalid={reload_result['invalidCount']} "
            f"skipped={reload_result['skippedCount']}"
        )
        self.stdout.write(self.style.SUCCESS("Module registry sample data initialized."))

    def _reset_existing_state(self) -> None:
        ModuleLoadEntry.objects.all().delete()
        ModuleLoadSnapshot.objects.all().delete()
        ModuleActivation.objects.all().delete()
        ModuleAssetVersion.objects.all().delete()
        ModuleAsset.objects.all().delete()
        if MANAGED_MODULES_ROOT.exists():
            shutil.rmtree(MANAGED_MODULES_ROOT)
