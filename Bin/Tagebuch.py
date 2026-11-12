#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
"""Choose a journal date in rofi, open it in Neovim, and record that date."""

from datetime import date, datetime, timedelta
from pathlib import Path
import argparse
import os
import re
import stat
import sqlite3
import subprocess
import tempfile

import reminderScript as reminders

JOURNAL_PATH = Path.home() / "Documents/Tagebuch.txt"
KITTY = Path.home() / "Bin/kitty"
SEPARATOR = "-" * 68
ROFI_THEME = "inputbar { enabled: false; } listview { fixed-height: false; }"
HEADER = re.compile(r"^-{3,}\n(\d{2}\.\d{2}\.\d{4})\n-{3,}[^\S\n]*$", re.MULTILINE)
CANCELLED = 2


def journal_headers(content: str) -> list[tuple[date, int, int]]:
    """Read only date headings enclosed in separator lines."""
    return [
        (datetime.strptime(match[1], "%d.%m.%Y").date(), match.start(), match.end())
        for match in HEADER.finditer(content)
    ]


def choose_date(entries: set[date], newest: date) -> date | None:
    missing = reminders.next_missing_date(entries)
    options = {
        f"Continue with newest date ({newest:%d.%m.%Y})": newest,
        f"Continue with next missing date ({missing:%d.%m.%Y})": missing,
    }
    result = subprocess.run(
        [
            "rofi",
            "-dmenu",
            "-i",
            "-no-custom",
            "-p",
            "Journal",
            "-theme-str",
            ROFI_THEME,
        ],
        input="\n".join(options),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise RuntimeError(f"Rofi failed: {result.stderr.strip()}")
    return options.get(result.stdout.strip())


def prepare_entry(content: str, selected: date) -> tuple[str, int]:
    """Insert missing headings in descending date order; reopen existing entries."""
    headers = journal_headers(content)
    for day, _, end in headers:
        if day == selected:
            return content, content.count("\n", 0, end) + 1
    insertion = next(
        (start for day, start, _ in headers if day < selected), len(content)
    )
    prefix = "\n" if insertion and not content[:insertion].endswith("\n") else ""
    heading = f"{prefix}{SEPARATOR}\n{selected:%d.%m.%Y}\n{SEPARATOR}\n\n"
    updated = content[:insertion] + heading + content[insertion:]
    return updated, content.count("\n", 0, insertion) + bool(prefix) + 3


def write_journal(path: Path, content: str) -> None:
    """Replace the journal atomically, preserving permissions."""
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "offset_days",
        nargs="?",
        type=int,
        help="Compatibility: days after the newest existing entry (skip menu)",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Import journal dates into the database without opening the editor",
    )
    args = parser.parse_args()
    try:
        content = (
            JOURNAL_PATH.read_text(encoding="utf-8") if JOURNAL_PATH.exists() else ""
        )
        entries = {day for day, _, _ in journal_headers(content)}
        reminders.init_db()
        if args.sync:
            reminders.sync_journal_dates(entries)
            print(f"Synchronized {len(entries)} journal dates")
            return 0
        newest = date.today()
        if args.offset_days is not None:
            selected = max(
                entries, default=date.today() - timedelta(days=1)
            ) + timedelta(days=args.offset_days)
        else:
            selected = choose_date(entries, newest)
        if selected is None:
            return CANCELLED
        if selected > date.today():
            raise ValueError("Cannot open a future journal date")
        updated, line = prepare_entry(content, selected)
        if updated != content:
            write_journal(JOURNAL_PATH, updated)
        try:
            subprocess.run(
                [
                    str(KITTY),
                    "--detach",
                    "nvim",
                    f"+{line}",
                    "+normal o",
                    "+startinsert",
                    str(JOURNAL_PATH),
                ],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            # Remove our heading if launching failed and nobody edited the file.
            if (
                updated != content
                and JOURNAL_PATH.read_text(encoding="utf-8") == updated
            ):
                write_journal(JOURNAL_PATH, content)
            raise
        reminders.sync_journal_dates(entries)
        reminders.acknowledge_journal(selected)
        return 0
    except (
        OSError,
        ValueError,
        RuntimeError,
        sqlite3.Error,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
