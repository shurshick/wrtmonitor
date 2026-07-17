import argparse
from pathlib import Path

from .config import load_settings
from .services.database_backups import (
    create_backup,
    default_backup_path,
    restore_backup,
    verify_backup,
    verify_restore_drill,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="WrtMonitor PostgreSQL backup utility")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("path", nargs="?", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("path", type=Path)
    drill = subparsers.add_parser("drill")
    drill.add_argument("path", type=Path)
    restore = subparsers.add_parser("restore")
    restore.add_argument("path", type=Path)
    restore.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    database_url = load_settings().database_url

    if args.command == "create":
        path = args.path or default_backup_path(Path("/backups"))
        print(create_backup(database_url, path))
    elif args.command == "verify":
        verify_backup(args.path)
        print("backup structure: OK")
    elif args.command == "drill":
        print(f"restore drill: OK ({verify_restore_drill(database_url, args.path)})")
    elif args.command == "restore":
        if not args.confirm:
            parser.error(
                "restore requires --confirm and a stopped WrtMonitor application"
            )
        restore_backup(database_url, args.path)
        print("restore: OK")


if __name__ == "__main__":
    main()
