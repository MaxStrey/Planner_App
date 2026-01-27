from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "planner_config.toml"


@dataclass(frozen=True)
class CalendarConfig:
    work_calendar_ids: list[str]


@dataclass(frozen=True)
class PlannerConfig:
    calendar: CalendarConfig


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
        try:
            import tomli as tomllib
        except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "TOML support is unavailable. Install tomli or use Python 3.11+."
            ) from exc

    return tomllib.loads(path.read_text(encoding="utf-8"))


def _find_config_path(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def load_config(path: Path | None = None) -> PlannerConfig:
    if path is None:
        path = _find_config_path(Path.cwd())
        if path is None:
            raise FileNotFoundError(
                f"Missing {CONFIG_FILENAME} in the repo root."
            )

    if not path.exists():
        raise FileNotFoundError(f"Missing {CONFIG_FILENAME} at {path}.")

    data = _load_toml(path)
    calendar = data.get("calendar")
    if not isinstance(calendar, dict):
        raise ValueError(f"{CONFIG_FILENAME} missing [calendar] section.")
    work_calendar_ids = calendar.get("work_calendar_ids")
    if work_calendar_ids is None:
        raise ValueError(
            f"{CONFIG_FILENAME} missing calendar.work_calendar_ids."
        )
    if not isinstance(work_calendar_ids, list) or not all(
        isinstance(item, str) for item in work_calendar_ids
    ):
        raise ValueError(
            f"{CONFIG_FILENAME} calendar.work_calendar_ids must be a list of strings."
        )

    return PlannerConfig(
        calendar=CalendarConfig(work_calendar_ids=work_calendar_ids)
    )
