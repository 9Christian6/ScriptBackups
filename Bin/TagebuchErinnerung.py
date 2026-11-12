#!/bin/python3
"""Show the journal reminder and missing-day count in Polybar."""

from reminderScript import JOURNAL_EVENT_ID, database, get_display_string


def main() -> None:
    with database() as connection:
        reminder = connection.execute(
            """SELECT events.id, 'Tagebuch' AS message
               FROM events JOIN event_state ON events.id = event_state.event_id
               WHERE events.id = ? AND events.enabled = 1 AND event_state.pending = 1""",
            (JOURNAL_EVENT_ID,),
        ).fetchone()
    message = get_display_string(reminder, polybar_format=True) if reminder else None
    print(message or "")


if __name__ == "__main__":
    main()
