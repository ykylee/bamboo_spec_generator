from __future__ import annotations

from pathlib import Path

from django.core.management import BaseCommand, CommandError

from apps.buildmeta.services import import_definition_records, load_definition_import_records


class Command(BaseCommand):
    help = "연도별 JSON 빌드 정의를 읽어 운영 메타데이터 DB에 적재한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--input-root",
            default="../build_info_json",
            help="연도별 JSON 빌드 정의 루트 디렉터리",
        )

    def handle(self, *args, **options) -> None:
        input_root = Path(options["input_root"]).resolve()
        if not input_root.exists():
            raise CommandError(f"Input root does not exist: {input_root}")

        records = load_definition_import_records(input_root)
        if not records:
            raise CommandError(f"No JSON build definitions found under: {input_root}")

        summary = import_definition_records(records)
        self.stdout.write(f"Imported build definitions from: {input_root}")
        self.stdout.write(f"Imported definitions: {summary['importedCount']}")
        self.stdout.write(self.style.SUCCESS(f"Activated definitions: {summary['activatedCount']}"))
