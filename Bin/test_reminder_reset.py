"""Reset regression checks using a temporary database and mocked desktop tools."""

from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import acknowledge
import reminderScript as reminders


class ReminderResetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = patch.object(reminders, "DB_FILE", Path(temporary.name) / "test.db")
        database.start()
        self.addCleanup(database.stop)
        output = redirect_stdout(StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        reminders.init_db()
        self.original_date = (date.today() - timedelta(days=3)).isoformat()
        conn = reminders.get_db_connection()
        with conn:
            for event_id in (1, 2):
                conn.execute(
                    "INSERT INTO events (id, name, message) VALUES (?, ?, ?)",
                    (event_id, f"Event {event_id}", "Reminder"),
                )
                conn.execute(
                    """INSERT INTO event_state
                       (event_id, last_triggered, pending, acknowledged_date)
                       VALUES (?, ?, 1, ?)""",
                    (event_id, self.original_date, self.original_date),
                )
        conn.close()

    def state(self, event_id):
        conn = reminders.get_db_connection()
        try:
            return tuple(conn.execute(
                "SELECT * FROM event_state WHERE event_id = ?", (event_id,)
            ).fetchone())
        finally:
            conn.close()

    def test_reset_restores_entire_state_and_leaves_other_events_alone(self):
        original = self.state(2)
        other = self.state(1)
        reminders.acknowledge(2)
        self.assertEqual(self.state(2)[2:], (0, date.today().isoformat()))
        reminders.reset_reminder(2)
        self.assertEqual(self.state(2), original)
        self.assertEqual(self.state(1), other)

    def test_journal_can_undo_multiple_acknowledgements_in_order(self):
        original = self.state(1)
        reminders.acknowledge(1)
        first = self.state(1)
        self.assertEqual(first[2], 1)
        self.assertEqual(first[3], (date.today() - timedelta(days=2)).isoformat())
        reminders.acknowledge_journal()
        reminders.reset_reminder(1)
        self.assertEqual(self.state(1), first)
        reminders.reset_reminder(1)
        self.assertEqual(self.state(1), original)

    def test_no_history_and_unknown_events_do_not_change_state(self):
        original = self.state(2)
        reminders.reset_reminder(2)
        reminders.reset_reminder(999)
        reminders.acknowledge(999)
        self.assertEqual(self.state(2), original)
        reminders.acknowledge(2)
        reminders.reset_reminder(2)
        with redirect_stdout(StringIO()) as output:
            reminders.reset_reminder(2)
        self.assertIn("No saved state", output.getvalue())
        self.assertEqual(self.state(2), original)

    def test_failed_acknowledgement_does_not_save_history(self):
        conn = reminders.get_db_connection()
        with conn:
            conn.execute(
                "UPDATE event_state SET acknowledged_date = NULL WHERE event_id = 1"
            )
        conn.close()
        with self.assertRaises(TypeError):
            reminders.acknowledge(1)
        conn = reminders.get_db_connection()
        try:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM event_state_history"
            ).fetchone()[0], 0)
        finally:
            conn.close()


class ResetMenuTests(unittest.TestCase):
    def test_reset_lists_each_event_once_and_passes_its_id(self):
        with patch.object(acknowledge, "run_command", side_effect=[
            "2 Daily task 0 09:00\n2 Daily task 1 09:00\n3 Daily task 2 None",
            "Reset event 2 to its previous state",
        ]) as run, patch.object(
            acknowledge, "select_option", return_value="2 Daily task"
        ) as select, patch.object(acknowledge, "notify") as notify:
            acknowledge.reset_event()
        select.assert_called_once_with(["2 Daily task", "3 Daily task"])
        self.assertEqual(run.call_args.args[0], [acknowledge.REMINDER_SCRIPT, "reset", "2"])
        notify.assert_called_once_with("Reset event 2 to its previous state")

    def test_cancel_does_not_reset(self):
        with patch.object(acknowledge, "run_command", return_value="2 Task 0 None") as run, patch.object(
            acknowledge, "select_option", return_value=None
        ):
            acknowledge.reset_event()
        run.assert_called_once_with(acknowledge.LIST_COMMAND)


if __name__ == "__main__":
    unittest.main()
