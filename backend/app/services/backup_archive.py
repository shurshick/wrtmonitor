"""Validate router backups without extracting untrusted archive members."""

import gzip
import io
from pathlib import PurePosixPath
import tarfile


MAX_UNPACKED_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 4096


def validate_router_backup(content: bytes) -> None:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
            unpacked = compressed.read(MAX_UNPACKED_BYTES + 1)
        if len(unpacked) > MAX_UNPACKED_BYTES:
            raise ValueError("Backup exceeds unpacked size limit")
        with tarfile.open(fileobj=io.BytesIO(unpacked), mode="r:") as archive:
            count = 0
            files = 0
            for member in archive:
                count += 1
                path = PurePosixPath(member.name)
                if (
                    count > MAX_MEMBERS
                    or path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != "etc"
                    or "\\" in member.name
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("Backup contains unsafe members")
                files += int(member.isfile())
            if not files:
                raise ValueError("Backup contains no configuration files")
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise ValueError("Invalid backup archive") from exc
