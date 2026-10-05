import os
from pathlib import Path

import pytest

from backend.app.services import database_backups


@pytest.mark.skipif(os.name == "nt", reason="POSIX backup file permissions")
def test_backup_is_private_and_does_not_follow_predictable_tmp_symlink(
    tmp_path, monkeypatch
):
    output = tmp_path / "backup.dump"
    victim = tmp_path / "unrelated"
    victim.write_bytes(b"do-not-change")
    output.with_suffix(".dump.tmp").symlink_to(victim)

    def dump(command, env):
        target = Path(command[command.index("--file") + 1])
        assert target.stat().st_mode & 0o077 == 0
        target.write_bytes(b"database-backup")

    monkeypatch.setattr(database_backups, "_run", dump)
    monkeypatch.setattr(database_backups, "verify_backup", lambda path: None)
    database_backups.create_backup("postgresql://owner:password@localhost/db", output)
    assert output.read_bytes() == b"database-backup"
    assert output.stat().st_mode & 0o077 == 0
    assert victim.read_bytes() == b"do-not-change"
