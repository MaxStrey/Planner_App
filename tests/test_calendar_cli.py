from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from planner.cli import app


def test_calendar_busy_missing_credentials() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["calendar", "busy"])

    assert result.exit_code != 0
    assert "Missing OAuth client secrets" in result.output


def test_calendar_busy_work_requires_config() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["calendar", "busy", "--calendars", "work"])

    assert result.exit_code != 0
    assert "Missing planner_config.toml" in result.output


def test_calendar_busy_work_empty_config() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("planner_config.toml").write_text(
            "[calendar]\nwork_calendar_ids = []\n", encoding="utf-8"
        )
        result = runner.invoke(app, ["calendar", "busy", "--calendars", "work"])

    assert result.exit_code != 0
    assert "No calendars found for mode 'work'." in result.output


def test_calendar_busy_partial_freebusy_success() -> None:
    runner = CliRunner()
    calendars = [
        {"id": "cal-1", "summary": "One", "selected": True, "primary": False},
        {"id": "cal-2", "summary": "Two", "selected": True, "primary": False},
    ]
    response = {
        "calendars": {
            "cal-1": {"errors": [{"domain": "global", "reason": "notFound"}]},
            "cal-2": {
                "busy": [
                    {
                        "start": "2024-01-01T10:00:00Z",
                        "end": "2024-01-01T11:00:00Z",
                    }
                ]
            },
        }
    }

    with patch("planner.cli.list_calendars", return_value=calendars), patch(
        "planner.cli.fetch_freebusy_response", return_value=response
    ):
        result = runner.invoke(app, ["calendar", "busy", "--calendars", "all"])

    assert result.exit_code == 0
    assert "Warning: FreeBusy error for cal-1" in result.output
    assert "->" in result.output
