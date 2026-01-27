from unittest.mock import patch

from typer.testing import CliRunner

from planner.cli import app


def test_calendar_list_formats_output() -> None:
    runner = CliRunner()
    calendars = [
        {
            "id": "primary",
            "summary": "Main",
            "selected": True,
            "primary": True,
        },
        {
            "id": "work",
            "summary": "Work",
            "selected": False,
            "primary": False,
        },
    ]

    with patch("planner.cli.list_calendars", return_value=calendars):
        result = runner.invoke(app, ["calendar", "list"])

    assert result.exit_code == 0
    assert result.output == (
        "selected=True primary Main  primary\n"
        "selected=False Work  work\n"
    )
