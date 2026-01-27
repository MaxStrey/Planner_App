from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from enum import Enum
import uuid
import typer

from planner import __version__
from planner.calendar_api import (
    DEFAULT_TIMEZONE,
    fetch_freebusy_response,
    list_calendars,
)
from planner.config import load_config
from planner.db import connect, init_db

app = typer.Typer(help="Planner CLI", no_args_is_help=True)
calendar_app = typer.Typer(help="Calendar commands")
task_app = typer.Typer(help="Task commands")
app.add_typer(calendar_app, name="calendar")
app.add_typer(task_app, name="task")


@app.callback()
def cli() -> None:
    """Planner CLI."""
    # This callback exists to keep the CLI in group mode.
    return None


@app.command()
def version() -> None:
    """Print the Planner version."""
    typer.echo(__version__)


class CalendarScope(str, Enum):
    primary = "primary"
    selected = "selected"
    all = "all"
    work = "work"


@calendar_app.command("list")
def calendar_list() -> None:
    """List available calendars."""
    try:
        calendars = list_calendars()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        typer.echo(f"Calendar error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for item in calendars:
        selected_text = f"selected={item['selected']}"
        primary_text = " primary" if item.get("primary") else ""
        summary = item.get("summary", "")
        calendar_id = item.get("id", "")
        typer.echo(f"{selected_text}{primary_text} {summary}  {calendar_id}")


@calendar_app.command("busy")
def calendar_busy(
    days: int = typer.Option(7, "--days", min=1),
    calendars: CalendarScope = typer.Option(CalendarScope.selected, "--calendars"),
    raw: bool = typer.Option(False, "--raw"),
) -> None:
    """List busy intervals from configured calendars."""
    try:
        if calendars is CalendarScope.primary:
            calendar_ids = ["primary"]
        elif calendars is CalendarScope.work:
            config = load_config()
            calendar_ids = list(config.calendar.work_calendar_ids)
        else:
            available = list_calendars()
            if calendars is CalendarScope.selected:
                calendar_ids = [item["id"] for item in available if item.get("selected")]
            else:
                calendar_ids = [item["id"] for item in available]

        if not calendar_ids:
            typer.echo(
                f"No calendars found for mode '{calendars.value}'.", err=True
            )
            raise typer.Exit(code=1)

        response = fetch_freebusy_response(
            days=days, calendar_ids=calendar_ids, tz_name=DEFAULT_TIMEZONE
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        typer.echo(f"Calendar error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if raw:
        typer.echo(
            json.dumps(
                {"calendar_ids": calendar_ids, "freebusy": response},
                indent=2,
                sort_keys=True,
            )
        )
        return

    intervals = _parse_busy_intervals(
        response, calendar_ids=calendar_ids, tz_name=DEFAULT_TIMEZONE
    )
    if not intervals:
        typer.echo(f"No busy intervals found in the next {days} days.")
        return

    for interval in intervals:
        typer.echo(
            f"{interval.start:%Y-%m-%d %H:%M} -> {interval.end:%Y-%m-%d %H:%M}"
        )


def _parse_busy_intervals(
    response: dict, *, calendar_ids: list[str], tz_name: str
) -> list["BusyInterval"]:
    from planner.calendar_api import BusyInterval, _parse_rfc3339
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    calendars = response.get("calendars", {})
    intervals: list[BusyInterval] = []
    failures = 0

    for calendar_id in calendar_ids:
        calendar_data = calendars.get(calendar_id)
        if calendar_data is None:
            typer.echo(
                f"Warning: missing FreeBusy data for {calendar_id}.", err=True
            )
            failures += 1
            continue
        if calendar_data.get("errors"):
            typer.echo(
                f"Warning: FreeBusy error for {calendar_id}: {calendar_data['errors']}",
                err=True,
            )
            failures += 1
            continue

        for slot in calendar_data.get("busy", []):
            start = _parse_rfc3339(slot["start"]).astimezone(tz)
            end = _parse_rfc3339(slot["end"]).astimezone(tz)
            intervals.append(BusyInterval(start=start, end=end))

    if failures == len(calendar_ids):
        raise typer.Exit(code=1)

    intervals.sort(key=lambda item: item.start)
    return _merge_adjacent_intervals(intervals)


def _merge_adjacent_intervals(
    intervals: list["BusyInterval"],
) -> list["BusyInterval"]:
    if not intervals:
        return []

    merged = [intervals[0]]
    for interval in intervals[1:]:
        last = merged[-1]
        if last.end == interval.start:
            merged[-1] = last.__class__(start=last.start, end=interval.end)
            continue
        merged.append(interval)

    return merged


@calendar_app.command("work")
def calendar_work() -> None:
    """Print configured work calendar IDs."""
    try:
        config = load_config()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        typer.echo(f"Calendar error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    work_ids = list(config.calendar.work_calendar_ids)
    if not work_ids:
        typer.echo("No work calendars configured.", err=True)
        raise typer.Exit(code=1)

    summaries: dict[str, str] = {}
    try:
        for item in list_calendars():
            if item.get("id"):
                summaries[item["id"]] = item.get("summary", "")
    except (FileNotFoundError, RuntimeError, ValueError):
        summaries = {}

    for calendar_id in work_ids:
        summary = summaries.get(calendar_id, "")
        if summary:
            typer.echo(f"{calendar_id}  {summary}")
        else:
            typer.echo(calendar_id)


def _parse_due(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Due date must be ISO8601 with timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Due date must include a timezone offset.")
    return parsed


def _open_task_db() -> sqlite3.Connection:
    conn = connect()
    init_db(conn)
    return conn


@task_app.command("add")
def task_add(
    title: str = typer.Option(..., "--title"),
    due: str = typer.Option(..., "--due"),
    est: int = typer.Option(..., "--est"),
    priority: int = typer.Option(2, "--priority"),
) -> None:
    """Add a task."""
    try:
        due_at = _parse_due(due)
    except ValueError as exc:
        typer.echo(f"Task error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if est <= 0:
        typer.echo("Task error: Estimate must be greater than 0.", err=True)
        raise typer.Exit(code=1)

    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    conn = _open_task_db()
    try:
        conn.execute(
            """
            INSERT INTO tasks (id, title, due_at, estimate_minutes, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                title,
                due_at.isoformat(),
                est,
                priority,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    typer.echo(task_id)


@task_app.command("list")
def task_list() -> None:
    """List tasks."""
    conn = _open_task_db()
    try:
        rows = conn.execute(
            """
            SELECT id, due_at, estimate_minutes, priority, title
            FROM tasks
            ORDER BY due_at ASC, priority ASC
            """
        ).fetchall()
    finally:
        conn.close()

    for task_id, due_at, estimate_minutes, priority, title in rows:
        typer.echo(
            f"{task_id} {due_at} est={estimate_minutes} pri={priority} {title}"
        )


@task_app.command("delete")
def task_delete(task_id: str) -> None:
    """Delete a task."""
    conn = _open_task_db()
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()

    if cursor.rowcount == 0:
        typer.echo(f"Task not found: {task_id}", err=True)
        raise typer.Exit(code=1)


def main() -> None:
    # This is what the console script should call.
    app()


if __name__ == "__main__":
    main()
