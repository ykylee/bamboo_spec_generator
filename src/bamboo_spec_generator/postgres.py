from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess


class PostgresError(RuntimeError):
    """Raised when PostgreSQL command execution fails."""


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    sslmode: str = "prefer"

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        return cls(
            host=os.environ.get("BAMBOO_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("BAMBOO_DB_PORT", "5432")),
            user=os.environ.get("BAMBOO_DB_USER", "postgres"),
            password=os.environ.get("BAMBOO_DB_PASSWORD", ""),
            database=os.environ.get("BAMBOO_DB_NAME", "postgres"),
            sslmode=os.environ.get("BAMBOO_DB_SSLMODE", "prefer"),
        )

    def masked_dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} sslmode={self.sslmode}"
        )


def schema_sql_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "designs" / "sql" / "build_metadata_schema.sql"


def load_schema_sql() -> str:
    return schema_sql_path().read_text(encoding="utf-8")


def build_psql_command(config: PostgresConfig, *, sql: str | None = None, sql_file: Path | None = None) -> list[str]:
    command = [
        "psql",
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--username",
        config.user,
        "--dbname",
        config.database,
        "--no-password",
        "--set",
        "ON_ERROR_STOP=1",
    ]
    if sql is not None:
        command.extend(["--command", sql])
    if sql_file is not None:
        command.extend(["--file", str(sql_file)])
    return command


def run_psql(
    config: PostgresConfig,
    *,
    sql: str | None = None,
    sql_file: Path | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if config.password:
        env["PGPASSWORD"] = config.password
    if config.sslmode:
        env["PGSSLMODE"] = config.sslmode
    try:
        return subprocess.run(
            build_psql_command(config, sql=sql, sql_file=sql_file),
            check=True,
            capture_output=capture_output,
            text=True,
            env=env,
        )
    except FileNotFoundError as error:
        raise PostgresError("psql command is not installed or not found in PATH.") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() if error.stderr else str(error)
        raise PostgresError(message) from error


def check_connection(config: PostgresConfig) -> str:
    result = run_psql(config, sql="select current_database(), current_user, version();")
    return result.stdout.strip()


def apply_schema(config: PostgresConfig) -> str:
    result = run_psql(config, sql_file=schema_sql_path())
    return result.stdout.strip()
