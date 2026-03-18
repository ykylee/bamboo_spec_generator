from __future__ import annotations

from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


class Command(BaseCommand):
    help = "SQLite 개발 DB를 초기화하고 migration을 다시 적용한다."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--database",
            default="default",
            help="초기화할 Django database alias",
        )

    def handle(self, *args, **options) -> None:
        alias = options["database"]
        connection = connections[alias]
        engine = connection.settings_dict["ENGINE"]

        if engine != "django.db.backends.sqlite3":
            raise CommandError("init_dev_db is only supported for SQLite development databases.")

        db_name = connection.settings_dict["NAME"]
        if not db_name:
            raise CommandError("SQLite database path is not configured.")

        db_path = Path(db_name)
        connection.close()

        if db_path.exists():
            db_path.unlink()
            self.stdout.write(f"Deleted SQLite database: {db_path}")
        else:
            self.stdout.write(f"SQLite database does not exist yet: {db_path}")

        call_command("migrate", database=alias, interactive=False, verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS(f"Initialized SQLite development database: {db_path}"))
