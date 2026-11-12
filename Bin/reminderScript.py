#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
"""SQLite reminder backend used by rofi and Polybar.

Journal acknowledgements track individual dates. ``acknowledged_date`` remains
 the last contiguous journal date, so filling newer dates never hides older gaps.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
import argparse
import re
import sqlite3

DB_FILE = Path("/home/christian/Opt/ReminderDataBase/remindersWithTime.db")
WEEKDAY_MAP = {
    name: i for i, name in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
}
JOURNAL_EVENT_ID = 1


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on failure, and always close the connection."""
    connection = get_db_connection()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    with database() as connection:
        for statement in (
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                message TEXT NOT NULL, enabled INTEGER DEFAULT 1)""",
            """CREATE TABLE IF NOT EXISTS event_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                weekday INTEGER NOT NULL, time TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE)""",
            """CREATE TABLE IF NOT EXISTS event_state (
                event_id INTEGER PRIMARY KEY, last_triggered TEXT,
                pending INTEGER DEFAULT 0, acknowledged_date TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE)""",
            """CREATE TABLE IF NOT EXISTS event_state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                last_triggered TEXT, pending INTEGER, acknowledged_date TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE)""",
            """CREATE TABLE IF NOT EXISTS journal_entries (
                entry_date TEXT PRIMARY KEY, history_id INTEGER,
                FOREIGN KEY(history_id) REFERENCES event_state_history(id)
                ON DELETE SET NULL)""",
        ):
            connection.execute(statement)


def parse_time(value: str | None) -> time | None:
    if not value:
        return None
    for pattern in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(value, pattern).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time: {value}")


def parse_weekdays(values: Sequence[str]) -> list[int]:
    days = set()
    for value in values:
        for token in re.split(r"[\s,]+", value.strip().lower()):
            if not token:
                continue
            if token in WEEKDAY_MAP:
                days.add(WEEKDAY_MAP[token])
            elif token.isdigit() and 0 <= int(token) <= 6:
                days.add(int(token))
            else:
                raise ValueError(f"Invalid weekday: {token}")
    if not days:
        raise ValueError("At least one weekday is required")
    return sorted(days)


def add_reminder(
    name: str,
    message: str,
    weekdays: Sequence[str],
    time_str: str | None = None,
    enabled: bool = True,
) -> int:
    days = parse_weekdays(weekdays)
    reminder_time = parse_time(time_str)
    if not name.strip() or not message.strip():
        raise ValueError("Name and message must not be empty")
    with database() as connection:
        cursor = connection.execute(
            "INSERT INTO events (name, message, enabled) VALUES (?, ?, ?)",
            (name, message, int(enabled)),
        )
        event_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO event_schedule (event_id, weekday, time) VALUES (?, ?, ?)",
            [
                (
                    event_id,
                    day,
                    reminder_time.strftime("%H:%M") if reminder_time else None,
                )
                for day in days
            ],
        )
        connection.execute("INSERT INTO event_state (event_id) VALUES (?)", (event_id,))
    print("Reminder added with id", event_id)
    return event_id


def next_trigger_day(last_triggered: str, weekday: int) -> datetime:
    """Return the next matching weekday strictly after the last trigger."""
    previous = datetime.fromisoformat(last_triggered)
    return previous + timedelta(days=(weekday - previous.weekday()) % 7 or 7)


def check_reminders(verbose: bool = False) -> list[sqlite3.Row]:
    now = datetime.now()
    triggered = []
    seen = set()
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute("""
            SELECT e.id, e.name, e.message, s.weekday, s.time, st.last_triggered
            FROM events e JOIN event_schedule s ON e.id = s.event_id
            JOIN event_state st ON e.id = st.event_id WHERE e.enabled = 1
            ORDER BY e.id, s.weekday
        """).fetchall()
        for row in rows:
            # The most recent occurrence also catches reminders missed while off.
            due = now.date() - timedelta(days=(now.weekday() - row["weekday"]) % 7)
            if (
                row["time"]
                and due == now.date()
                and parse_time(row["time"]) > now.time()
            ):
                due -= timedelta(days=7)
            last = row["last_triggered"]
            if row["id"] in seen:
                continue
            if last is None:
                # New reminders start with today's schedule, not last week's.
                if due != now.date():
                    continue
            elif due <= date.fromisoformat(last):
                continue
            connection.execute(
                """
                UPDATE event_state SET pending = 1, last_triggered = ? WHERE event_id = ?
            """,
                (now.date().isoformat(), row["id"]),
            )
            seen.add(row["id"])
            triggered.append(row)
    if verbose:
        for row in triggered:
            print("Triggered:", row["name"])
    return triggered


def get_last_ack(event_id: int | str) -> datetime | None:
    with database() as connection:
        row = connection.execute(
            "SELECT acknowledged_date FROM event_state WHERE event_id = ?",
            (int(event_id),),
        ).fetchone()
    return (
        datetime.fromisoformat(row["acknowledged_date"])
        if row and row["acknowledged_date"]
        else None
    )


def get_last_journal_ack() -> datetime | None:
    return get_last_ack(JOURNAL_EVENT_ID)


def journal_dates(connection: sqlite3.Connection) -> set[date]:
    return {
        date.fromisoformat(row[0])
        for row in connection.execute("SELECT entry_date FROM journal_entries")
    }


def next_missing_date(entries: set[date], today: date | None = None) -> date:
    """Find the first gap from the journal's first date, bounded by today."""
    today = today or date.today()
    candidate = min(entries, default=today)
    while candidate in entries and candidate <= today:
        candidate += timedelta(days=1)
    return min(candidate, today)


def _update_journal_state(connection: sqlite3.Connection) -> None:
    entries = journal_dates(connection)
    if not entries:
        return
    today = date.today()
    missing = next_missing_date(entries, today)
    frontier = (
        today if today in entries and missing == today else missing - timedelta(days=1)
    )
    # Today's journal is due in the evening; older gaps stay pending all day.
    pending = missing < today or (
        missing == today and today not in entries and datetime.now().hour >= 18
    )
    connection.execute(
        """UPDATE event_state SET acknowledged_date = ?, pending = ?
                          WHERE event_id = ?""",
        (frontier.isoformat(), int(pending), JOURNAL_EVENT_ID),
    )


def sync_journal_dates(entries: set[date]) -> None:
    """Import existing journal headers without discarding acknowledgement history."""
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT OR IGNORE INTO journal_entries (entry_date) VALUES (?)",
            [(day.isoformat(),) for day in sorted(entries)],
        )
        _update_journal_state(connection)


def count_sunwednesdays(last_date: datetime) -> int:
    days = (date.today() - last_date.date()).days
    return sum(
        (last_date.date() + timedelta(days=offset)).weekday() in (2, 6)
        for offset in range(days + 1)
    )


def get_day_diff(last_ack_date: datetime | None, event_id: int | str) -> str:
    if int(event_id) == JOURNAL_EVENT_ID:
        with database() as connection:
            entries = journal_dates(connection)
        if entries:
            # Count completed days after the newest entry; today's entry is
            # still due today, and historical gaps do not affect this badge.
            missing = max(0, (date.today() - max(entries)).days - 1)
            return f" ({missing})" if missing else ""
    if last_ack_date is None:
        return ""
    days = (date.today() - last_ack_date.date()).days
    if days < 2:
        return ""
    count = (
        days - 1
        if int(event_id) == 1
        else count_sunwednesdays(last_ack_date)
        if int(event_id) == 3
        else days
    )
    return f" ({count})"


def get_display_string(row: sqlite3.Row, polybar_format: bool) -> str | None:
    last_ack = get_last_ack(row["id"])
    if row["id"] == JOURNAL_EVENT_ID and last_ack is not None:
        if datetime.now().hour < 18 and (date.today() - last_ack.date()).days <= 1:
            return None
    return (
        f"{row['message']}{get_day_diff(last_ack, row['id'])}"
        if polybar_format
        else f"{row['id']} {row['message']}"
    )


def query_pending(polybar_format: bool = False) -> None:
    with database() as connection:
        rows = connection.execute("""
            SELECT e.id, e.name, e.message FROM events e
            JOIN event_state s ON e.id = s.event_id
            WHERE s.pending = 1 AND e.enabled = 1 ORDER BY e.id
        """).fetchall()
    print(
        ", ".join(
            message
            for row in rows
            if (message := get_display_string(row, polybar_format)) is not None
        )
    )


def acknowledge_journal(entry_date: date | None = None) -> None:
    acknowledge(JOURNAL_EVENT_ID, entry_date)


def acknowledge(reminder_id: int, entry_date: date | None = None) -> None:
    """Save state and the selected journal date in a single transaction."""
    reminder_id = int(reminder_id)
    if entry_date and reminder_id != JOURNAL_EVENT_ID:
        raise ValueError("--date is only supported for the journal")
    if entry_date and entry_date > date.today():
        raise ValueError("Cannot acknowledge a future journal date")
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        state = connection.execute(
            "SELECT * FROM event_state WHERE event_id = ?", (reminder_id,)
        ).fetchone()
        if state is None:
            raise ValueError(f"No event found: {reminder_id}")
        history = connection.execute(
            """
            INSERT INTO event_state_history (event_id, last_triggered, pending, acknowledged_date)
            VALUES (?, ?, ?, ?)
        """,
            (
                reminder_id,
                state["last_triggered"],
                state["pending"],
                state["acknowledged_date"],
            ),
        )
        acknowledged_date, pending = date.today(), 0
        if reminder_id == JOURNAL_EVENT_ID:
            entries = journal_dates(connection)
            if entries or entry_date:
                selected = entry_date or next_missing_date(entries)
                connection.execute(
                    "INSERT OR IGNORE INTO journal_entries (entry_date, history_id) VALUES (?, ?)",
                    (selected.isoformat(), history.lastrowid),
                )
                _update_journal_state(connection)
                print("Acknowledged", reminder_id, selected.isoformat())
                return
            previous = state["acknowledged_date"]
            acknowledged_date = (
                min(date.fromisoformat(previous) + timedelta(days=1), date.today())
                if previous
                else date.today()
            )
            pending = state["pending"] if acknowledged_date < date.today() else 0
        connection.execute(
            "UPDATE event_state SET pending = ?, acknowledged_date = ? WHERE event_id = ?",
            (pending, acknowledged_date.isoformat(), reminder_id),
        )
    print("Acknowledged", reminder_id)


def reset_reminder(reminder_id: int) -> None:
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            """
            SELECT h.* FROM event_state_history h JOIN events e ON e.id = h.event_id
            JOIN event_state s ON s.event_id = h.event_id
            WHERE h.event_id = ? ORDER BY h.id DESC LIMIT 1
        """,
            (reminder_id,),
        ).fetchone()
        if previous is None:
            print("No saved state to reset for event", reminder_id)
            return
        connection.execute(
            """UPDATE event_state SET last_triggered = ?, pending = ?, acknowledged_date = ?
                              WHERE event_id = ?""",
            (
                previous["last_triggered"],
                previous["pending"],
                previous["acknowledged_date"],
                reminder_id,
            ),
        )
        connection.execute(
            "DELETE FROM journal_entries WHERE history_id = ?", (previous["id"],)
        )
        connection.execute(
            "DELETE FROM event_state_history WHERE id = ?", (previous["id"],)
        )
    print("Reset event", reminder_id, "to its previous state")


def delete_reminder(reminder_id: int) -> None:
    with database() as connection:
        connection.execute("DELETE FROM events WHERE id = ?", (reminder_id,))
    print("Deleted", reminder_id)


def list_reminders() -> None:
    with database() as connection:
        rows = connection.execute("""SELECT e.id, e.name, s.weekday, s.time FROM events e
                                     JOIN event_schedule s ON e.id = s.event_id ORDER BY e.id, s.weekday""").fetchall()
    for row in rows:
        print(row["id"], row["name"], row["weekday"], row["time"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Create a reminder")
    add.add_argument("--name", required=True)
    add.add_argument("--message", required=True)
    add.add_argument("--weekdays", nargs="+", required=True)
    add.add_argument("--time")
    commands.add_parser("check")
    query = commands.add_parser("query")
    query.add_argument("--polybar", action="store_true")
    ack = commands.add_parser("ack")
    ack.add_argument("id", type=int)
    ack.add_argument(
        "--date", type=date.fromisoformat, help="Journal date (YYYY-MM-DD)"
    )
    for command in ("reset", "delete"):
        commands.add_parser(command).add_argument("id", type=int)
    commands.add_parser("list")
    args = parser.parse_args()
    try:
        init_db()
        if args.command == "add":
            add_reminder(args.name, args.message, args.weekdays, args.time)
        elif args.command == "check":
            check_reminders(verbose=True)
        elif args.command == "query":
            query_pending(args.polybar)
        elif args.command == "ack":
            acknowledge(args.id, args.date)
        elif args.command == "reset":
            reset_reminder(args.id)
        elif args.command == "delete":
            delete_reminder(args.id)
        elif args.command == "list":
            list_reminders()
    except (ValueError, sqlite3.Error) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
