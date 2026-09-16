import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import Column, Integer, MetaData, Table

from backend.app.db import Base


def test_baseline_does_not_follow_runtime_metadata(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    snapshot = json.loads((directory / "0001_schema.json").read_text())
    spec = importlib.util.spec_from_file_location(
        "baseline", directory / "0001_initial_schema.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = MetaData()
    Table("future_table", metadata, Column("id", Integer, primary_key=True))
    monkeypatch.setattr(Base, "metadata", metadata)
    operations = MagicMock()
    monkeypatch.setattr(migration, "op", operations)
    migration.upgrade()
    assert [call.args[0] for call in operations.execute.call_args_list] == snapshot[
        "statements"
    ]
    assert not any(
        "future_table" in call.args[0] for call in operations.execute.call_args_list
    )
    migration.downgrade()
    assert [call.args[0] for call in operations.drop_table.call_args_list] == list(
        reversed(snapshot["tables"])
    )
