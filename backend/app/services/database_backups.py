import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
from sqlalchemy.engine import make_url


class BackupError(RuntimeError):
    pass


def _connection(
    database_url: str, database: str | None = None
) -> tuple[list[str], dict[str, str]]:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise BackupError("Only PostgreSQL backups are supported")
    args = [
        "--host",
        url.host or "localhost",
        "--port",
        str(url.port or 5432),
        "--username",
        url.username or "postgres",
        "--dbname",
        database or (url.database or "postgres"),
    ]
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    return args, env


def _run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, env=env, text=True, capture_output=True, check=True
        )
    except FileNotFoundError as exc:
        raise BackupError(f"Database tool is not installed: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise BackupError((exc.stderr or exc.stdout or str(exc)).strip()) from exc


def create_backup(database_url: str, output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    args, env = _connection(database_url)
    try:
        _run(
            [
                "pg_dump",
                *args,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(temporary),
            ],
            env,
        )
        verify_backup(temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def verify_backup(backup: Path) -> None:
    backup = backup.resolve()
    if not backup.is_file() or backup.stat().st_size == 0:
        raise BackupError("Backup file is missing or empty")
    result = _run(["pg_restore", "--list", str(backup)], os.environ.copy())
    if "alembic_version" not in result.stdout or "users" not in result.stdout:
        raise BackupError("Backup does not contain the WrtMonitor schema")


def restore_backup(database_url: str, backup: Path) -> None:
    verify_backup(backup)
    args, env = _connection(database_url)
    _run(
        [
            "pg_restore",
            *args,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            str(backup.resolve()),
        ],
        env,
    )


def verify_restore_drill(database_url: str, backup: Path) -> str:
    verify_backup(backup)
    url = make_url(database_url)
    drill_database = f"wrtmonitor_verify_{uuid4().hex[:12]}"
    maintenance = (
        url.set(database="postgres")
        .render_as_string(hide_password=False)
        .replace("postgresql+psycopg://", "postgresql://")
    )
    target = url.set(database=drill_database).render_as_string(hide_password=False)
    try:
        with psycopg.connect(maintenance, autocommit=True) as connection:
            connection.execute(f'CREATE DATABASE "{drill_database}"')
        args, env = _connection(target)
        _run(
            ["pg_restore", *args, "--no-owner", "--no-acl", str(backup.resolve())], env
        )
        with psycopg.connect(
            target.replace("postgresql+psycopg://", "postgresql://")
        ) as connection:
            version = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            users = connection.execute("SELECT count(*) FROM users").fetchone()
            if not version or users is None:
                raise BackupError("Restored database failed integrity checks")
            return f"migration={version[0]}, users={users[0]}"
    finally:
        with psycopg.connect(maintenance, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (drill_database,),
            )
            connection.execute(f'DROP DATABASE IF EXISTS "{drill_database}"')


def default_backup_path(directory: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"wrtmonitor-{timestamp}.dump"
