from __future__ import annotations

from django.core.management import BaseCommand

from apps.buildmeta.services import initialize_specs_draft_data


class Command(BaseCommand):
    help = "등록된 활성 정의를 기준으로 Specs 초안용 BuildInfo 데이터를 초기화한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset-existing",
            action="store_true",
            help="기존 BuildInfo를 삭제 후 현재 기준으로 다시 초기화한다.",
        )

    def handle(self, *args, **options) -> None:
        summary = initialize_specs_draft_data(reset_existing=options["reset_existing"])
        self.stdout.write(f"Initialized drafts: {summary['initializedCount']}")
        self.stdout.write(f"Updated drafts: {summary['updatedCount']}")
        self.stdout.write(f"Removed drafts: {summary['removedCount']}")
        self.stdout.write(self.style.SUCCESS(f"Skipped plans: {summary['skippedCount']}"))
