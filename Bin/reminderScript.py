#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import argparse
import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_FILE = Path("/home/christian/Opt/ReminderDataBase/reminders.db")

WEEKDAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6
}


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
        (name, message, int(enabled))
    )

    event_id = cur.lastrowid

    for wd in weekday_indices:
        cur.execute(
            "INSERT INTO event_schedule (event_id, weekday, time) VALUES (?, ?, ?)",
            (event_id, wd, reminder_time.strftime("%H:%M") if reminder_time else None)
        )

    cur.execute("INSERT INTO event_state (event_id) VALUES (?)", (event_id,))

    conn.commit()
    conn.close()

    print("Reminder added with id", event_id)


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

    today = date.today().weekday()
    now = datetime.now().strftime("%H:%M")
    today_str = date.today().isoformat()

    triggered = []

    for r in rows:

        if r["weekday"] != today:
            continue

        if r["time"] and r["time"] > now:
            continue

        if r["last_triggered"] == today_str:
            continue

        cur.execute(
            "UPDATE event_state SET pending = 1, last_triggered = ? WHERE event_id = ?",
            (today_str, r["id"])
        )

        triggered.append(r)

        if verbose:
            print("Triggered:", r["name"])

    conn.commit()
    conn.close()

    return triggered


def query_pending(polybar_format= False):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT e.id, e.name, e.message
    FROM events e
    JOIN event_state st ON e.id = st.event_id
    WHERE st.pending = 1 AND e.enabled = 1
    """)

    rows = cur.fetchall()
    conn.close()
    messages = []
    for r in rows:
        if(polybar_format):
            messages.append(f"{r['id']} {r['message']}")
        else:
            messages.append(f"{r['message']}")
    print(', '.join(messages))


def acknowledge(reminder_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE event_state SET pending = 0, acknowledged_date = ? WHERE event_id = ?",
        (date.today().isoformat(), reminder_id)
    )

    conn.commit()
    conn.close()

    print("Acknowledged", reminder_id)


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
        print(r['id'], r['name'], r['weekday'], r['time'])


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
    p_query.add_argument("--polybar", action="store_true", help="Enable polybar output mode")

    p_ack = sub.add_parser("ack")
    p_ack.add_argument("id", type=int)

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

    elif args.cmd == "delete":
        delete_reminder(args.id)

    elif args.cmd == "list":
        list_reminders()


if __name__ == "__main__":
    main()

