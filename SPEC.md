# Planner_App — Phase 1 Specification (CLI MVP)

## 0. Purpose
Build a local-first CLI application that:
1) stores tasks locally (SQLite),
2) reads the user's Google Calendar busy times,
3) computes free time slots inside configurable working hours,
4) schedules tasks into those free slots using a deterministic greedy algorithm,
5) optionally pushes those scheduled blocks back to Google Calendar as events tagged with a planner prefix.

Phase 1 goal is an end-to-end pipeline that is reliable and testable.

---

## 1. Non-Goals (Explicit Exclusions)
Phase 1 does NOT include:
- learning/improving task duration estimates from history
- partial completion check-ins / progress tracking / rescheduling logic
- anti-procrastination buddy behaviors or notifications
- GUI (desktop/mobile/web); CLI only
- multi-user support
- multiple calendar accounts
- sophisticated optimization (no OR-Tools / CP-SAT in Phase 1)
- natural-language parsing of tasks
- recurring tasks, dependencies, or subtasks

---

## 2. Target Platform
- Runs locally on Linux (Ubuntu) and should be portable to macOS/Windows later.
- No hosted backend required.
- Storage is a single local SQLite file.

---

## 3. User Workflow (Happy Path)
1) User adds tasks via CLI:
   - title
   - due datetime (timezone-aware)
   - estimate minutes
   - priority (optional)
2) User runs planning command for a horizon (e.g. next 7 days):
   - app pulls busy intervals from Google Calendar
   - app computes free intervals inside working hours
   - app schedules tasks greedily into free intervals
   - app writes a plan (planned blocks) to SQLite and prints a readable schedule
3) User optionally pushes planned blocks to Google Calendar:
   - creates events titled with a prefix like `[PLANNER] <task title>`
   - stores Google event IDs locally to prevent duplicates and enable deletion
4) User can clear planner-created events in the horizon.

---

## 4. Interfaces (CLI Commands)
### 4.1 Tasks
- `planner task add --title "..." --due "<RFC3339>" --est <minutes> [--priority <int>]`
- `planner task list`
- `planner task delete <task_id>`

### 4.2 Calendar (Read)
- `planner calendar busy --days <N>`
  - prints busy intervals retrieved from Google Calendar primary calendar

### 4.3 Planning
- `planner plan --days <N>`
  - computes free intervals and creates planned blocks
  - prints schedule to stdout

### 4.4 Calendar (Write)
- `planner calendar push --days <N>`
  - inserts planned blocks as Google Calendar events
- `planner calendar clear --days <N>`
  - deletes only planner-created events (by stored IDs and/or `[PLANNER]` prefix)

---

## 5. Configuration
Phase 1 uses a local config file (default `planner_config.toml`) with:
- `timezone` (default: `America/New_York`)
- working hours by weekday (e.g. Mon–Fri 09:30–18:30)
- optional inclusion of weekends
- `min_block_minutes` (default 25)
- `buffer_minutes` between planned blocks (default 10)
- planning horizon default (e.g. 7 days)

Config must be validated at startup (fail fast with a clear error if invalid).

---

## 6. Data Model (SQLite)
### 6.1 Tasks table
Fields (minimum):
- `id` (string UUID)
- `title` (string)
- `due_at` (timezone-aware datetime)
- `estimate_minutes` (int)
- `priority` (int, default 2)
- `created_at` (datetime)

### 6.2 PlanBlocks table
Fields (minimum):
- `id` (string UUID)
- `task_id` (FK)
- `start_at` (timezone-aware datetime)
- `end_at` (timezone-aware datetime)
- `minutes` (int)
- `is_late` (bool) — true if scheduled block starts after task due_at or causes completion after due_at (define precisely below)
- `gcal_event_id` (nullable string) — set when pushed to Google Calendar
- `created_at` (datetime)

---

## 7. Scheduling Rules (Phase 1)
### 7.1 Inputs
- Tasks: (title, due_at, estimate_minutes, priority)
- Busy intervals from Google Calendar
- Working hours windows from config

### 7.2 Compute free intervals
For each day in horizon:
- define working window [work_start, work_end]
- subtract union of busy intervals occurring within that window
- output sorted free intervals
- discard free intervals shorter than `min_block_minutes`

### 7.3 Greedy scheduler (deterministic)
- Sort tasks by:
  1) earliest `due_at`
  2) higher `priority` first (smaller number = higher priority, or vice versa; choose and document)
  3) stable tie-breaker: task creation time or ID
- For each task in order:
  - allocate `estimate_minutes` into one or more blocks placed as early as possible in free time
  - do not create blocks shorter than `min_block_minutes`
  - insert `buffer_minutes` between adjacent planned blocks
  - if task cannot be fully scheduled before `due_at`, still schedule remaining blocks after `due_at` and mark `is_late = true`

Late definition (Phase 1):
- A plan block is late if its start time is >= task due_at.
(We may refine this in later phases to consider completion time.)

---

## 8. Google Calendar Integration (Phase 1)
### 8.1 Auth
- Uses OAuth Desktop App credentials in `secrets/credentials.json` (not committed)
- Stores token cache in `secrets/token.json` (not committed)

### 8.2 Busy times retrieval
- Use Google Calendar FreeBusy API against primary calendar.

### 8.3 Event creation
- Create an event per PlanBlock with:
  - summary: `[PLANNER] <task title>`
  - description includes task_id and plan_block_id
  - start/end set from block timestamps
- Store returned `eventId` in PlanBlocks to prevent duplicates.

### 8.4 Clearing events
- Delete only events created by this app:
  - prefer deletion by stored `gcal_event_id`
  - optionally also verify summary prefix `[PLANNER]` as a safeguard

---

## 9. Reliability Requirements
- All datetimes must be timezone-aware end-to-end.
- The planner must not delete or modify non-planner calendar events.
- If Google auth is missing/expired, commands fail with a clear actionable message.
- CLI commands return non-zero exit codes on errors.

---

## 10. Testing Requirements
Minimum test suite:
- interval subtraction: overlaps, containment, adjacency, empty cases
- greedy scheduler:
  - no overlapping plan blocks
  - blocks fit inside free intervals
  - respects min_block_minutes and buffer_minutes
  - deterministic output given same inputs
- DB CRUD for tasks and plan blocks using in-memory SQLite

---

## 11. Acceptance Criteria (Phase 1 Complete)
Phase 1 is considered complete when the following work reliably:
1) Add/list/delete tasks.
2) Pull busy intervals from Google Calendar for N days.
3) Generate a plan and store plan blocks in SQLite.
4) Push plan blocks to Google Calendar as `[PLANNER] ...` events.
5) Clear those planner-created events without affecting other events.
