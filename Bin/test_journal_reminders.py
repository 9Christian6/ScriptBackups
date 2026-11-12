"""Behavior checks with disposable SQLite databases and mocked desktop commands."""

from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import Tagebuch as journal
import acknowledge
import reminderScript as reminders


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        patcher = patch.object(reminders, "DB_FILE", Path(temporary.name) / "test.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.output = redirect_stdout(StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        reminders.init_db()
        reminders.add_reminder("Journal", "Journal", list(reminders.WEEKDAY_MAP))

    def test_newest_ack_keeps_gap_and_reset_restores_entries_and_state(self):
        today = date.today()
        start = today - timedelta(days=4)
        reminders.sync_journal_dates({start, today - timedelta(days=1)})
        with reminders.database() as connection:
            original = tuple(connection.execute("SELECT * FROM event_state").fetchone())
        reminders.acknowledge_journal(today)
        with reminders.database() as connection:
            state = connection.execute("SELECT * FROM event_state").fetchone()
            self.assertEqual(state["acknowledged_date"], start.isoformat())
            self.assertEqual(state["pending"], 1)
            self.assertIn(today, reminders.journal_dates(connection))
        self.assertEqual(reminders.get_day_diff(None, 1), "")
        reminders.reset_reminder(1)
        with reminders.database() as connection:
            self.assertEqual(
                tuple(connection.execute("SELECT * FROM event_state").fetchone()),
                original,
            )
            self.assertNotIn(today, reminders.journal_dates(connection))

    def test_badge_counts_only_days_after_newest_entry(self):
        today = date.today()
        reminders.sync_journal_dates(
            {today - timedelta(days=100), today - timedelta(days=4)}
        )
        self.assertEqual(reminders.get_day_diff(None, 1), " (3)")
        reminders.sync_journal_dates({today - timedelta(days=2)})
        self.assertEqual(reminders.get_day_diff(None, 1), " (1)")
        reminders.sync_journal_dates({today - timedelta(days=1)})
        self.assertEqual(reminders.get_day_diff(None, 1), "")
        reminders.sync_journal_dates({today})
        self.assertEqual(reminders.get_day_diff(None, 1), "")

    def test_next_missing_skips_existing_newer_entries(self):
        today = date.today()
        start = today - timedelta(days=3)
        reminders.sync_journal_dates({start, today - timedelta(days=1), today})
        reminders.acknowledge_journal()
        with reminders.database() as connection:
            row = connection.execute("SELECT * FROM event_state").fetchone()
            self.assertEqual(row["acknowledged_date"], today.isoformat())
            self.assertEqual(row["pending"], 0)

    def test_add_accepts_all_weekday_forms_and_rejects_invalid_values_atomically(self):
        event = reminders.add_reminder(
            "Task", "Task", ["mon,tue", "wed thu", "6"], "9:30 PM"
        )
        with reminders.database() as connection:
            rows = connection.execute(
                "SELECT weekday, time FROM event_schedule WHERE event_id = ?", (event,)
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in rows],
                [(0, "21:30"), (1, "21:30"), (2, "21:30"), (3, "21:30"), (6, "21:30")],
            )
        for weekdays, clock in [(["7"], None), (["mon"], "bad"), ([], None)]:
            with self.assertRaises(ValueError):
                reminders.add_reminder("Bad", "Bad", weekdays, clock)
        with reminders.database() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2
            )
        reminders.delete_reminder(event)
        with reminders.database() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM event_schedule WHERE event_id = ?", (event,)
                ).fetchone()[0],
                0,
            )

    def test_new_reminders_trigger_once_and_weekly_reminders_wait_for_next_week(self):
        fixed = datetime(2026, 11, 11, 22)
        with patch.object(reminders, "datetime", wraps=datetime) as clock:
            clock.now.return_value = fixed
            reminders.add_reminder("Weekly", "Weekly", ["wed"], "21:00")
            self.assertEqual(len(reminders.check_reminders()), 2)
            self.assertEqual(reminders.check_reminders(), [])
            clock.now.return_value = fixed + timedelta(days=1)
            self.assertEqual([row["id"] for row in reminders.check_reminders()], [1])
            clock.now.return_value = fixed + timedelta(days=7)
            self.assertEqual({row["id"] for row in reminders.check_reminders()}, {1, 2})

    def test_unknown_and_future_ack_leave_no_history(self):
        for event, day in [(999, None), (1, date.today() + timedelta(days=1))]:
            with self.assertRaises(ValueError):
                reminders.acknowledge(event, day)
        with reminders.database() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM event_state_history"
                ).fetchone()[0],
                0,
            )


class JournalTests(unittest.TestCase):
    @staticmethod
    def entry(day):
        return f"{journal.SEPARATOR}\n{day}\n{journal.SEPARATOR}\n\nExisting text\n"

    def test_gap_insertion_preserves_existing_text_and_date_order(self):
        content = self.entry("10.11.2026") + self.entry("08.11.2026")
        updated, line = journal.prepare_entry(content, date(2026, 11, 9))
        self.assertEqual(
            [day for day, _, _ in journal.journal_headers(updated)],
            [date(2026, 11, day) for day in (10, 9, 8)],
        )
        self.assertEqual(updated.count("Existing text"), 2)
        self.assertEqual(updated.splitlines()[line - 1], journal.SEPARATOR)
        self.assertEqual(
            journal.prepare_entry(updated, date(2026, 11, 9)), (updated, line)
        )

    def test_cancel_does_not_write_open_or_acknowledge(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.txt"
            content = self.entry("10.11.2026")
            path.write_text(content)
            with (
                patch.object(journal, "JOURNAL_PATH", path),
                patch("sys.argv", ["Tagebuch.py"]),
                patch.object(journal, "choose_date", return_value=None),
                patch.object(reminders, "init_db"),
                patch.object(reminders, "sync_journal_dates") as sync,
                patch.object(reminders, "acknowledge_journal") as ack,
                patch.object(journal.subprocess, "run") as run,
            ):
                self.assertEqual(journal.main(), 2)
            self.assertEqual(path.read_text(), content)
            sync.assert_not_called()
            ack.assert_not_called()
            run.assert_not_called()

    def test_acknowledgement_menu_does_not_ack_journal_twice(self):
        with (
            patch.object(
                acknowledge, "select_pending_event", return_value=("1", "Journal")
            ),
            patch.object(acknowledge.subprocess, "run") as run,
            patch.object(acknowledge, "notify") as notify,
        ):
            run.return_value.returncode = 0
            acknowledge.acknowledge_event()
            run.assert_called_once_with(
                ["/home/christian/Bin/Tagebuch.py"], check=False
            )
            notify.assert_called_once_with("Acknowledged: Journal")

    def test_launch_failure_restores_file_and_does_not_acknowledge(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.txt"
            content = self.entry("10.11.2026")
            path.write_text(content)
            with (
                patch.object(journal, "JOURNAL_PATH", path),
                patch("sys.argv", ["Tagebuch.py"]),
                patch.object(journal, "choose_date", return_value=date.today()),
                patch.object(reminders, "init_db"),
                patch.object(reminders, "sync_journal_dates") as sync,
                patch.object(reminders, "acknowledge_journal") as ack,
                patch.object(
                    journal.subprocess, "run", side_effect=OSError("Launch failed")
                ),
                patch("sys.stderr", new=StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    journal.main()
            self.assertEqual(path.read_text(), content)
            sync.assert_not_called()
            ack.assert_not_called()

    def test_menu_contains_both_dates(self):
        today = date.today()
        with patch.object(journal.subprocess, "run") as run:
            label = f"Continue with next missing date ({today - timedelta(days=2):%d.%m.%Y})"
            run.return_value.returncode = 0
            run.return_value.stdout = label
            selected = journal.choose_date(
                {today - timedelta(days=3), today - timedelta(days=1)}, today
            )
            self.assertEqual(selected, today - timedelta(days=2))
            self.assertIn(
                f"Continue with newest date ({today:%d.%m.%Y})",
                run.call_args.kwargs["input"],
            )


if __name__ == "__main__":
    unittest.main()
