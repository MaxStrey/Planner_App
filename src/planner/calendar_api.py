from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/New_York"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_PATH = Path("secrets/credentials.json")
TOKEN_PATH = Path("secrets/token.json")


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _ensure_credentials_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing OAuth client secrets at {path}. "
            "Run Google API setup and save credentials.json."
        )


def _get_credentials() -> "Credentials":
    _ensure_credentials_file(CREDENTIALS_PATH)

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _build_service():
    from googleapiclient.discovery import build

    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def fetch_freebusy_response(
    days: int, calendar_ids: Iterable[str], tz_name: str = DEFAULT_TIMEZONE
) -> dict:
    calendar_ids = list(calendar_ids)
    if not calendar_ids:
        raise ValueError("No calendar IDs provided for FreeBusy query.")
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    time_min = now.replace(microsecond=0).isoformat()
    time_max = (now + timedelta(days=days)).replace(microsecond=0).isoformat()

    service = _build_service()
    return (
        service.freebusy()
        .query(
            body={
                "timeMin": time_min,
                "timeMax": time_max,
                "timeZone": tz_name,
                "items": [{"id": calendar_id} for calendar_id in calendar_ids],
            }
        )
        .execute()
    )


def fetch_busy_intervals(
    days: int, calendar_ids: Iterable[str], tz_name: str = DEFAULT_TIMEZONE
) -> Iterable[BusyInterval]:
    tz = ZoneInfo(tz_name)
    response = fetch_freebusy_response(days=days, calendar_ids=calendar_ids, tz_name=tz_name)

    calendars = response.get("calendars", {})
    intervals = []
    for calendar_id in calendar_ids:
        calendar_data = calendars.get(calendar_id)
        if calendar_data is None:
            raise RuntimeError(f"FreeBusy response missing calendar data for {calendar_id}.")
        if calendar_data.get("errors"):
            raise RuntimeError(
                f"FreeBusy error for {calendar_id}: {calendar_data['errors']}"
            )

        for slot in calendar_data.get("busy", []):
            start = _parse_rfc3339(slot["start"]).astimezone(tz)
            end = _parse_rfc3339(slot["end"]).astimezone(tz)
            intervals.append(BusyInterval(start=start, end=end))

    intervals.sort(key=lambda item: item.start)
    return intervals


def list_calendars() -> list[dict]:
    service = _build_service()
    calendars = []
    page_token = None

    while True:
        response = (
            service.calendarList()
            .list(pageToken=page_token)
            .execute()
        )
        for item in response.get("items", []):
            calendars.append(
                {
                    "id": item.get("id", ""),
                    "summary": item.get("summary", ""),
                    "selected": bool(item.get("selected", False)),
                    "primary": bool(item.get("primary", False)),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return calendars
