from __future__ import annotations

from pathlib import Path

from django.core.management import BaseCommand, CommandError

from apps.buildmeta.services import load_definition_import_records, sync_definition_records


class Command(BaseCommand):
    help = "연도별 JSON 빌드 정의를 운영 메타데이터 DB와 반복 동기화한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--input-root",
            default="../build_info_json",
            help="연도별 JSON 빌드 정의 루트 디렉터리",
        )
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help="이번 입력에 없는 기존 활성 정의를 비활성화한다",
        )

    def handle(self, *args, **options) -> None:
        input_root = Path(options["input_root"]).resolve()
        if not input_root.exists():
            raise CommandError(f"Input root does not exist: {input_root}")

        records = load_definition_import_records(input_root)
        if not records:
            raise CommandError(f"No JSON build definitions found under: {input_root}")

        summary = sync_definition_records(
            records,
            deactivate_missing=options["deactivate_missing"],
        )
        self.stdout.write(f"Synchronized build definitions from: {input_root}")
        self.stdout.write(f"Imported definitions: {summary['importedCount']}")
        self.stdout.write(f"Activated definitions: {summary['activatedCount']}")
        self.stdout.write(f"Unchanged definitions: {summary['unchangedCount']}")
        self.stdout.write(self.style.SUCCESS(f"Deactivated definitions: {summary['deactivatedCount']}"))
