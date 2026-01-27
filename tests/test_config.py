from pathlib import Path

import pytest

from planner.config import load_config


def test_load_config_from_path(tmp_path: Path) -> None:
    config_path = tmp_path / "planner_config.toml"
    config_path.write_text(
        "[calendar]\nwork_calendar_ids = [\"cal-1\", \"cal-2\"]\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.calendar.work_calendar_ids == ["cal-1", "cal-2"]


def test_load_config_missing_section(tmp_path: Path) -> None:
    config_path = tmp_path / "planner_config.toml"
    config_path.write_text("title = \"planner\"\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing \\[calendar\\]"):
        load_config(config_path)
