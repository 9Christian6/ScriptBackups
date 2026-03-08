#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
from pprint import pprint
import os
import argparse
import sqlite3
import json
import sys
import re
from datetime import datetime, date, time
from pathlib import Path

# Configuration
DB_FILE = Path("/home/christian/Bin/reminders.db")

# Weekday mapping (0 = Monday, 6 = Sunday)
WEEKDAY_MAP = {
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, 
        "fri": 4, "sat": 5, "sun": 6
        }

def get_db_connection():
    """Connect to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL, 
            config TEXT NOT NULL,
            last_triggered TEXT,
            enabled INTEGER DEFAULT 1,
            pending INTEGER DEFAULT 0,
            acknowledged_date TEXT
        )
    ''')

    # Add new columns if they don't exist (for existing databases)
    for column, default in [
            ('enabled', 1),
            ('pending', 0),
            ('acknowledged_date', None)
            ]:
        try:
            if default is None:
                cursor.execute(f'ALTER TABLE reminders ADD COLUMN {column} TEXT')
            else:
                cursor.execute(f'ALTER TABLE reminders ADD COLUMN {column} INTEGER DEFAULT {default}')
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

def reset_database(confirm=False):
    """Reset the database by deleting and recreating it."""
    if not confirm:
        print("⚠️  WARNING: This will delete ALL reminders and reset IDs to start from 1.")
        print("   Use --confirm flag to proceed.")
        return False

    try:
        # Delete the database file
        if DB_FILE.exists():
            DB_FILE.unlink()
            print(f"✓ Database file '{DB_FILE}' deleted.")

        # Recreate fresh database
        init_db()
        print(f"✓ Fresh database created.")
        print("✓ All reminders cleared. IDs will start from 1.")
        return True
    except Exception as e:
        print(f"✗ Error resetting database: {e}")
        return False

def parse_time(time_str):
    """Parse time string in various formats."""
    if not time_str:
        return None

    time_str = time_str.strip().lower()

    formats = [
            "%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I:%M:%S %p",
            ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(time_str, fmt)
            return parsed.time()
        except ValueError:
            continue

    return None

def add_reminder(name, message, interval=None, weekdays=None, time_str=None, enabled=True):
    """Add a new reminder to the database."""
    if not interval and not weekdays:
        print("Error: You must specify either --interval or --weekdays.")
        return False

    if interval and weekdays:
        print("Error: Please choose either --interval OR --weekdays, not both.")
        return False

    reminder_time = None
    if time_str:
        reminder_time = parse_time(time_str)
        if not reminder_time:
            print(f"Error: Invalid time format '{time_str}'. Use HH:MM (24h) or HH:MM AM/PM (12h).")
            return False

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if interval:
            r_type = 'interval'
            config = {"days": int(interval)}
        else:
            r_type = 'weekday'
            day_indices = []
            for d in weekdays:
                d_lower = d.lower()
                if d_lower in WEEKDAY_MAP:
                    day_indices.append(WEEKDAY_MAP[d_lower])
                else:
                    try:
                        val = int(d)
                        if 0 <= val <= 6:
                            day_indices.append(val)
                        else:
                            raise ValueError
                    except ValueError:
                        print(f"Error: Invalid weekday '{d}'. Use 0-6 or mon-sun.")
                        return False
            config = {"days": day_indices}

        if reminder_time:
            config["time"] = reminder_time.strftime("%H:%M")

        config_json = json.dumps(config)

        cursor.execute('''
            INSERT INTO reminders (name, message, type, config, last_triggered, enabled, pending, acknowledged_date)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
        ''', (name, message, r_type, config_json, None, 1 if enabled else 0))

        conn.commit()
        time_info = f" at {reminder_time.strftime('%H:%M')}" if reminder_time else ""
        status_info = " (enabled)" if enabled else " (disabled)"
        print(f"Reminder '{name}' added successfully{time_info}{status_info}.")
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def edit_reminder(reminder_id, name=None, message=None, interval=None, weekdays=None, 
                  time_str=None, enable=None, disable=None):
    """Edit an existing reminder by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch existing reminder
    cursor.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
    row = cursor.fetchone()

    if not row:
        print(f"✗ No reminder found with ID {reminder_id}.")
        conn.close()
        return False

    # Get current values
    current_name = row['name']
    current_message = row['message']
    current_type = row['type']
    current_config = json.loads(row['config'])
    current_enabled = row['enabled']

    # Update fields if provided
    new_name = name if name is not None else current_name
    new_message = message if message is not None else current_message

    # Handle enabled/disabled
    if enable:
        new_enabled = 1
    elif disable:
        new_enabled = 0
    else:
        new_enabled = current_enabled

    # Handle type and config changes
    new_type = current_type
    new_config = current_config.copy()
    config_changed = False

    # If interval or weekdays provided, update type and config
    if interval is not None:
        new_type = 'interval'
        new_config = {"days": int(interval)}
        config_changed = True
        # Preserve time if it exists
        if "time" in current_config:
            new_config["time"] = current_config["time"]
    elif weekdays is not None:
        new_type = 'weekday'
        day_indices = []
        for d in weekdays:
            d_lower = d.lower()
            if d_lower in WEEKDAY_MAP:
                day_indices.append(WEEKDAY_MAP[d_lower])
            else:
                try:
                    val = int(d)
                    if 0 <= val <= 6:
                        day_indices.append(val)
                    else:
                        raise ValueError
                except ValueError:
                    print(f"Error: Invalid weekday '{d}'. Use 0-6 or mon-sun.")
                    conn.close()
                    return False
        new_config = {"days": day_indices}
        config_changed = True
        # Preserve time if it exists
        if "time" in current_config:
            new_config["time"] = current_config["time"]

    # Handle time update
    if time_str is not None:
        if time_str == "":
            # Remove time if empty string provided
            if "time" in new_config:
                del new_config["time"]
                config_changed = True
        else:
            reminder_time = parse_time(time_str)
            if not reminder_time:
                print(f"Error: Invalid time format '{time_str}'. Use HH:MM (24h) or HH:MM AM/PM (12h).")
                conn.close()
                return False
            new_config["time"] = reminder_time.strftime("%H:%M")
            config_changed = True

    # Build update query
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(new_name)

    if message is not None:
        updates.append("message = ?")
        params.append(new_message)

    if interval is not None or weekdays is not None or time_str is not None:
        updates.append("type = ?")
        params.append(new_type)
        updates.append("config = ?")
        params.append(json.dumps(new_config))

    if enable or disable:
        updates.append("enabled = ?")
        params.append(new_enabled)

    if not updates:
        print("No changes specified. Use --name, --message, --interval, --weekdays, --time, --enable, or --disable.")
        conn.close()
        return False

    # Add ID to params
    params.append(reminder_id)

    query = f"UPDATE reminders SET {', '.join(updates)} WHERE id = ?"

    try:
        cursor.execute(query, params)
        conn.commit()

        if cursor.rowcount > 0:
            print(f"✓ Reminder ID {reminder_id} updated successfully.")
            print(f"  Name: {current_name} → {new_name}")
            print(f"  Message: {current_message} → {new_message}")
            if interval is not None or weekdays is not None:
                print(f"  Type: {current_type} → {new_type}")
                print(f"  Config: {json.dumps(current_config)} → {json.dumps(new_config)}")
            if enable or disable:
                print(f"  Enabled: {current_enabled} → {new_enabled}")
            return True
        else:
            print(f"✗ No changes made to reminder ID {reminder_id}.")
            return False
    except Exception as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def check_reminders(verbose=False, filter_id=None, filter_name=None):
    """Check all reminders and mark as pending if criteria are met."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build query with filters
    query = "SELECT * FROM reminders WHERE enabled = 1"
    params = []

    if filter_id:
        query += " AND id = ?"
        params.append(filter_id)

    if filter_name:
        query += " AND name LIKE ?"
        params.append(f"%{filter_name}%")

    cursor.execute(query, params)
    rows = cursor.fetchall()

    today = date.today()
    today_str = today.isoformat()
    now = datetime.now()
    current_time = now.time()
    marked_pending = 0

    for row in rows:
        r_id = row['id']
        name = row['name']
        r_type = row['type']
        config = json.loads(row['config'])
        last_triggered_str = row['last_triggered']
        pending = row['pending']
        acknowledged_date = row['acknowledged_date']

        # Skip if already pending and not acknowledged for today
        if pending == 1:
            if acknowledged_date == today_str:
                print('Skipping due to acknowledgment today')
                continue  # Already acknowledged today
            # else:
            #     # Reset pending for new day
            #     cursor.execute('UPDATE reminders SET pending = 0, acknowledged_date = NULL WHERE id = ?', (r_id,))

        # Check time requirement if specified
        if "time" in config:
            reminder_time = datetime.strptime(config["time"], "%H:%M").time()
            time_match = (
                    current_time.hour == reminder_time.hour and 
                    current_time.minute == reminder_time.minute
                    )
            if not time_match:
                continue  # Skip if time doesn't match

        should_trigger = False

        last_triggered = None
        if last_triggered_str:
            last_triggered = date.fromisoformat(last_triggered_str)

        if r_type == 'interval':
            interval_days = config['days']
            if last_triggered is None:
                should_trigger = True
            else:
                delta = today - last_triggered
                if delta.days >= interval_days:
                    should_trigger = True

        elif r_type == 'weekday':
            allowed_weekdays = config['days']
            if today.weekday() in allowed_weekdays:
                if last_triggered_str != today_str:
                    should_trigger = True
                if last_triggered_str is None:
                    should_trigger = True

        if should_trigger:
            # Mark as pending (waiting for acknowledgment)
            cursor.execute('''
                UPDATE reminders SET pending = 1, last_triggered = ? WHERE id = ?
            ''', (today_str, r_id))
            marked_pending += 1

            if verbose:
                print(f"✓ Reminder '{name}' is now pending acknowledgment")

    conn.commit()
    conn.close()

    if verbose:
        if marked_pending == 0:
            print("No new reminders due at this time.")
        else:
            print(f"{marked_pending} reminder(s) marked as pending.")

    return marked_pending

def query_pending(format_type='text', filter_id=None, filter_name=None, show_all=False):
    """Query pending reminders for polybar display."""
    conn = get_db_connection()
    cursor = conn.cursor()
    check_reminders(filter_id=filter_id, filter_name=filter_name)

    # Build query with filters
    if show_all:
        query = "SELECT id, name, message, type, config, last_triggered, enabled, pending FROM reminders WHERE 1=1"
    else:
        query = "SELECT id, name, message, type, config, last_triggered, enabled, pending FROM reminders WHERE enabled = 1 AND pending = 1 AND acknowledged_date IS NULL"

    params = []

    if filter_id:
        query += " AND id = ?"
        params.append(filter_id)

    if filter_name:
        query += " AND name LIKE ?"
        params.append(f"%{filter_name}%")

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        if format_type == 'text':
            print("")
        elif format_type == 'json':
            print(json.dumps({"count": 0, "reminders": []}))
        elif format_type == 'polybar':
            print("")
        return

    if format_type == 'json':
        reminders = []
        for row in rows:
            reminders.append({
                "id": row['id'],
                "name": row['name'],
                "message": row['message'],
                "enabled": bool(row['enabled']),
                "pending": bool(row['pending'])
                })
        output = {"count": len(reminders), "reminders": reminders}
        print(json.dumps(output))

    elif format_type == 'polybar':
        # Format for polybar: "🔔 2 | Brush Teeth, Journal"
        names = [row['name'] for row in rows]
        print(f"{', '.join(names)}")

    else:  # text
        for row in rows:
            status = []
            if row['enabled']:
                status.append("ON")
            else:
                status.append("OFF")
            if row['pending']:
                status.append("PENDING")
            status_str = ", ".join(status)
            #print(f"[{row['id']}] {row['name']}: {row['message']} [{status_str}]")
            print(f"{row['name']} {row['message']} [{status_str}]")

def acknowledge_reminder(reminder_id):
    """Acknowledge a specific reminder."""
    conn = get_db_connection()
    cursor = conn.cursor()

    today_str = date.today().isoformat()

    cursor.execute('''
        UPDATE reminders 
        SET pending = 0, acknowledged_date = ? 
        WHERE id = ? AND enabled = 1
    ''', (today_str, reminder_id))

    if cursor.rowcount > 0:
        print(f"✓ Reminder ID {reminder_id} acknowledged.")
    else:
        print(f"✗ No pending reminder found with ID {reminder_id}.")

    conn.commit()
    conn.close()

def acknowledge_all(filter_name=None):
    """Acknowledge all pending reminders."""
    conn = get_db_connection()
    cursor = conn.cursor()

    today_str = date.today().isoformat()

    if filter_name:
        cursor.execute('''
            UPDATE reminders 
            SET pending = 0, acknowledged_date = ? 
            WHERE enabled = 1 AND pending = 1 AND name LIKE ?
        ''', (today_str, f"%{filter_name}%"))
    else:
        cursor.execute('''
            UPDATE reminders 
            SET pending = 0, acknowledged_date = ? 
            WHERE enabled = 1 AND pending = 1
        ''', (today_str,))

    count = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"✓ {count} reminder(s) acknowledged.")

def toggle_reminder(reminder_id, enable=None):
    """Enable or disable a reminder."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if enable is None:
        # Toggle
        cursor.execute('SELECT enabled FROM reminders WHERE id = ?', (reminder_id,))
        row = cursor.fetchone()
        if not row:
            print(f"No reminder found with ID {reminder_id}.")
            conn.close()
            return
        enable = 0 if row['enabled'] else 1

    cursor.execute('UPDATE reminders SET enabled = ? WHERE id = ?', (1 if enable else 0, reminder_id))

    if cursor.rowcount > 0:
        status = "enabled" if enable else "disabled"
        print(f"✓ Reminder ID {reminder_id} {status}.")
    else:
        print(f"No reminder found with ID {reminder_id}.")

    conn.commit()
    conn.close()

def dump_db(filter_id=None, filter_name=None, show_all=True):
    """List all stored reminders."""
    print("Commencing db dump")
    con = get_db_connection()
    cursor = con.cursor()
    rows = con.execute('SELECT * FROM reminders').fetchall()
    for row in rows:
        print(dict(row))

def list_reminders(filter_id=None, filter_name=None, show_all=True):
    """List all stored reminders."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        terminal_width = os.get_terminal_size().columns 
    except:
        terminal_width = 10
    query = "SELECT * FROM reminders WHERE 1=1"
    params = []

    if filter_id:
        query += " AND id = ?"
        params.append(filter_id)

    if filter_name:
        query += " AND name LIKE ?"
        params.append(f"%{filter_name}%")

    query += " ORDER BY id"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No reminders found matching your criteria.")
        return

    print(f"{'ID':<5} {'Name':<20} {'Type':<10} {'Config':<30} {'Status':<20} {'Last Triggered':<20}")
    print("-" * terminal_width)
    for row in rows:
        config = json.loads(row['config'])
        if 'time' in config:
            config_str = f"days={config['days']}, time={config['time']}"
        else:
            config_str = f"days={config['days']}"

        status = []

        if row['enabled']:
            status.append("ON")
        else:
            status.append("OFF")

        if row['pending'] and not row['acknowledged_date']:
            status.append("PENDING")

        status_str = " | ".join(status)
        last_triggered_str = "Never"
        if row['last_triggered']:
            last_triggered_str = row['last_triggered']

        print(f"{row['id']:<5} {row['name']:<20} {row['type']:<10} {config_str:<30} {status_str:<20} {last_triggered_str:<10}")

def delete_reminder(reminder_id):
    """Delete a reminder by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    if cursor.rowcount > 0:
        print(f"✓ Reminder ID {reminder_id} deleted.")
    else:
        print(f"✗ No reminder found with ID {reminder_id}.")
    conn.commit()
    conn.close()

def main():
    init_db()
    parser = argparse.ArgumentParser(description="Local CLI Reminder System with Polybar Support")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    #Add dump argument
    parser_add = subparsers.add_parser('dump-db', help='Dumps the complete database')

    # Add Command
    parser_add = subparsers.add_parser('add', help='Add a new reminder')
    parser_add.add_argument('--name', required=True, help='Name of the event')
    parser_add.add_argument('--message', required=True, help='Message to display')
    parser_add.add_argument('--interval', type=int, help='Trigger every N days')
    parser_add.add_argument('--weekdays', nargs='+', help='Trigger on specific days (0-6 or mon-sun)')
    parser_add.add_argument('--time', type=str, help='Optional time (HH:MM 24h or HH:MM AM/PM)')
    parser_add.add_argument('--disabled', action='store_true', help='Create reminder but disabled')

    # Edit Command
    parser_edit = subparsers.add_parser('edit', help='Edit an existing reminder')
    parser_edit.add_argument('id', type=int, help='ID of the reminder to edit')
    parser_edit.add_argument('--name', type=str, help='New name for the reminder')
    parser_edit.add_argument('--message', type=str, help='New message for the reminder')
    parser_edit.add_argument('--interval', type=int, help='Change to interval trigger (every N days)')
    parser_edit.add_argument('--weekdays', nargs='+', help='Change to weekday trigger (0-6 or mon-sun)')
    parser_edit.add_argument('--time', type=str, help='Change time (HH:MM 24h or HH:MM AM/PM, empty to remove)')
    parser_edit.add_argument('--enable', action='store_true', help='Enable the reminder')
    parser_edit.add_argument('--disable', action='store_true', help='Disable the reminder')

    # Check Command
    parser_check = subparsers.add_parser('check', help='Check and mark due reminders as pending')
    parser_check.add_argument('-v', '--verbose', action='store_true', help='Show verbose output')
    parser_check.add_argument('--id', type=int, help='Check specific reminder by ID')
    parser_check.add_argument('--name', type=str, help='Check reminders matching name (partial match)')

    # Query Command (for polybar)
    parser_query = subparsers.add_parser('query', help='Query pending reminders')
    parser_query.add_argument('-f', '--format', choices=['text', 'json', 'polybar'], 
                              default='text', help='Output format')
    parser_query.add_argument('--id', type=int, help='Filter by reminder ID')
    parser_query.add_argument('--name', type=str, help='Filter by reminder name (partial match)')
    parser_query.add_argument('--all', action='store_true', help='Show all reminders (not just pending)')

    # Acknowledge Command
    parser_ack = subparsers.add_parser('acknowledge', help='Acknowledge a reminder')
    parser_ack.add_argument('id', type=int, nargs='?', help='ID of reminder to acknowledge')
    parser_ack.add_argument('--all', action='store_true', help='Acknowledge all pending')
    parser_ack.add_argument('--name', type=str, help='Acknowledge all pending matching name')

    # Toggle Command
    parser_toggle = subparsers.add_parser('toggle', help='Enable/disable a reminder')
    parser_toggle.add_argument('id', type=int, help='ID of reminder')
    parser_toggle.add_argument('--enable', action='store_true', help='Enable the reminder')
    parser_toggle.add_argument('--disable', action='store_true', help='Disable the reminder')

    # List Command
    parser_list = subparsers.add_parser('list', help='List all reminders')
    parser_list.add_argument('--id', type=int, help='Filter by reminder ID')
    parser_list.add_argument('--name', type=str, help='Filter by reminder name (partial match)')

    # Delete Command
    parser_del = subparsers.add_parser('delete', help='Delete a reminder')
    parser_del.add_argument('id', type=int, help='ID of the reminder to delete')

    # Reset Command
    parser_reset = subparsers.add_parser('reset', help='Reset database (delete all reminders)')
    parser_reset.add_argument('--confirm', action='store_true', help='Confirm database reset')

    args = parser.parse_args()

    if args.command == 'add':
        add_reminder(args.name, args.message, args.interval, args.weekdays, 
                     args.time, enabled=not args.disabled)
    elif args.command == 'dump-db':
        dump_db()
    elif args.command == 'edit':
        edit_reminder(args.id, name=args.name, message=args.message, 
                      interval=args.interval, weekdays=args.weekdays, 
                      time_str=args.time, enable=args.enable, disable=args.disable)
    elif args.command == 'check':
        check_reminders(verbose=args.verbose, filter_id=args.id, filter_name=args.name)
    elif args.command == 'query':
        query_pending(format_type=args.format, filter_id=args.id, 
                      filter_name=args.name, show_all=args.all)
    elif args.command == 'acknowledge':
        if args.id:
            acknowledge_reminder(args.id)
        elif args.name:
            acknowledge_all(filter_name=args.name)
        elif args.all:
            acknowledge_all()
        else:
            print("Error: Specify reminder ID, --name, or --all")
    elif args.command == 'toggle':
        if args.enable:
            toggle_reminder(args.id, enable=True)
        elif args.disable:
            toggle_reminder(args.id, enable=False)
        else:
            toggle_reminder(args.id)
    elif args.command == 'list':
        list_reminders(filter_id=args.id, filter_name=args.name)
    elif args.command == 'delete':
        delete_reminder(args.id)
    elif args.command == 'reset':
        reset_database(confirm=args.confirm)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
