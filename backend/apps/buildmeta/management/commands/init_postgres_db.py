from __future__ import annotations

from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


class Command(BaseCommand):
    help = "PostgreSQL 개발 DB의 public 스키마를 초기화하고 migration을 다시 적용한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--database",
            default="default",
            help="초기화할 Django database alias",
        )
        parser.add_argument(
            "--schema",
            default="public",
            help="초기화할 PostgreSQL schema 이름",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="실제 schema 삭제 및 재생성을 수행한다",
        )

    def handle(self, *args, **options) -> None:
        alias = options["database"]
        schema = options["schema"]
        force = options["force"]
        connection = connections[alias]
        engine = connection.settings_dict["ENGINE"]

        if engine != "django.db.backends.postgresql":
            raise CommandError("init_postgres_db is only supported for PostgreSQL databases.")
        if not force:
            raise CommandError("init_postgres_db requires --force because it drops the target schema.")

        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            cursor.execute(f'CREATE SCHEMA "{schema}"')

        connection.close()
        self.stdout.write(f"Recreated PostgreSQL schema: {schema}")
        call_command("migrate", database=alias, interactive=False, verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS(f"Initialized PostgreSQL database using schema: {schema}"))
