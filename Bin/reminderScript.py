#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import argparse
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

DB_FILE = Path("/home/christian/Opt/ReminderDataBase/remindersWithTime.db")

WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        message TEXT NOT NULL,
        enabled INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS event_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        weekday INTEGER NOT NULL,
        time TEXT,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS event_state (
        event_id INTEGER PRIMARY KEY,
        last_triggered TEXT,
        pending INTEGER DEFAULT 0,
        acknowledged_date TEXT,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS event_state_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        last_triggered TEXT,
        pending INTEGER,
        acknowledged_date TEXT,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()


def parse_time(time_str):
    if not time_str:
        return None

    formats = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            pass

    return None


def add_reminder(name, message, weekdays, time_str=None, enabled=True):
    conn = get_db_connection()
    cur = conn.cursor()
    reminder_time = parse_time(time_str) if time_str else None
    weekday_indices = []
    weekdays = weekdays[0].replace(",", "").split()
    for d in weekdays:
        d = d.lower()
        if d in WEEKDAY_MAP:
            weekday_indices.append(WEEKDAY_MAP[d])
        else:
            try:
                val = int(d)
                if 0 <= val <= 6:
                    weekday_indices.append(val)
            except ValueError:
                print("Invalid weekday:", d)
                return

    cur.execute(
        "INSERT INTO events (name, message, enabled) VALUES (?, ?, ?)",
        (name, message, int(enabled)),
    )
    event_id = cur.lastrowid
    for wd in weekday_indices:
        cur.execute(
            "INSERT INTO event_schedule (event_id, weekday, time) VALUES (?, ?, ?)",
            (event_id, wd, reminder_time.strftime("%H:%M") if reminder_time else None),
        )
    cur.execute("INSERT INTO event_state (event_id) VALUES (?)", (event_id,))
    conn.commit()
    conn.close()
    print("Reminder added with id", event_id)


def next_trigger_day(last_triggered, weekday) -> datetime:
    next_trigger_day = datetime.fromisoformat(last_triggered)
    while next_trigger_day.weekday() != weekday:
        next_trigger_day = next_trigger_day + timedelta(days=1)
    return next_trigger_day


def check_reminders(verbose=False):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT e.id, e.name, e.message, s.weekday, s.time, st.last_triggered
    FROM events e
    JOIN event_schedule s ON e.id = s.event_id
    LEFT JOIN event_state st ON e.id = st.event_id
    WHERE e.enabled = 1
    """)

    rows = cur.fetchall()
    today_date = date.today()
    now = datetime.now().strftime("%H:%M")
    today_str = today_date.isoformat()
    triggered = []

    for r in rows:
        next_trigger = next_trigger_day(r["last_triggered"], r["weekday"])
        if isinstance(next_trigger, str):
            next_trigger_date = date.fromisoformat(next_trigger)
        elif isinstance(next_trigger, datetime):
            next_trigger_date = next_trigger.date()
        else:
            next_trigger_date = next_trigger

        if today_date < next_trigger_date:
            continue

        if today_date == next_trigger_date and r["time"] and r["time"] > now:
            continue

        if r["last_triggered"] == today_str:
            continue

        cur.execute(
            "UPDATE event_state SET pending = 1, last_triggered = ? WHERE event_id = ?",
            (today_str, r["id"]),
        )

        triggered.append(r)

        if verbose:
            print("Triggered:", r["name"])

    conn.commit()
    conn.close()
    return triggered


def query_pending(polybar_format=False):
    conn = get_db_connection()
    cur = conn.cursor()

    query_string_with_time_check = """
    WITH event_schedules AS (
        SELECT id
        FROM event_schedule
        GROUP BY id, weekday
    ),
    aggregated_events AS (
        SELECT e.id, e.name, e.message, MAX(CASE WHEN sched.time IS NULL OR TIME(sched.time) > TIME('now') THEN sched.time END) AS schedule_time
        FROM events e
        JOIN event_state state ON e.id = state.event_id AND state.pending = 1
        LEFT JOIN (
            SELECT es.event_id, es.time
            FROM event_schedule es
            WHERE (es.time IS NULL OR TIME(es.time) > TIME('now'))
        )
        sched ON e.id = sched.event_id
        GROUP BY e.id, e.name, e.message
    )
    SELECT id, name, message, schedule_time
    FROM aggregated_events as ae
    """
    # WHERE ae.schedule_time IS NULL OR TIME('now') > TIME(ae.schedule_time);

    cur.execute(query_string_with_time_check)
    rows = cur.fetchall()
    conn.close()
    messages = []
    for r in rows:
        event_string = get_display_string(r, polybar_format)
        if event_string is not None:
            messages.append(event_string)
        # last_ack_date = get_last_ack(str(r["id"]))
        # dayDiffStr = get_day_diff(last_ack_date, str(r["id"]))
        # if str(r["id"]) == "1":
        #     delta = datetime.today().date() - get_last_journal_ack().date()
        #     if datetime.now().strftime("%H") < "18" and delta.days == 1:
        #         continue
        # if polybar_format:
        #     messages.append(f"{r['id']} {r['message']}")
        # else:
        #     messages.append(f"{r['message']}{dayDiffStr}")
    print(", ".join(messages))


def get_display_string(r, polybar_format):
    last_ack_date = get_last_ack(str(r["id"]))
    dayDiffStr = get_day_diff(last_ack_date, str(r["id"]))
    if str(r["id"]) == "1":
        delta = datetime.today().date() - get_last_journal_ack().date()
        if datetime.now().strftime("%H") < "18" and delta.days == 1:
            return None
    if polybar_format:
        return f"{r['message']}{dayDiffStr}"
        # return f"{r['id']} {r['message']}{dayDiffStr}"
    return f"{r['id']} {r['message']}"


def count_sunwednesdays(last_date):
    today = datetime.today()
    event_count = 0
    current = last_date
    while current <= today:
        if current.weekday() == 6 or current.weekday() == 2:
            event_count += 1
        current += timedelta(days=1)
    return event_count


def get_day_diff(last_ack_date, event_id):
    dayDiff = (datetime.today() - last_ack_date).days
    if dayDiff < 2:
        return ""
    if event_id == "1":
        return " (" + str(dayDiff - 1) + ")"
    if event_id == "3":
        return " (" + str(count_sunwednesdays(last_ack_date)) + ")"
    return " (" + str(dayDiff) + ")"


def get_last_ack(event_id):
    conn = get_db_connection()
    cur = conn.cursor()
    last_acked = cur.execute(
        "SELECT acknowledged_date FROM event_state WHERE event_id = ?", event_id
    )
    last_acked_string = last_acked.fetchone()[0]
    return datetime.strptime(last_acked_string, "%Y-%m-%d")


def get_last_journal_ack():
    conn = get_db_connection()
    cur = conn.cursor()
    last_acked = cur.execute(
        "SELECT acknowledged_date FROM event_state WHERE event_id = 1"
    )
    last_acked_string = last_acked.fetchone()[0]
    return datetime.strptime(last_acked_string, "%Y-%m-%d")


def acknowledge_journal():
    acknowledge(1)


def acknowledge(reminder_id):
    """Save the previous state and acknowledge atomically, allowing an undo."""
    reminder_id = int(reminder_id)
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            state = conn.execute(
                "SELECT * FROM event_state WHERE event_id = ?", (reminder_id,)
            ).fetchone()
            if state is None:
                print("No event found:", reminder_id)
                return

            conn.execute(
                """INSERT INTO event_state_history
                   (event_id, last_triggered, pending, acknowledged_date)
                   VALUES (?, ?, ?, ?)""",
                (reminder_id, state["last_triggered"], state["pending"],
                 state["acknowledged_date"]),
            )
            acknowledged_date = date.today()
            pending = 0
            if reminder_id == 1:
                acknowledged_date = (
                    date.fromisoformat(state["acknowledged_date"]) + timedelta(days=1)
                )
                if acknowledged_date < date.today():
                    pending = state["pending"]

            conn.execute(
                """UPDATE event_state SET pending = ?, acknowledged_date = ?
                   WHERE event_id = ?""",
                (pending, acknowledged_date.isoformat(), reminder_id),
            )
    finally:
        conn.close()
    print("Acknowledged", reminder_id)


def reset_reminder(reminder_id):
    """Restore and consume the most recent saved state for an existing event."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                """SELECT history.* FROM event_state_history AS history
                   JOIN events ON events.id = history.event_id
                   JOIN event_state ON event_state.event_id = history.event_id
                   WHERE history.event_id = ? ORDER BY history.id DESC LIMIT 1""",
                (reminder_id,),
            ).fetchone()
            if previous is None:
                print("No saved state to reset for event", reminder_id)
                return

            conn.execute(
                """UPDATE event_state
                   SET last_triggered = ?, pending = ?, acknowledged_date = ?
                   WHERE event_id = ?""",
                (previous["last_triggered"], previous["pending"],
                 previous["acknowledged_date"], reminder_id),
            )
            conn.execute(
                "DELETE FROM event_state_history WHERE id = ?", (previous["id"],)
            )
    finally:
        conn.close()
    print("Reset event", reminder_id, "to its previous state")


def delete_reminder(reminder_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM events WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()
    print("Deleted", reminder_id)


def list_reminders():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT e.id, e.name, e.message, s.weekday, s.time
    FROM events e
    JOIN event_schedule s ON e.id = s.event_id
    ORDER BY e.id
    """)
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        print(r["id"], r["name"], r["weekday"], r["time"])


def main():

    init_db()

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--message", required=True)
    p_add.add_argument("--weekdays", nargs="+", required=True)
    p_add.add_argument("--time")

    sub.add_parser("check")
    p_query = sub.add_parser("query")
    p_query.add_argument(
        "--polybar", action="store_true", help="Enable polybar output mode"
    )

    p_ack = sub.add_parser("ack")
    p_ack.add_argument("id", type=int)

    p_reset = sub.add_parser("reset", help="Undo an event's last acknowledgement")
    p_reset.add_argument("id", type=int)

    p_del = sub.add_parser("delete")
    p_del.add_argument("id", type=int)

    sub.add_parser("list")

    args = parser.parse_args()

    if args.cmd == "add":
        add_reminder(args.name, args.message, args.weekdays, args.time)

    elif args.cmd == "check":
        check_reminders(True)

    elif args.cmd == "query":
        if args.polybar:
            query_pending(args.polybar)
        else:
            query_pending()

    elif args.cmd == "ack":
        acknowledge(args.id)

    elif args.cmd == "reset":
        reset_reminder(args.id)

    elif args.cmd == "delete":
        delete_reminder(args.id)

    elif args.cmd == "list":
        list_reminders()


if __name__ == "__main__":
    main()
