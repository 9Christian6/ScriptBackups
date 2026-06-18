#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import argparse
import sqlite3
import pandas
from datetime import datetime, date, timedelta
from pathlib import Path

DB_FILE = Path("/home/christian/Opt/ReminderDataBase/remindersWithTime.db")

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

    query_string_all_events="""
        select * 
        from event_schedule 
        join event_state using(event_id)
        join events on event_schedule.event_id=events.id
    """
    cur.execute(query_string_all_events)
    rows = cur.fetchall()
    should_be_printed = []
    for r in rows:
        if r['enabled'] != 1:
            continue
        if r['pending'] != 1:
            continue
        last_triggered = datetime.strptime(r['last_triggered'], "%Y-%m-%d")
        stale_since = datetime.today() - last_triggered
        if stale_since > timedelta(days=2):
            should_be_printed.append(r)
            continue
        if r['weekday'] != datetime.today().weekday():
            continue
        if r['time'] is not None:
            trigger_time = datetime.strptime(r['time'], "%H:%M").time()
            current_time = datetime.now().time()
            if trigger_time > current_time:
                continue
        should_be_printed.append(r)
    conn.close()
    messages = []
    for r in should_be_printed:
        if(polybar_format):
            messages.append(f"{r['id']} {r['message']}")
        else:
            messages.append(f"{r['message']}")
    print(', '.join(messages))


def acknowledge_journal():
    conn = get_db_connection()
    cur = conn.cursor()
    last_acked = cur.execute("SELECT acknowledged_date FROM event_state WHERE event_id = 1")
    last_acked_string = last_acked.fetchone()[0]
    next_ack_date = (datetime.strptime(last_acked_string, "%Y-%m-%d") + timedelta(days=1)).date()
    cur.execute( "UPDATE event_state SET acknowledged_date = ? WHERE event_id = ?", (next_ack_date.isoformat(), '1'))
    if (next_ack_date >= datetime.today().date()):
        cur.execute( "UPDATE event_state SET pending = 0 WHERE event_id = ?", ('1'))

    conn.commit()
    conn.close()


def acknowledge(reminder_id):
    if reminder_id == 1:
        acknowledge_journal()
        return
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

def infer_type(value):
    """
    Attempts to parse a value into the most fitting Python type.
    """
    # If it's already a native non-string type (or None), return it as is
    if value is None or isinstance(value, (int, float, bool, bytes)):
        return value
    
    # If it's a string, attempt to infer a more specific type
    if isinstance(value, str):
        val_stripped = value.strip()
        
        # Check for boolean or null representations
        if val_stripped.lower() in ('true', 'false'):
            return val_stripped.lower() == 'true'
        if val_stripped.lower() in ('none', 'null', ''):
            return None
            
        # Try parsing as integer
        try:
            return int(val_stripped)
        except ValueError:
            pass
            
        # Try parsing as float
        try:
            return float(val_stripped)
        except ValueError:
            pass
            
    # Fallback to original string if no other type fits
    return value

def execute_and_print_query(query: str):
    """
    Executes a SQL query, parses the results into fitting Python types, 
    and prints all values.
    """
    try:
        # Connect to the database (use ':memory:' for testing without a file)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Execute the query
            cursor.execute(query)
            
            # Check if the query returns rows (e.g., SELECT statements)
            if cursor.description is None:
                print(f"Query executed successfully. Rows affected: {cursor.rowcount}")
                return
            
            # Fetch all rows and get column names
            rows = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
            
            if not rows:
                print("Query executed successfully, but no rows were returned.")
                return
            
            print(f"--- Found {len(rows)} row(s) ---")
            
            # Process and print each row
            for row_idx, row in enumerate(rows, start=1):
                print(f"\n[Row {row_idx}]")
                parsed_row = {}
                for col_idx, raw_value in enumerate(row):
                    col_name = column_names[col_idx]
                    
                    # Parse into fitting type
                    parsed_value = infer_type(raw_value)
                    parsed_row[col_name] = parsed_value
                    
                    # Print the variable name, value, and its inferred type
                    type_name = type(parsed_value).__name__
                    print(f"  {col_name:<15} = {str(parsed_value):<15} (type: {type_name})")
                    
            return parsed_row # Returns the last row as a dictionary, optional

    except sqlite3.Error as e:
        print(f"SQLite error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


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
