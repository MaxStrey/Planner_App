from typer.testing import CliRunner

from planner import __version__
from planner.cli import app


def test_version_command_returns_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
