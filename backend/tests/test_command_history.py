from uuid import uuid4

from sqlalchemy.dialects import postgresql

from backend.app.services.commands import (
    TERMINAL_STATUSES,
    cleanup_device_command_history,
)
from backend.app.web.routes import templates


class Result:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class RecordingSession:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return Result(2)


def test_command_history_cleanup_targets_only_terminal_rows():
    db = RecordingSession()

    removed = cleanup_device_command_history(db, uuid4(), 30, 500)

    assert removed == 4
    assert len(db.statements) == 2
    compiled = [
        statement.compile(dialect=postgresql.dialect()) for statement in db.statements
    ]
    assert set(compiled[0].params["status_1"]) == TERMINAL_STATUSES
    assert set(compiled[1].params["status_1"]) == TERMINAL_STATUSES
    assert compiled[1].params["param_1"] == 500
    assert "queued" not in compiled[0].params["status_1"]
    assert "sent" not in compiled[0].params["status_1"]
    assert "running" not in compiled[0].params["status_1"]


def test_command_history_template_is_paginated_and_compact():
    html = templates.get_template("partials/commands.html").render(
        device=type("Device", (), {"id": uuid4()})(),
        commands=[
            {
                "command_type": "agent.update",
                "status": "success",
                "source": "web",
                "created_at": "2026-07-17T10:00:00+00:00",
                "completed_at": "2026-07-17T10:00:05+00:00",
                "last_error": None,
                "payload": {},
                "result": {},
            }
            for _ in range(5)
        ],
        command_pagination={
            "page": 1,
            "pages": 3,
            "total": 13,
            "start": 1,
            "end": 5,
            "retention_days": 30,
            "max_per_device": 500,
        },
    )

    assert html.count('class="command-item"') == 5
    assert "Показано 1–5 из 13" in html
    assert "command_page=2" in html
    assert "Хранятся 30 дней" in html
