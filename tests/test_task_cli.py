from pathlib import Path

import pytest
from typer.testing import CliRunner

from planner.cli import app


def _set_db_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "planner.db"
    monkeypatch.setenv("PLANNER_DB_PATH", str(db_path))
    return db_path


def test_task_add_list_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    _set_db_path(monkeypatch, tmp_path)

    result = runner.invoke(
        app,
        [
            "task",
            "add",
            "--title",
            "Write tests",
            "--due",
            "2025-01-01T10:00:00+00:00",
            "--est",
            "30",
        ],
    )
    assert result.exit_code == 0
    task_id = result.stdout.strip()
    assert task_id

    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert task_id in result.stdout
    assert "est=30" in result.stdout

    result = runner.invoke(app, ["task", "delete", task_id])
    assert result.exit_code == 0

    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_task_add_rejects_naive_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    _set_db_path(monkeypatch, tmp_path)

    result = runner.invoke(
        app,
        [
            "task",
            "add",
            "--title",
            "No timezone",
            "--due",
            "2025-01-01T10:00:00",
            "--est",
            "15",
        ],
    )

    assert result.exit_code != 0
    assert "timezone" in result.output
